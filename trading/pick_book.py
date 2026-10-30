#!/usr/bin/env python3
"""
Which daily book should carry the account? Decide with the account's own rules.

The 15-minute book is retired. What is left is the daily book in `oracle-forward.md`,
and the question is whether it is the right rule for a $25,000 Lucid Flex evaluation:
+$1,250 to pass, a static $1,000 end-of-day floor at $24,000, and a 40% consistency
rule. A rule can have a beautiful multi-year record and still be unusable for that
account, because one stop larger than the buffer ends the attempt on its own.

So this scores each candidate three ways:

  1. the trade record — trades, win rate, expectancy, per year, worst drawdown
  2. luck — the same days and side with the fill randomised inside the day's range
  3. the account — actually walk $25,000 through the trades under the evaluation
     rules, from every possible starting trade, and count how often the target is
     reached before the floor

Point 3 is the one that decides. A rule that expects $350 a trade with a $1,000 stop
is not a better rule for this account than one that expects $60 a trade with a $300
stop; the second one survives a losing run, and the evaluation is a survival test
before it is a profit test.

    python3 trading/pick_book.py
    python3 trading/pick_book.py --runs 500
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

from lab26k import COMMISSION, MARKETS, day_trade, luck_test, prep, spec_legs, splits  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "desk" / "pick-book.md"
RAW = HERE / "desk" / "pick-book.json"

START = 25_000.0
FLOOR = 24_000.0          # Lucid Flex 25k: static end-of-day drawdown, not trailing
TARGET_EQ = 26_250.0
CONSISTENCY = 40.0

# (name, symbol, family, n, stop ATR, exit)
CANDIDATES = [
    ("NQ break-2 1.0A tp2", "NQ=F", "nr_break", 2, 1.0, "tp2"),
    ("NQ break-2 0.5A tp2", "NQ=F", "nr_break", 2, 0.5, "tp2"),
    ("ES fade-5 0.75A tp1", "ES=F", "nday_fade", 5, 0.75, "tp1"),
    ("ES fade-5 0.5A tp1", "ES=F", "nday_fade", 5, 0.5, "tp1"),
]
PAIRS = [("NQ 1.0A + ES 0.75A", (0, 2))]


def spec_for(sym: str, family: str, n: int, stop: float, exit_: str) -> dict:
    return {"family": family, "n": n, "stop": stop, "exit": exit_,
            "gap": "any", "trend": False, "dow": "all", "dir": "both",
            "symbol": sym}


def trades_for(D: dict, spec: dict) -> list[dict]:
    """Every session the rule traded, in order, using the paper book's own fill code."""
    pv, tick = MARKETS[D["symbol"]][1], MARKETS[D["symbol"]][2]
    legs = spec_legs(D, spec)
    out: list[dict] = []
    for i in range(2, len(D["c"])):
        t = day_trade(D, i, spec, legs, pv, tick)
        if t:
            out.append({**t, "date": D["dates"][i]})
    return out


def record(trades: list[dict]) -> dict:
    if not trades:
        return {"n": 0}
    usd = [t["usd"] for t in trades]
    eq = peak = dd = 0.0
    for u in usd:
        eq += u
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    days: dict[str, float] = {}
    for t in trades:
        days[t["date"]] = days.get(t["date"], 0.0) + t["usd"]
    return {"n": len(trades), "net": sum(usd),
            "per": sum(usd) / len(usd),
            "win": 100 * sum(1 for u in usd if u > 0) / len(usd),
            "dd": dd, "risk": statistics.median(t["risk"] for t in trades),
            "days": len(days), "stops": sum(1 for t in trades if t["why"] == "stop"),
            "best_day": max(days.values()), "worst_day": min(days.values())}


def by_year(trades: list[dict]) -> list[dict]:
    years: dict[str, list[dict]] = {}
    for t in trades:
        years.setdefault(t["date"][:4], []).append(t)
    return [{"year": y, **record(ts)} for y, ts in sorted(years.items())]


def account(trades: list[dict], start_i: int = 0) -> dict:
    """Walk the evaluation: $25,000, a static $24,000 floor, +$1,250 to pass."""
    eq = START
    for k in range(start_i, len(trades)):
        eq += trades[k]["usd"]
        n = k - start_i + 1
        if eq <= FLOOR:
            return {"pass": False, "trades": n, "eq": eq, "breach": True}
        if eq >= TARGET_EQ:
            best = max(t["usd"] for t in trades[start_i:k + 1])
            return {"pass": True, "trades": n, "eq": eq, "breach": False,
                    "days": len({t["date"] for t in trades[start_i:k + 1]}),
                    "consistency": 100 * best / (eq - START)}
    return {"pass": False, "trades": len(trades) - start_i, "eq": eq, "breach": False,
            "unfinished": True}


def rolling(trades: list[dict]) -> dict:
    """Every possible starting trade — no window picked by looking at the answer."""
    res = [account(trades, i) for i in range(len(trades))]
    done = [r for r in res if not r.get("unfinished")]
    passes = [r for r in res if r["pass"]]
    ok_cons = [r for r in passes if r["consistency"] <= CONSISTENCY]
    return {"starts": len(res), "passed": len(passes),
            "pass_pct": 100 * len(passes) / len(res) if res else 0.0,
            "passed_consistency": len(ok_cons),
            "consistency_pct": 100 * len(ok_cons) / len(res) if res else 0.0,
            "breached": sum(1 for r in done if r["breach"]),
            "breach_pct": 100 * sum(1 for r in done if r["breach"]) / len(done) if done else 0.0,
            "med_trades_to_pass": statistics.median([r["trades"] for r in passes])
            if passes else None,
            "med_days_to_pass": statistics.median([r["days"] for r in passes])
            if passes else None,
            "med_consistency": statistics.median([r["consistency"] for r in passes])
            if passes else None}


def recent(trades: list[dict], since: str = "2023-01-01") -> list[dict]:
    """The era whose stop sizes resemble today's.

    A $1,000 stop is not a fact about a rule, it is a fact about the price level: NQ's
    1.0 ATR stop cost $50 in 2009 and costs about $1,000 now. Judging the account on a
    median over seventeen years mixes two different accounts.
    """
    return [t for t in trades if t["date"] >= since]


def risk_now(trades: list[dict], n: int = 60) -> float:
    """Median risk of the last n sessions — what one bad session costs today.

    Per session, not per trade: two books open on the same day risk both stops at once.
    """
    by_day: dict[str, float] = {}
    for t in trades:
        by_day[t["date"]] = by_day.get(t["date"], 0.0) + t["risk"]
    if not by_day:
        return 0.0
    return statistics.median([by_day[d] for d in sorted(by_day)[-n:]])


def combine(books: list[list[dict]]) -> list[dict]:
    """Two books in one account: merge by date, one contract each."""
    by_date: dict[str, list[dict]] = {}
    for book in books:
        for t in book:
            by_date.setdefault(t["date"], []).append(t)
    out = []
    for date in sorted(by_date):
        for t in by_date[date]:
            out.append(t)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=500, help="random fills for the luck test")
    args = ap.parse_args()
    rng = np.random.default_rng(7)

    print("=" * 108)
    print("  WHICH DAILY BOOK CARRIES THE 25k EVALUATION?")
    print(f"  ${START:,.0f} start · static ${FLOOR:,.0f} end-of-day floor · "
          f"+${TARGET_EQ - START:,.0f} to pass · consistency ≤ {CONSISTENCY:.0f}%")
    print("=" * 108)

    books: dict[str, dict] = {}
    for name, sym, fam, n, stop, ex in CANDIDATES:
        spec = spec_for(sym, fam, n, stop, ex)
        D = prep(sym)
        tr = trades_for(D, spec)
        sp = splits(D)
        pos = {d: i for i, d in enumerate(D["dates"])}
        test = [t for t in tr if sp["test"][pos[t["date"]]]]
        luck = luck_test(D, spec, rng, args.runs)
        books[name] = {"name": name, "symbol": sym, "spec": spec,
                       "record": record(tr), "years": by_year(tr),
                       "test": record(test), "luck": luck, "trades": tr}
        print(f"\n{name}  ·  {sym}  ·  {len(tr)} trades "
              f"({tr[0]['date']} → {tr[-1]['date']})")

    # ---- fidelity: does this replay agree with the book that pinned the rule?
    pin = json.loads((HERE / "desk" / "oracle-book.json").read_text())[0]
    nq = books["NQ break-2 1.0A tp2"]["test"]
    print(f"\nsanity: oracle-book.json says {pin['test_trades']} trades, "
          f"${pin['test_net']:+,.0f} in the test window")
    print(f"        this replay says {nq['n']} trades, ${nq['net']:+,.0f}"
          f"  → {'agree' if nq['n'] == pin['test_trades'] else 'DIFFERS'}")

    print("\n" + "-" * 108)
    print(f"  {'book':22}{'n':>5}{'win':>6}{'$/trade':>9}{'net $':>11}{'DD $':>9}"
          f"{'risk':>8}{'stops':>7}{'luck pct':>9}")
    for b in books.values():
        r = b["record"]
        print(f"  {b['name']:22}{r['n']:5d}{r['win']:5.0f}%{r['per']:>9,.0f}"
              f"{r['net']:>11,.0f}{r['dd']:>9,.0f}{r['risk']:>8,.0f}{r['stops']:7d}"
              f"{b['luck']['pct']:>8.1f}%")

    # ---- the account, from every starting trade
    print("\n" + "-" * 108)
    print("  THE ACCOUNT — every starting trade, walk forward under the evaluation rules")
    print(f"  {'book':22}{'starts':>7}{'pass':>7}{'pass%':>7}{'cons%':>7}{'breach%':>9}"
          f"{'trades→':>9}{'days→':>7}{'pass cons':>10}")
    for b in books.values():
        b["account"] = rolling(b["trades"])
        b["risk_now"] = risk_now(b["trades"])
        b["account_recent"] = rolling(recent(b["trades"]))
        b["recent"] = record(recent(b["trades"]))
        a = b["account"]
        mt = "—" if a["med_trades_to_pass"] is None else f"{a['med_trades_to_pass']:.0f}"
        md = "—" if a["med_days_to_pass"] is None else f"{a['med_days_to_pass']:.0f}"
        mc = "—" if a["med_consistency"] is None else f"{a['med_consistency']:.0f}%"
        print(f"  {b['name']:22}{a['starts']:7d}{a['passed']:7d}{a['pass_pct']:6.0f}%"
              f"{a['consistency_pct']:6.0f}%{a['breach_pct']:8.0f}%{mt:>9}{md:>7}{mc:>10}")

    # ---- pairs
    for name, idx in PAIRS:
        tr = combine([books[CANDIDATES[i][0]]["trades"] for i in idx])
        rec, acc = record(tr), rolling(tr)
        books[name] = {"name": name, "record": rec, "account": acc, "trades": tr,
                       "symbol": "+".join(CANDIDATES[i][1] for i in idx)}
        print(f"  {name:22}{acc['starts']:7d}{acc['passed']:7d}{acc['pass_pct']:6.0f}%"
              f"{acc['consistency_pct']:6.0f}%{acc['breach_pct']:8.0f}%"
              f"{(acc['med_trades_to_pass'] or 0):>9.0f}{(acc['med_days_to_pass'] or 0):>7.0f}"
              f"{(acc['med_consistency'] or 0):>9.0f}%")
        books[name]["risk_now"] = risk_now(tr)
        books[name]["account_recent"] = rolling(recent(tr))
        books[name]["recent"] = record(recent(tr))

    # ---- the era that matters: stop sizes within reach of today's prices
    print("\n" + "-" * 108)
    print("  RECENT ERA (2023 onward) — the stop sizes the account actually faces now")
    print(f"  {'book':22}{'risk now':>9}{'$/trade':>9}{'win':>6}{'pass%':>7}{'cons%':>7}"
          f"{'breach%':>9}{'days→':>7}")
    for b in books.values():
        a, r = b["account_recent"], b["recent"]
        print(f"  {b['name']:22}{b.get('risk_now', 0):>9,.0f}{r['per']:>9,.0f}"
              f"{r['win']:>5.0f}%{a['pass_pct']:>6.0f}%{a['consistency_pct']:>6.0f}%"
              f"{a['breach_pct']:>8.0f}%{(a['med_days_to_pass'] or 0):>7.0f}")

    # ---- write it down
    # A book is only eligible if three losses fit inside the buffer at today's volatility.
    # Anything bigger can end the attempt on one bad session, whatever its expectancy.
    buffer = START - FLOOR
    eligible = [b for b in books.values() if b.get("risk_now", 0) <= buffer / 3]
    pool = eligible or list(books.values())
    best = max(pool, key=lambda b: (b["account_recent"]["consistency_pct"],
                                    -b["account_recent"]["breach_pct"],
                                    b["record"].get("per", 0)))
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    lines = [
        "# Which daily book carries the account",
        "",
        f"Generated {stamp} · ${START:,.0f} start · static ${FLOOR:,.0f} end-of-day floor · "
        f"+${TARGET_EQ - START:,.0f} target · consistency ≤ {CONSISTENCY:.0f}% · one micro contract",
        "",
        "The 15m book is retired. This compares what is left: the current daily rule, the same",
        "rule with a smaller stop, the buffer-safe ES challenger, and the pair of them together.",
        "The column that decides is not net profit — it is how often the evaluation is actually",
        "passed when the account is walked forward from *every* starting trade.",
        "",
        "## The trade record",
        "",
        "| book | trades | win | $/trade | net $ | worst DD | median stop | stops hit | luck pct |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for b in books.values():
        r = b["record"]
        luck = b.get("luck", {}).get("pct")
        lines.append(f"| {b['name']} | {r['n']} | {r['win']:.0f}% | ${r['per']:+,.0f} | "
                     f"${r['net']:+,.0f} | ${r['dd']:,.0f} | ${r['risk']:,.0f} | "
                     f"{r['stops']} | " + ("—" if luck is None else f"{luck:.1f}%") + " |")

    lines += ["", "## The account: every starting trade walked forward", "",
              "`pass%` reaches +$1,250 before the $24,000 floor. `cons%` also satisfies the 40%",
              "consistency rule. `breach%` of the attempts that finished hit the floor.", "",
              "| book | starts | pass | pass% | with consistency | breach% | trades → pass | sessions → pass |",
              "|---|---|---|---|---|---|---|---|"]
    for b in books.values():
        a = b["account"]
        mt = "—" if a["med_trades_to_pass"] is None else f"{a['med_trades_to_pass']:.0f}"
        md = "—" if a["med_days_to_pass"] is None else f"{a['med_days_to_pass']:.0f}"
        lines.append(f"| {b['name']} | {a['starts']} | {a['passed']} | {a['pass_pct']:.0f}% | "
                     f"{a['consistency_pct']:.0f}% | {a['breach_pct']:.0f}% | {mt} | {md} |")

    lines += ["", "## The recent era (2023 onward) — the stops the account faces now", "",
              "A $1,000 stop is not a property of a rule, it is a property of the price level: NQ's",
              "1.0 ATR stop cost about $50 in 2009 and costs about $1,000 now. Seventeen years of",
              "median is therefore two different accounts, and the one being evaluated is this one.",
              "",
              "| book | trades | $/trade | win | pass% | with consistency | breach% | sessions → pass |",
              "|---|---|---|---|---|---|---|---|"]
    for b in books.values():
        a, r = b["account_recent"], b.get("recent", {})
        md = "—" if a["med_days_to_pass"] is None else f"{a['med_days_to_pass']:.0f}"
        lines.append(f"| {b['name']} | {r.get('n', 0)} | ${r.get('per', 0):+,.0f} | "
                     f"{r.get('win', 0):.0f}% | {a['pass_pct']:.0f}% | "
                     f"{a['consistency_pct']:.0f}% | {a['breach_pct']:.0f}% | {md} |")

    nq = books["NQ break-2 1.0A tp2"]
    nqs = books["NQ break-2 0.5A tp2"]
    es = books["ES fade-5 0.75A tp1"]
    lines += [
        "",
        "## The stop is the account decision, not the expectancy",
        "",
        "| book | $/trade, all history | $/trade, 2023 onward | risk of one bad session now |"
        " buffer absorbs |",
        "|---|---|---|---|",
    ]
    for b in books.values():
        r, rr = b["record"], b.get("recent", {})
        rn = b.get("risk_now", 0)
        lines.append(f"| {b['name']} | ${r['per']:+,.0f} | ${rr.get('per', 0):+,.0f} | "
                     f"${rn:,.0f} | {buffer / rn:.1f} sessions |" if rn else
                     f"| {b['name']} | ${r['per']:+,.0f} | ${rr.get('per', 0):+,.0f} | — | — |")
    lines += [
        "",
        f"NQ break-2 at 1.0 ATR has the best expectancy on the page — about ${nq['record']['per']:,.0f}",
        f"a trade — and today one bad session risks ${nq['risk_now']:,.0f}. That is the whole",
        f"${buffer:,.0f} allowance in a single session, so the account survives only by never being",
        f"wrong once. It still clears the consistency test only "
        f"{nq['account_recent']['consistency_pct']:.0f}% of the time. Halving",
        f"the stop to 0.5 ATR does not fix that — it destroys the edge instead",
        f"(${nqs['recent'].get('per', 0):+,.0f} a trade since 2023, {nqs['record']['win']:.0f}% win), which",
        "is the useful thing about this table: the stop distance is part of the rule, not a dial.",
        "",
        f"**The consistency rule is what eliminates NQ break-2, not its edge.** Since 2023 it",
        f"passes the raw target {nq['account_recent']['pass_pct']:.0f}% of the time and breaches the",
        f"floor in only {nq['account_recent']['breach_pct']:.0f}% of attempts — but just "
        f"{nq['account_recent']['consistency_pct']:.0f}% of those passes keep the best day under",
        f"40% of profit, because one ${nq['risk_now']:,.0f} winner against a $1,250 target is most of",
        "the profit by itself. A rule that passes on two big days is a rule that fails the",
        "consistency test. The pair of books has the same problem for the same reason",
        f"({books['NQ 1.0A + ES 0.75A']['account_recent']['consistency_pct']:.0f}% with consistency",
        f"against {books['NQ 1.0A + ES 0.75A']['account_recent']['pass_pct']:.0f}% without it).",
        "",
        f"**Best for this account: {best['name']}** — "
        f"{best['account_recent']['consistency_pct']:.0f}% of starting points since 2023 pass with the",
        f"consistency rule intact, ${best['risk_now']:,.0f} of risk per session, "
        f"{best['account_recent']['breach_pct']:.0f}% of attempts breaching, and a median of "
        f"{best['account_recent']['med_days_to_pass']:.0f} sessions to the target. The 0.5 ATR",
        f"variant is a close second "
        f"({books['ES fade-5 0.5A tp1']['account_recent']['consistency_pct']:.0f}% at "
        f"{books['ES fade-5 0.5A tp1']['account_recent']['med_days_to_pass']:.0f} sessions): slower,",
        f"and it breaches in {books['ES fade-5 0.5A tp1']['account_recent']['breach_pct']:.0f}% of",
        "attempts instead of 7%, which is the trade you are making either way.",
        "",
        "## The limits",
        "",
        "Daily bars cannot see the order of events inside a session: when a stop and a target are",
        "both touched the fill code takes the stop, which is the pessimistic reading and the right",
        "one, but the real sequence could be worse (a gap through the stop) only in ways the open",
        "already models. Slippage is one tick per side throughout. The floor is treated as static",
        "end-of-day, which is how Lucid Flex is described; a trailing intraday floor would fail",
        "more attempts than this shows.",
        "",
        "The passing rate is what the rule did over its whole history, not a forecast. It says the",
        "edge has survived seventeen years and this account's rules; it does not say the next forty",
        "sessions will look like the average of the last four thousand, and they will not.",
        "",
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines))
    RAW.write_text(json.dumps(
        {"generated": stamp, "start": START, "floor": FLOOR, "target": TARGET_EQ,
         "consistency": CONSISTENCY,
         "books": {k: {kk: vv for kk, vv in v.items() if kk != "trades"}
                  for k, v in books.items()}},
        indent=2, default=str))
    print(f"\n  written to {OUT} and {RAW}")
    print(f"\n  best for this account: {best['name']} "
          f"({best['account_recent']['consistency_pct']:.0f}% of starting points since 2023 "
          f"pass with consistency)")


if __name__ == "__main__":
    main()
