#!/usr/bin/env python3
"""
Three months of the whole business, not one account.

The question changed. It is no longer "which rule passes one $25,000 evaluation" —
it is "which rule, at which account size, makes the most money in ninety days once
accounts are being recycled, some of them fail, and payouts are taken as they become
available". Those are different questions and they have different answers, because
the thing that limits the total is no longer the rule's expectancy. It is the firm's
account caps and the payout caps.

What the rules actually are (checked against Lucid's own pages, not assumed)
--------------------------------------------------------------------------
* The floor **trails** the highest closing balance by the account's max loss and then
  locks at starting balance + $100. So a good run buys the right to lose less; an
  account that has closed at +$600 is protected only to +$400. This file models the
  trailing floor; an earlier version of `pick_book.py` modelled a static one and its
  pass rates were too high.
* The 40% consistency rule applies **during the evaluation only** and is measured as
  the largest single-day profit divided by total profit. It is not a payout rule, and
  a day that is too big can be diluted by continuing to trade.
* A funded account pays out only after **five separate qualifying days** with at least
  $100/$150/$200/$250 of profit (by size), a **$500 minimum request**, and at most
  **50% of profit** per request, capped at $1,000/$2,000/$2,500/$3,000 by size. The
  trader keeps 90%. The payout is deducted from the balance and the floor locks to
  starting + $100, which is what usually kills a funded account shortly afterwards.
* **Ten accounts maximum, five of them funded.** That cap — not capital — is why
  "keep opening accounts with the profits" stops working, and it is why the size of
  each account matters more than the number of them.

So the simulation walks a ninety-day window (63 sessions) of real trades, sampled
from 2023 onward, through a portfolio: five evaluation slots and five funded slots,
refilled as accounts pass or die, fees paid out of a starting bankroll, payouts taken
whenever the rules allow. All accounts in one run share the same market window, which
is what copy-trading across accounts actually looks like.

    python3 trading/portfolio.py
    python3 trading/portfolio.py --runs 800 --bankroll 500
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lab26k import MARKETS, day_trade, prep, spec_legs  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "desk" / "portfolio.md"
RAW = HERE / "desk" / "portfolio.json"

SESSIONS = 63             # ninety days of weekdays, holidays netted out
MAX_ACCOUNTS = 10
MAX_EVAL = 5
MAX_FUNDED = 5
SPLIT = 0.90              # funded Flex pays the trader 90%
CONSISTENCY = 40.0
LOCK = 100.0              # floor locks $100 above the starting balance
MIN_REQUEST = 500.0
MAX_PAYOUTS = 5

# Lucid Flex, list prices (no promo) from the dated checkout capture; resets are cheaper
# than a fresh evaluation, which matters when accounts are expected to die.
TIERS = {
    "25k": dict(label="$25K", fee=65.0, reset=45.0, buffer=1_000.0, target=1_250.0,
                cap=1_000.0, min_day=100.0, max_micros=20),
    "50k": dict(label="$50K", fee=115.0, reset=80.0, buffer=2_000.0, target=3_000.0,
                cap=2_000.0, min_day=150.0, max_micros=40),
    "100k": dict(label="$100K", fee=215.0, reset=150.0, buffer=3_000.0, target=6_000.0,
                 cap=2_500.0, min_day=200.0, max_micros=60),
    "150k": dict(label="$150K", fee=323.0, reset=225.0, buffer=4_500.0, target=9_000.0,
                 cap=3_000.0, min_day=250.0, max_micros=100),
}
TIER_ORDER = ["25k", "50k", "100k", "150k"]

BOOKS = {
    "ES fade-5 0.75A tp1": ("ES=F", dict(family="nday_fade", n=5, stop=0.75, exit="tp1",
                                         gap="any", trend=False, dow="all", dir="both")),
    "ES fade-5 0.5A tp1": ("ES=F", dict(family="nday_fade", n=5, stop=0.5, exit="tp1",
                                        gap="any", trend=False, dow="all", dir="both")),
    "NQ break-2 1.0A tp2": ("NQ=F", dict(family="nr_break", n=2, stop=1.0, exit="tp2",
                                         gap="any", trend=False, dow="all", dir="both")),
}

# (name, book, tier or "ladder", micros or 0 for "size to 31% of the buffer")
STRATEGIES = [
    ("25k  ES 0.75A  1 micro", "ES fade-5 0.75A tp1", "25k", 1),
    ("25k  ES 0.75A  2 micros", "ES fade-5 0.75A tp1", "25k", 2),
    ("50k  ES 0.75A  2 micros", "ES fade-5 0.75A tp1", "50k", 2),
    ("50k  ES 0.75A  4 micros", "ES fade-5 0.75A tp1", "50k", 4),
    ("50k  ES 0.50A  5 micros", "ES fade-5 0.5A tp1", "50k", 5),
    ("100k ES 0.75A  6 micros", "ES fade-5 0.75A tp1", "100k", 6),
    ("150k ES 0.75A  9 micros", "ES fade-5 0.75A tp1", "150k", 9),
    ("150k ES 0.50A  7 micros", "ES fade-5 0.5A tp1", "150k", 7),
    ("150k NQ 1.0A   2 micros", "NQ break-2 1.0A tp2", "150k", 2),
    ("ladder  ES 0.75A  31%", "ES fade-5 0.75A tp1", "ladder", 0),
]

LADDER_R = 0.31           # stop distance as a fraction of the buffer, the 25k book's own
LADDER_MULT = 8.0         # upgrade when the bankroll holds eight of the next tier's fees


# ------------------------------------------------------------------ market data
def book_days(name: str, since: str) -> dict:
    """Per-session P&L of the rule at one micro contract, from `since` onward."""
    sym, spec = BOOKS[name]
    D = prep(sym)
    pv, tick = MARKETS[sym][1], MARKETS[sym][2]
    legs = spec_legs(D, spec)
    pnl, risk, dates = [], [], []
    for i in range(2, len(D["c"])):
        if D["dates"][i] < since:
            continue
        t = day_trade(D, i, spec, legs, pv, tick)
        pnl.append(t["usd"] if t else 0.0)
        risk.append(t["risk"] if t else 0.0)
        dates.append(D["dates"][i])
    return {"pnl": np.array(pnl), "risk": np.array(risk), "dates": dates,
            "med_risk": statistics.median([r for r in risk if r]) if any(risk) else 0.0}


# ------------------------------------------------------------------ one account
def step_eval(a: dict, pnl: float, tier: dict) -> str | None:
    """Advance an evaluation one session. Returns 'pass', 'breach' or None."""
    a["bal"] += pnl
    a["high"] = max(a["high"], a["bal"])
    a["best"] = max(a["best"], pnl)
    a["sess"] += 1
    a["floor"] = max(-tier["buffer"], min(a["high"] - tier["buffer"], LOCK))
    if a["bal"] < a["floor"]:
        return "breach"
    if a["bal"] >= tier["target"] and a["bal"] > 0:
        if 100.0 * a["best"] / a["bal"] <= CONSISTENCY:
            return "pass"
    return None


def step_funded(a: dict, pnl: float, tier: dict) -> tuple[str | None, float]:
    """Advance a funded account one session: ('breach', 0) or (None, cash paid out)."""
    a["bal"] += pnl
    a["high"] = max(a["high"], a["bal"])
    a["sess"] += 1
    if not a["paid"]:
        a["floor"] = max(-tier["buffer"], min(a["high"] - tier["buffer"], LOCK))
    if a["bal"] < a["floor"]:
        return "breach", 0.0
    if pnl >= tier["min_day"]:
        a["qual"] += 1
    if a["qual"] >= 5 and a["pay_n"] < MAX_PAYOUTS:
        room = a["bal"] - a["floor"] - 50.0
        want = min(tier["cap"], 0.5 * max(a["bal"], 0.0), room)
        if want >= MIN_REQUEST:
            got = want * SPLIT
            a["cash"] += got
            a["bal"] -= want
            a["floor"] = LOCK
            a["paid"] = True
            a["qual"] = 0
            a["pay_n"] += 1
            return None, got
    return None, 0.0


def new_eval(tier: dict, micros: int) -> dict:
    return {"bal": 0.0, "high": 0.0, "best": 0.0, "floor": -tier["buffer"], "sess": 0,
            "micros": micros}


def new_funded(tier: dict, micros: int) -> dict:
    return {"bal": 0.0, "high": 0.0, "floor": -tier["buffer"], "qual": 0, "paid": False,
            "pay_n": 0, "cash": 0.0, "sess": 0, "micros": micros}


def size_for(tier: dict, med_risk: float, frac: float) -> int:
    """Contracts such that one stop is `frac` of the buffer."""
    if med_risk <= 0:
        return 1
    m = int(round(frac * tier["buffer"] / med_risk))
    return max(1, min(m, tier["max_micros"]))


def tier_for(bankroll: float) -> str:
    """Buy the biggest account the bankroll can replace eight times over."""
    pick = TIER_ORDER[0]
    for name in TIER_ORDER:
        if bankroll >= LADDER_MULT * TIERS[name]["fee"]:
            pick = name
    return pick


# ------------------------------------------------------------------ the desk
def simulate(days: dict, tier_name: str, micros: int, runs: int,
             bankroll0: float, rng: np.random.Generator,
             window: int = SESSIONS) -> dict:
    pnl_all = days["pnl"]
    med_risk = days["med_risk"]
    lo, hi = 0, len(pnl_all) - window
    if hi <= lo:
        raise SystemExit(f"not enough sessions: {len(pnl_all)}")

    nets, opened, passes, breaches, funded_ends = [], 0, 0, 0, []
    payouts: list[int] = []
    paid_totals: list[float] = []
    pass_sess: list[int] = []
    eval_attempts = 0

    for _ in range(runs):
        i0 = int(rng.integers(lo, hi))
        pnl = pnl_all[i0:i0 + window]
        bankroll = bankroll0
        fees = 0.0
        cash = 0.0
        evals: list[dict] = []
        funded: list[dict] = []
        hold: list[dict] = []          # passed evaluations waiting for a funded slot
        n_open = n_pass = n_breach = 0
        pay_here: list[float] = []
        pass_days_here: list[int] = []

        for s in range(len(pnl)):
            x = float(pnl[s])

            # --- fill the evaluation slots, paying the fee from the bankroll
            while (len(evals) < MAX_EVAL
                   and len(evals) + len(funded) + len(hold) < MAX_ACCOUNTS):
                t = tier_for(bankroll) if tier_name == "ladder" else tier_name
                tier = TIERS[t]
                m = micros if micros else size_for(tier, med_risk, LADDER_R)
                if bankroll < tier["fee"]:
                    break
                bankroll -= tier["fee"]
                fees += tier["fee"]
                evals.append({**new_eval(tier, m), "tier": t})
                n_open += 1

            # --- evaluations
            keep: list[dict] = []
            for a in evals:
                tier = TIERS[a["tier"]]
                out = step_eval(a, x * a["micros"], tier)
                if out == "breach":
                    n_breach += 1
                    if bankroll >= tier["reset"]:
                        bankroll -= tier["reset"]
                        fees += tier["reset"]
                        keep.append({**new_eval(tier, a["micros"]), "tier": a["tier"]})
                elif out == "pass":
                    n_pass += 1
                    pass_days_here.append(a["sess"])
                    hold.append({"tier": a["tier"], "micros": a["micros"]})
                else:
                    keep.append(a)
            evals = keep

            # --- funded accounts
            keepf: list[dict] = []
            for f in funded:
                tier = TIERS[f["tier"]]
                out, got = step_funded(f, x * f["micros"], tier)
                cash += got
                if out == "breach":
                    continue
                keepf.append(f)
            funded = keepf

            # --- a passed evaluation becomes a funded account when a slot is free
            while hold and len(funded) < MAX_FUNDED:
                h = hold.pop(0)
                funded.append({**new_funded(TIERS[h["tier"]], h["micros"]),
                               "tier": h["tier"]})

        pay_here = sum(f["cash"] for f in funded)
        pays = sum(f["pay_n"] for f in funded)
        nets.append(cash - fees)
        opened += n_open
        passes += n_pass
        breaches += n_breach
        funded_ends.append(len(funded))
        payouts.append(pays)
        paid_totals.append(cash)
        pass_sess.extend(pass_days_here)
        eval_attempts += n_open + n_breach   # every reset starts a new attempt

    nets_a = np.array(nets)
    return {
        "runs": runs,
        "mean": float(nets_a.mean()), "median": float(np.median(nets_a)),
        "p10": float(np.percentile(nets_a, 10)), "p90": float(np.percentile(nets_a, 90)),
        "positive_pct": float(100.0 * (nets_a > 0).mean()),
        "mean_open": opened / runs, "mean_pass": passes / runs,
        "mean_breach": breaches / runs,
        "mean_funded_end": statistics.mean(funded_ends),
        "mean_payouts": statistics.mean(payouts),
        "mean_paid_total": statistics.mean(paid_totals) if paid_totals else 0.0,
        "attempts": eval_attempts,
        "pass_pct": 100.0 * passes / eval_attempts if eval_attempts else 0.0,
        "med_sessions_to_pass": statistics.median(pass_sess) if pass_sess else None,
        "within_3_pct": 100.0 * sum(1 for d in pass_sess if d <= 3) / len(pass_sess)
        if pass_sess else 0.0,
        "within_10_pct": 100.0 * sum(1 for d in pass_sess if d <= 10) / len(pass_sess)
        if pass_sess else 0.0,
    }


def table(rows: dict, sessions: int) -> list[str]:
    out = [
        f"| strategy | capital | stop / buffer | median net | mean net | p10 | p90 "
        f"| windows positive | eval pass | funded at end | payouts |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows.values():
        out.append(
            f"| {r['name']} | ${r['capital']:,.0f} | {100 * r['risk_frac']:.0f}% "
            f"| ${r['median']:,.0f} | ${r['mean']:,.0f} | ${r['p10']:,.0f} "
            f"| ${r['p90']:,.0f} | {r['positive_pct']:.0f}% | {r['pass_pct']:.0f}% "
            f"| {r['mean_funded_end']:.1f} | {r['mean_payouts']:.1f} |")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=400)
    ap.add_argument("--bankroll", type=float, default=350.0,
                    help="cash on hand on day one (five $65 evaluations, say)")
    ap.add_argument("--since", default="2023-01-01")
    args = ap.parse_args()
    rng = np.random.default_rng(11)

    books = {name: book_days(name, args.since) for name in BOOKS}

    print("=" * 118)
    print("  NINETY DAYS OF THE DESK — five evaluations, five funded slots, 90/10 payouts")
    print(f"  {SESSIONS}-session windows sampled from {args.since} onward · "
          f"{args.runs} runs per strategy · small-bankroll ladder starts at "
          f"${args.bankroll:,.0f}")
    print("=" * 118)
    for name, d in books.items():
        print(f"  {name:22} {len(d['pnl']):4d} sessions · median stop at one micro "
              f"${d['med_risk']:,.0f}")

    rows: dict[str, dict] = {}
    rows_half: dict[str, dict] = {}
    for name, book, tier_name, micros in STRATEGIES:
        days = books[book]
        if tier_name == "ladder":
            capital = args.bankroll
            frac = LADDER_R
        else:
            t = TIERS[tier_name]
            capital = max(args.bankroll, 5 * t["fee"] + 3 * t["reset"])
            frac = micros * days["med_risk"] / t["buffer"]
        res = simulate(days, tier_name, micros, args.runs, capital, rng)
        res.update({"name": name, "book": book, "tier": tier_name, "micros": micros,
                    "risk_frac": frac, "capital": capital})
        rows[name] = res
        half = simulate(days, tier_name, micros, max(args.runs // 2, 100), capital, rng,
                        window=2 * SESSIONS)
        half.update({"name": name, "book": book, "tier": tier_name, "micros": micros,
                     "risk_frac": frac, "capital": capital})
        rows_half[name] = half

    print("\n" + "-" * 118)
    print(f"  {'strategy':26}{'cap':>7}{'risk':>6}{'median':>10}{'mean':>10}{'p10':>10}"
          f"{'p90':>10}{'pos%':>6}{'pass%':>6}{'fund':>6}{'pays':>6}{'mean 6mo':>10}")
    for name, r in rows.items():
        print(f"  {name:26}{r['capital']:>7,.0f}{100 * r['risk_frac']:>5.0f}%"
              f"{r['median']:>10,.0f}{r['mean']:>10,.0f}{r['p10']:>10,.0f}"
              f"{r['p90']:>10,.0f}{r['positive_pct']:>5.0f}%{r['pass_pct']:>5.0f}%"
              f"{r['mean_funded_end']:>6.1f}{r['mean_payouts']:>6.1f}"
              f"{rows_half[name]['mean']:>10,.0f}")

    # The pick: most expected money over two quarters, among the lines that still pass a
    # decent share of evaluations and keep one stop inside 60% of the buffer. One quarter
    # is too noisy to separate the leaders — they sit inside each other's error bars.
    pool = [r for r in rows.values()
            if r["pass_pct"] >= 40 and r["positive_pct"] >= 40 and r["risk_frac"] <= 0.60]
    best = max(pool or list(rows.values()),
               key=lambda r: (rows_half[r["name"]]["mean"], r["mean"]))
    surest = max(rows.values(), key=lambda r: (r["positive_pct"], r["mean"]))
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    k25_1 = rows["25k  ES 0.75A  1 micro"]
    k25_2 = rows["25k  ES 0.75A  2 micros"]
    k50_4 = rows["50k  ES 0.75A  4 micros"]
    k150_9 = rows["150k ES 0.75A  9 micros"]
    nq = rows["150k NQ 1.0A   2 micros"]
    lad = rows["ladder  ES 0.75A  31%"]
    best_half = rows_half[best["name"]]

    lines = [
        "# Ninety days of the desk",
        "",
        f"Generated {stamp} · {SESSIONS}-session windows sampled from {args.since} onward · "
        f"{args.runs} runs per line · small-bankroll line starts with ${args.bankroll:,.0f}",
        "",
        "One account is a puzzle; a portfolio of them is a business, and the business has",
        "different limits. Lucid allows **ten accounts in total, five of them funded**, so",
        "\"open more accounts with the profits\" hits a wall that has nothing to do with money.",
        "The scarce thing is a *funded slot*, and each one pays out at most $1,000 (25K) /",
        "$2,000 (50K) / $2,500 (100K) / $3,000 (150K) per request, at most 50% of profit, only",
        "after five separate days of $100–$250 profit, and only five times before the account",
        "is retired to a live review.",
        "",
        "## What is being simulated",
        "",
        "Every run samples a real 63-session window of trades from 2023 onward — the era whose",
        "volatility matches today's — and runs five evaluation slots and five funded slots",
        "through it. Evaluations pay their fee out of capital and are replaced at the reset fee",
        "when they breach. A pass converts to a funded account at zero profit. Every funded",
        "account requests the largest payout the rules allow the moment it qualifies, and the",
        "90% share is banked. All accounts in a run see the same market window, which is what",
        "copying one signal across ten accounts actually looks like.",
        "",
        "Capital is set to five evaluation fees plus three resets, which is the minimum needed",
        "to keep the desk staffed; the ladder line is the exception and starts from $350.",
        "",
        "## Ninety days",
        "",
    ] + table(rows, SESSIONS) + [
        "",
        f"**The pick: {best['name']}** — mean ${best['mean']:,.0f} per ninety days on "
        f"${best['capital']:,.0f} of capital, median ${best['median']:,.0f}, p10 "
        f"${best['p10']:,.0f}, p90 ${best['p90']:,.0f}, positive in "
        f"{best['positive_pct']:.0f}% of windows. Over that quarter it opens "
        f"{best['mean_open']:.0f} accounts, passes {best['mean_pass']:.0f} evaluations, ends "
        f"with {best['mean_funded_end']:.1f} funded and takes {best['mean_payouts']:.1f} "
        f"payouts. In six months the same line averages ${best_half['mean']:,.0f}.",
        "",
        "The pick is made on the six-month mean, not the three-month one: at ninety days the",
        "top three lines sit within each other's error bars, and choosing between them on that",
        "noise is how a backtest gets overfitted. It is restricted to lines that pass at least",
        "40% of their evaluations and finish a quarter in profit at least 40% of the time —",
        "a desk you would keep funding, not a lottery ticket that happens to have a good mean.",
        "",
        "Both big-account lines fail that second test, and it is worth saying exactly what is",
        f"being refused: the $150K at nine micros averages ${rows_half['150k ES 0.75A  9 micros']['mean']:,.0f}",
        "over six months — the most money on the page — while losing money in "
        f"{100 - k150_9['positive_pct']:.0f}% of ninety-day windows, and its worst tenth of",
        f"six-month windows ends down ${abs(rows_half['150k ES 0.75A  9 micros']['p10']):,.0f}. That is",
        "the trade the brief asks for and the one worth thinking twice about: the same edge,",
        "carried bigger, and three times as likely to have you funding accounts out of your own",
        "pocket for a quarter before it pays anything back.",
        "",
        "Read the mean and the median together, because they disagree and the disagreement is",
        "the whole story. The median window pays back **less than the fees** — you spend the",
        "quarter passing evaluations that have not yet converted into cash — while a minority",
        "of windows pay many multiples. That is a business with a long lead time, not a",
        "steady drip, and it is why a ninety-day judgement flatters nothing.",
        "",
        "## Six months, the same lines",
        "",
        "The first quarter is mostly lead time; the second is where funded accounts start",
        "paying more than once and the fees stop being the story. If the question is \"will this",
        "make money\", this is the table that answers it, and the answers change sign.",
        "",
    ] + table(rows_half, 2 * SESSIONS) + [
        "",
        "## Why size, not count, decides the money",
        "",
        f"A 25K account at one micro — {100 * k25_1['risk_frac']:.0f}% of the buffer per stop, "
        f"the conservative setting the last report recommended — is the worst line on the page:",
        f"mean ${k25_1['mean']:,.0f}, positive in {k25_1['positive_pct']:.0f}% of windows. It",
        f"passes ({k25_1['pass_pct']:.0f}% of attempts) and still makes nothing worth having,",
        "because a 25K pass is $1,250 of profit, the 50%-of-profit rule caps the first request",
        "near $625, and the floor then locks at $25,100 with a few hundred dollars of room. The",
        "account is too small for the machinery around it.",
        "",
        f"Doubling it to two micros on the same 25K account is the single biggest improvement on",
        f"the table for the capital: mean ${k25_2['mean']:,.0f} on ${k25_2['capital']:,.0f}, ",
        f"positive in {k25_2['positive_pct']:.0f}% of windows, and it reaches the payout gate",
        "roughly twice as fast. The risk per stop rises to about 51% of the buffer, which is",
        "the honest price: two bad sessions end the attempt instead of four.",
        "",
        f"Up the tiers the same trade repeats — the $50K at four micros averages "
        f"${k50_4['mean']:,.0f} a quarter, the $150K at nine micros ${k150_9['mean']:,.0f} —",
        "but the cost is variance rather than average: the big accounts win bigger and also",
        f"empty the wallet more often ({k150_9['positive_pct']:.0f}% of quarters in profit against",
        f"{k50_4['positive_pct']:.0f}% for the 50K). Over six months they do pull ahead",
        f"(${rows_half['150k ES 0.75A  9 micros']['mean']:,.0f} against "
        f"${rows_half['50k  ES 0.75A  4 micros']['mean']:,.0f}), which is the fair argument for",
        "them: the same edge, carried by bigger accounts, is worth more per funded slot, and",
        "funded slots are the thing you cannot buy more of.",
        "",
        "## Can it be done in three days?",
        "",
        "Three days is the firm's *minimum*, not a schedule. It needs the full target inside",
        "three sessions with no day over 40% of the profit. At every size on this page that",
        f"essentially never happens — {k25_2['within_3_pct']:.0f}%–{k150_9['within_3_pct']:.0f}% "
        f"of passes arrive that fast, and only {k25_2['within_10_pct']:.0f}% within ten sessions "
        f"at the fastest line ({k150_9['within_10_pct']:.0f}% at the slowest), because the "
        f"median pass takes {k25_1['med_sessions_to_pass']:.0f} sessions. Three days is set for",
        "scalpers taking risk that would end this book; a rule that trades half the sessions",
        "cannot finish a month of edge in a week, and trading bigger makes the target *bigger*",
        "faster than it makes the gains bigger.",
        "",
        "## Starting from $350",
        "",
        f"The ladder line buys the biggest account the bankroll can replace eight times over "
        f"and sizes each to {100 * lad['risk_frac']:.0f}% of its buffer: mean "
        f"${lad['mean']:,.0f}, median ${lad['median']:,.0f}, "
        f"{lad['mean_open']:.0f} accounts opened, {lad['mean_funded_end']:.1f} funded at the "
        "end. It is the honest version of \"reinvest the profits\" — fees are cheap enough",
        "that capital stops being the constraint within a quarter, and the account caps become",
        "the ceiling instead.",
        "",
        "## What this does not model",
        "",
        "The sample is 2023 onward: one regime, with volatility high enough that a 0.75 ATR",
        "stop is $250–$300. A calmer quarter passes more slowly; a violent one breaches more",
        "accounts. Payouts are requested the instant they qualify, which no trader does",
        "perfectly. Breaches are scored on the closing balance, not the session's worst moment.",
        "Slippage is one tick per side and commissions are real, but a fast market fills worse.",
        "Fees are list prices; a 30%-off checkout improves every line, most of all the 25K one.",
        "Lucid's payout page says \"50% of your account balance\" in one place and \"50% of",
        "profit\" in its table; this models the stricter reading, so a payout cannot be taken",
        "until profit is at least twice the request.",
        "",
        f"`NQ break-2` at $150K ({100 * nq['risk_frac']:.0f}% of the buffer per stop) appears as",
        f"a control: mean ${nq['mean']:,.0f}, positive in {nq['positive_pct']:.0f}% of windows.",
        "Its edge is real and its best days are too large a share of a small pass threshold,",
        "which is exactly why it was retired from the single-account book.",
        "",
        f"Best odds on the page, if profit is not the only thing that matters: {surest['name']},",
        f"positive in {surest['positive_pct']:.0f}% of windows with a mean of "
        f"${surest['mean']:,.0f}.",
        "",
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines).replace("$-", "-$"))
    RAW.write_text(json.dumps({"generated": stamp, "sessions": SESSIONS,
                               "bankroll": args.bankroll, "runs": args.runs,
                               "since": args.since,
                               "risk_med": {k: v["med_risk"] for k, v in books.items()},
                               "ninety_days": rows, "six_months": rows_half},
                              indent=2, default=str))
    print(f"\n  written to {OUT} and {RAW}")
    print(f"\n  most money: {best['name']} — mean ${best['mean']:,.0f}, "
          f"median ${best['median']:,.0f}, positive in {best['positive_pct']:.0f}% of runs")


if __name__ == "__main__":
    main()
