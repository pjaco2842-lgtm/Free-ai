#!/usr/bin/env python3
"""
From "a rule with an edge" to "this account, this goal".

The lab answers "is there an edge". This answers the only questions that matter
after that:

  1. Does one contract even FIT? At $25,000 risking 1% ($250) you cannot trade
     MNQ when its stop is 150 points x $2 = $300. Whole-contract granularity is
     where most retail plans quietly stop being possible.
  2. How long to +$1,250 (+5%)? Measured from EVERY month in history, not from
     the one start date that happens to look good.
  3. What happens if the edge is half as strong as the backtest says? A rule
     that only reaches the goal at full historical strength is not a plan.
  4. Do these rules actually diversify, or are they three versions of "buy the
     dip on an index"?

Sizing is fixed-fractional on live equity, whole contracts, no margin fantasy.

    python3 trading/target.py --risk 0.01
    python3 trading/target.py --risk 0.02 --haircut 0.5 --slip 2
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lab  # noqa: E402
from lab import COMMISSION, COMMS, MARKETS, RULES, atr_series, ema, fetch_daily, simulate  # noqa: E402

# The three rules that beat 500 random-entry versions in BOTH directions of time.
# params = the setting the lab selected; stop/hold/entry come from RULES.
WATCHLIST = [
    ("NQ=F", "fade_trend_day", {"trend": 1.5}),
    ("YM=F", "fade_trend_day", {"trend": 1.5}),
    ("ZS=F", "nr_break", {"lookback": 7}),
]
# MARKETS already uses MNQ/MYM point values for NQ/YM; ZS is the only
# full-size contract in this watchlist. CME MZS is 500 bu (1/10 ZS) and has
# a 0.5-cent tick vs ZS's 0.25-cent tick.
MICRO_ADJUSTMENTS = {"ZS=F": (0.1, 2.0)}  # (point-value multiplier, tick-size multiplier)
DAILY_TRADE_CAP = 20  # Lucid 25K account: 20 micros / 2 minis total per day
ALT_PARAMS = {  # the neighbours, to show the choice isn't a knife-edge
    "fade_trend_day": [{"trend": t} for t in (1.2, 1.5, 2.0)],
    "nr_break": [{"lookback": n} for n in (5, 7, 10)],
}


def load(symbol, rule, params, slip_ticks=None, micro=False):
    name, pv, tick = MARKETS[symbol]
    if micro and symbol in MICRO_ADJUSTMENTS:
        pv_scale, tick_scale = MICRO_ADJUSTMENTS[symbol]
        pv *= pv_scale
        tick *= tick_scale
    comm = COMMS.get(symbol, COMMISSION)
    cost_ticks = lab.SLIP_TICKS if slip_ticks is None else slip_ticks
    bars = fetch_daily(symbol)
    atr = atr_series(bars)
    emas = {k: ema([b.c for b in bars], k) for k in (20, 50, 200)}
    fn, _grid, cfg = RULES[rule]
    previous_slip = lab.SLIP_TICKS
    try:
        if slip_ticks is not None:
            lab.SLIP_TICKS = slip_ticks
        trades = simulate(bars, atr, fn(bars, atr, emas, params), cfg["stop"], pv, tick,
                          hold=cfg.get("hold", 1), entry=cfg["entry"], comm=comm)
    finally:
        lab.SLIP_TICKS = previous_slip
    round_trip_cost = 2 * (comm + cost_ticks * tick * pv)
    for t in trades:
        t["symbol"], t["rule"] = symbol, rule
        t["pv"] = pv
        t["round_trip_cost_usd"] = round_trip_cost
    return trades


def run_account(trades, start=25000.0, risk_pct=0.01, contracts_cap=10, haircut=1.0,
                min_contracts=1, daily_contracts_cap=DAILY_TRADE_CAP, daily_stop_frac=0.02,
                daily_loss_limit=None):
    """Chronological sizing with per-symbol overlap, aggregate daily risk and contract caps."""
    equity = start
    peak = start
    max_dd = 0.0
    skipped = 0
    taken = 0
    breach = 0        # trades spent below 90% of the running peak
    curve = []
    busy_until = {}
    current_day = None
    day_risk_remaining = 0.0
    day_contracts = 0
    daily_blocked = False
    day_start_equity = start
    day_loss_limit = start * daily_stop_frac
    daily_stop_hits = 0
    for t in sorted(trades, key=lambda t: (t["date"], t["symbol"])):
        if t["date"] != current_day:
            current_day = t["date"]
            day_start_equity = equity
            day_loss_limit = day_start_equity * daily_stop_frac
            if daily_loss_limit is not None:
                day_loss_limit = min(day_loss_limit, daily_loss_limit)
            day_risk_remaining = equity * risk_pct
            day_contracts = 0
            daily_blocked = False
        if day_start_equity - equity >= day_loss_limit:
            if not daily_blocked:
                daily_stop_hits += 1
            daily_blocked = True
            day_risk_remaining = 0.0
        sym = t["symbol"]
        if busy_until.get(sym) and t["date"] <= busy_until[sym]:
            continue
        gross_unit_risk = t["risk_pts"] * t["pv"]
        budget_unit_risk = gross_unit_risk + t.get("round_trip_cost_usd", 0.0)
        if budget_unit_risk <= 0:
            skipped += 1
            continue
        contracts = int(day_risk_remaining // budget_unit_risk)
        contracts = min(max(contracts, 0), contracts_cap, daily_contracts_cap - day_contracts)
        if contracts <= 0 or contracts < min_contracts:
            skipped += 1
            continue
        pnl = t["net"] * haircut * gross_unit_risk * contracts
        day_risk_remaining -= budget_unit_risk * contracts
        day_contracts += contracts
        equity += pnl
        taken += 1
        busy_until[sym] = t["date"]
        if day_start_equity - equity >= day_loss_limit:
            if not daily_blocked:
                daily_stop_hits += 1
            daily_blocked = True
            day_risk_remaining = 0.0
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
        if equity < 0.9 * peak:
            breach += 1
        curve.append((t["date"], equity, pnl, sym, t["rule"]))
    return {"final": equity, "pnl": equity - start, "max_dd": max_dd,
            "taken": taken, "skipped": skipped, "curve": curve, "breach": breach,
            "daily_stop_hits": daily_stop_hits,
            "min_dd_pct": 100 * max_dd / start}


def lucid_start_sweep(trades, start, target_profit, risk_pct, max_loss=1000.0,
                      consistency=0.50, contracts_cap=DAILY_TRADE_CAP,
                      daily_contracts_cap=DAILY_TRADE_CAP, daily_stop_frac=0.02,
                      daily_loss_limit=None, haircut=1.0, horizon_days=None):
    """Replay each historical start with fresh equity and approximate Lucid 25K EOD rules.

    horizon_days limits each attempt to that many trading days, which is how the
    "pass in a week" question gets answered instead of guessed.
    """
    by_day = defaultdict(list)
    for trade in trades:
        by_day[trade["date"]].append(trade)
    all_days = sorted(by_day)
    results = []
    for start_index, start_date in enumerate(all_days):
        equity = peak = start
        floor = start - max_loss
        largest_day = 0.0
        pass_result = None
        breach_date = None
        trades_seen = 0
        window = all_days[start_index:]
        if horizon_days is not None:
            window = window[:horizon_days]
        for day in window:
            day_start = equity
            risk_left = equity * risk_pct
            day_contracts = 0
            used_symbols = set()
            day_limit = day_start * daily_stop_frac
            if daily_loss_limit is not None:
                day_limit = min(day_limit, daily_loss_limit)
            for t in sorted(by_day[day], key=lambda trade: trade["symbol"]):
                if day_start - equity >= day_limit:
                    break
                if t["symbol"] in used_symbols:
                    continue
                gross_unit = t["risk_pts"] * t["pv"]
                budget_unit = gross_unit + t.get("round_trip_cost_usd", 0.0)
                if budget_unit <= 0 or risk_left < budget_unit:
                    continue
                count = min(int(risk_left // budget_unit), contracts_cap,
                            daily_contracts_cap - day_contracts)
                if count <= 0:
                    continue
                equity += t["net"] * haircut * gross_unit * count
                risk_left -= budget_unit * count
                day_contracts += count
                trades_seen += count
                used_symbols.add(t["symbol"])
            day_pnl = equity - day_start
            largest_day = max(largest_day, day_pnl)
            peak = max(peak, equity)
            floor = max(floor, min(peak - max_loss, start + 100.0))
            if equity <= floor:
                breach_date = day
                break
            profit = equity - start
            ratio = largest_day / profit if profit > 0 else float("inf")
            if profit >= target_profit and ratio <= consistency:
                pass_result = {"date": day, "profit": profit,
                               "largest_day": largest_day, "consistency": ratio}
                break
        results.append({"start_date": start_date, "pass": pass_result,
                        "breach_date": breach_date, "trades_seen": trades_seen,
                        "days_to_outcome": ((datetime.strptime(pass_result["date"], "%Y-%m-%d") -
                                              datetime.strptime(start_date, "%Y-%m-%d")).days
                                             if pass_result else None)})
    passes = [r for r in results if r["pass"]]
    breaches = [r for r in results if r["breach_date"]]
    pass_days = sorted(r["days_to_outcome"] for r in passes)
    return {"starts": len(results), "passes": len(passes), "breaches": len(breaches),
            "passed_without_breach_pct": 100 * len(passes) / len(results) if results else 0.0,
            "median_days_to_pass": statistics.median(pass_days) if pass_days else None,
            "pass_day_p25": pass_days[len(pass_days) // 4] if pass_days else None,
            "pass_day_p75": pass_days[(3 * len(pass_days)) // 4] if pass_days else None,
            "no_outcome_by_end": sum(r["pass"] is None and r["breach_date"] is None for r in results),
            "no_trade_windows": sum(1 for r in results if r["trades_seen"] == 0),
            "horizon_days": horizon_days,
            "consistency_limit": consistency, "max_loss": max_loss,
            "examples": [r for r in results if r["pass"]][:5]}


def months_between(a: str, b: str) -> float:
    da = datetime.strptime(a, "%Y-%m-%d")
    db = datetime.strptime(b, "%Y-%m-%d")
    return (db - da).days / 30.44


def time_to_target(curve, start, target, sample_every=1):
    """From every k-th entry in the curve, how many months until equity >= target?"""
    out = []
    for i in range(0, len(curve), sample_every):
        d0, e0, *_ = curve[i]
        goal = e0 * target
        for d1, e1, *_ in curve[i + 1:]:
            if e1 >= goal:
                out.append(months_between(d0, d1))
                break
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--equity", type=float, default=25000.0)
    ap.add_argument("--target", type=float, default=1.05, help="multiple of equity")
    ap.add_argument("--risk", type=float, default=0.01,
                    help="maximum planned risk per trading day as a fraction of equity")
    ap.add_argument("--haircut", type=float, default=1.0, help="scale every R by this")
    ap.add_argument("--slip", type=int, default=None, help="slippage ticks (default: lab's 1)")
    ap.add_argument("--contracts-cap", type=int, default=DAILY_TRADE_CAP,
                    help="per-signal cap, also constrained by combined daily cap (Lucid 25K: 20)")
    ap.add_argument("--micro", action="store_true",
                    help="convert standard ZS to MZS; NQ/YM market values already represent MNQ/MYM")
    ap.add_argument("--daily-contracts-cap", type=int, default=DAILY_TRADE_CAP,
                    help="maximum combined contracts entered on one day (Lucid 25K: 20 micros)")
    ap.add_argument("--daily-stop", type=float, default=0.02,
                    help="stop opening trades after this fraction of daily loss (default 2%%)")
    ap.add_argument("--lucid-daily-loss-limit", type=float, default=None,
                    help="also apply fixed daily loss cap in dollars, e.g. 600; unset for LucidPro")
    ap.add_argument("--lucid-max-loss", type=float, default=1000.0,
                    help="Lucid 25K max loss limit in dollars")
    ap.add_argument("--consistency", type=float, default=0.50,
                    help="maximum largest-day-profit / account-profit ratio")
    ap.add_argument("--horizon-days", type=int, default=None,
                    help="limit each replay to N trading days (e.g. 5 for a one-week attempt)")
    ap.add_argument("--json", default="trading/target.json")
    args = ap.parse_args()

    all_trades = []
    per_rule = {}
    print("=" * 96)
    print(f"  TARGET — ${args.equity:,.0f} -> ${args.equity * args.target:,.0f}  "
          f"(+{100 * (args.target - 1):.1f}%)   planned daily risk {100 * args.risk:.1f}%")
    print("=" * 96)
    print(f"\n  {'symbol':9}{'rule':17}{'trades':>7}{'yrs':>6}{'R total':>9}{'$/trade':>9}{'min risk':>10}")

    for symbol, rule, params in WATCHLIST:
        try:
            trades = load(symbol, rule, params, slip_ticks=args.slip, micro=args.micro)
        except Exception as err:  # noqa: BLE001
            print(f"  {symbol:9}{rule:17}  fetch failed: {err}")
            continue
        per_rule[f"{symbol} {rule}"] = trades
        all_trades.extend(trades)
        yrs = months_between(trades[0]["date"], trades[-1]["date"]) / 12 if trades else 0
        unit = statistics.mean(t["risk_pts"] * t["pv"] for t in trades) if trades else 0
        print(f"  {symbol:9}{rule:17}{len(trades):>7}{yrs:>6.1f}"
              f"{sum(t['net'] for t in trades):>9.1f}"
              f"{sum(t['net'] for t in trades) * unit / max(len(trades), 1):>9.0f}"
              f"{unit:>10,.0f}")

    # --- per-rule accounts (does one contract even fit?)
    print(f"\n  {'account':<26}{'trades':>7}{'skipped':>9}{'final':>11}{'max DD':>10}{'DD %':>7}")
    solo = {}
    for label, trades in per_rule.items():
        r = run_account(trades, args.equity, args.risk, args.contracts_cap, args.haircut,
                        daily_contracts_cap=args.daily_contracts_cap, daily_stop_frac=args.daily_stop,
                        daily_loss_limit=args.lucid_daily_loss_limit)
        solo[label] = r
        print(f"  {label:<26}{r['taken']:>7}{r['skipped']:>9}{r['final']:>11,.0f}"
              f"{r['max_dd']:>10,.0f}{r['min_dd_pct']:>7.1f}")

    # --- combined
    comb = run_account(all_trades, args.equity, args.risk, args.contracts_cap, args.haircut,
                       daily_contracts_cap=args.daily_contracts_cap, daily_stop_frac=args.daily_stop,
                       daily_loss_limit=args.lucid_daily_loss_limit)
    print(f"  {'ALL THREE TOGETHER':<26}{comb['taken']:>7}{comb['skipped']:>9}"
          f"{comb['final']:>11,.0f}{comb['max_dd']:>10,.0f}{comb['min_dd_pct']:>7.1f}"
          f"{('  -10% x' + str(comb['breach'])) if comb['breach'] else ''}")
    lucid = lucid_start_sweep(
        all_trades, args.equity, args.equity * (args.target - 1), args.risk,
        args.lucid_max_loss, args.consistency, args.contracts_cap,
        args.daily_contracts_cap, args.daily_stop, args.lucid_daily_loss_limit,
        args.haircut, args.horizon_days)
    print("\n  LUCID EVALUATION CHECK (historical start-date replay; daily bars only)")
    print(f"    {lucid['passes']}/{lucid['starts']} historical signal-date starts passed "
          f"profit/consistency without max-loss breach ({lucid['passed_without_breach_pct']:.1f}%)")
    print(f"    max-loss breaches before pass: {lucid['breaches']}; "
          f"unfinished by sample end: {lucid['no_outcome_by_end']}")
    print(f"    windows with no signal at all: {lucid['no_trade_windows']}/{lucid['starts']}")
    if lucid["median_days_to_pass"] is not None:
        print(f"    pass timing: median {lucid['median_days_to_pass']:.0f} calendar days "
              f"(p25 {lucid['pass_day_p25']}, p75 {lucid['pass_day_p75']})")
    else:
        print("    no pass times to report")

    yrs = months_between(comb["curve"][0][0], comb["curve"][-1][0]) / 12
    print(f"\n  {comb['taken']} trades over {yrs:.1f} years "
          f"({comb['taken'] / yrs:.1f}/yr) · final ${comb['final']:,.0f} · "
          f"P&L ${comb['pnl']:+,.0f}")

    # --- time to the goal, from every start point
    tt = time_to_target(comb["curve"], args.equity, args.target)
    if tt:
        tt_sorted = sorted(tt)
        print(f"\n  TIME TO +{100 * (args.target - 1):.0f}%, measured from {len(tt)} different start dates")
        print(f"    median {statistics.median(tt_sorted):.1f} months · "
              f"fastest {tt_sorted[0]:.1f} · slowest {tt_sorted[-1]:.1f}")
        for q, label in ((0.25, "25%"), (0.5, "50%"), (0.75, "75%"), (0.9, "90%")):
            print(f"      {label:>4} of starts got there within "
                  f"{tt_sorted[min(int(q * len(tt_sorted)), len(tt_sorted) - 1)]:.1f} months")
        print(f"    never reached it from {len(comb['curve']) - len(tt)} sampled starts")
    else:
        print("\n  the goal is never reached from any sampled start at this size")

    # --- reality check: what compound rate does this target actually demand?
    if comb["curve"]:
        span_years = months_between(comb["curve"][0][0], comb["curve"][-1][0]) / 12
        growth = comb["final"] / args.equity
        cagr = growth ** (1 / span_years) - 1 if span_years > 0 and growth > 0 else 0.0
        print(f"\n  REALITY CHECK — {100 * cagr:+.1f}%/yr compounded over {span_years:.1f} years")
        if cagr > 0 and args.target > growth:
            need = math.log(args.target) / math.log(1 + cagr)
            print(f"    to ${args.equity * args.target:,.0f} at this rate: "
                  f"~{need:.0f} years, starting now")
        elif args.target > growth:
            print("    the curve does not compound — the target is never reached")
        else:
            print("    the target is reached inside the tested history")

    # --- correlation: is this diversification or three copies of one bet?
    monthly = defaultdict(lambda: defaultdict(float))
    for label, trades in per_rule.items():
        for t in trades:
            monthly[label][t["date"][:7]] += t["net"]
    labels = list(monthly)
    print("\n  CORRELATION of monthly R (are these independent bets?)")
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            a, b = monthly[labels[i]], monthly[labels[j]]
            keys = sorted(set(a) | set(b))
            xs = [a.get(k, 0.0) for k in keys]
            ys = [b.get(k, 0.0) for k in keys]
            if len(keys) < 10 or statistics.pstdev(xs) == 0 or statistics.pstdev(ys) == 0:
                continue
            m = statistics.correlation(xs, ys)
            print(f"    {labels[i]:<26} vs {labels[j]:<26} r = {m:+.2f}")

    # --- parameter neighbours: is the winner a knife-edge setting?
    print("\n  PARAMETER NEIGHBOURS (full-history R, same stop) — a lone spike = coincidence")
    for symbol, rule, _params in WATCHLIST:
        line = []
        for p in ALT_PARAMS[rule]:
            trades = load(symbol, rule, p, slip_ticks=args.slip, micro=args.micro)
            line.append(f"{list(p.values())[0]}={sum(t['net'] for t in trades):+.1f}R")
        print(f"    {symbol:8}{rule:17} " + "   ".join(line))

    out = {"equity": args.equity, "risk": args.risk, "haircut": args.haircut,
           "lucid_start_sweep": lucid,
           "combined": {k: v for k, v in comb.items() if k != "curve"},
           "solo": {k: {kk: vv for kk, vv in v.items() if kk != "curve"} for k, v in solo.items()},
           "months_to_target": sorted(tt)}
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(out, indent=2))
    print(f"\n  written: {args.json}")


if __name__ == "__main__":
    main()
