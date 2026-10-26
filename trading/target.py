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
ALT_PARAMS = {  # the neighbours, to show the choice isn't a knife-edge
    "fade_trend_day": [{"trend": t} for t in (1.2, 1.5, 2.0)],
    "nr_break": [{"lookback": n} for n in (5, 7, 10)],
}


def load(symbol, rule, params, slip_ticks=None):
    name, pv, tick = MARKETS[symbol]
    comm = COMMS.get(symbol, COMMISSION)
    bars = fetch_daily(symbol)
    atr = atr_series(bars)
    emas = {k: ema([b.c for b in bars], k) for k in (20, 50, 200)}
    fn, _grid, cfg = RULES[rule]
    if slip_ticks is not None:
        import lab as _lab
        keep = _lab.SLIP_TICKS
        _lab.SLIP_TICKS = slip_ticks
    trades = simulate(bars, atr, fn(bars, atr, emas, params), cfg["stop"], pv, tick,
                      hold=cfg.get("hold", 1), entry=cfg["entry"], comm=comm)
    if slip_ticks is not None:
        import lab as _lab
        _lab.SLIP_TICKS = keep
    for t in trades:
        t["symbol"], t["rule"] = symbol, rule
        t["pv"] = pv
    return trades


def run_account(trades, start=25000.0, risk_pct=0.01, contracts_cap=10, haircut=1.0, min_contracts=1):
    """Chronological, one position at a time per symbol, whole contracts only."""
    equity = start
    peak = start
    max_dd = 0.0
    skipped = 0
    taken = 0
    breach = 0        # trades spent below 90% of the running peak
    curve = []
    busy_until = {}
    for t in sorted(trades, key=lambda t: (t["date"], t["symbol"])):
        sym = t["symbol"]
        if busy_until.get(sym) and t["date"] <= busy_until[sym]:
            continue
        risk_usd = equity * risk_pct
        unit_risk = t["risk_pts"] * t["pv"]
        contracts = int(risk_usd // unit_risk) if unit_risk > 0 else 0
        contracts = min(max(contracts, 0), contracts_cap)
        if contracts < min_contracts:
            skipped += 1
            continue
        pnl = t["net"] * haircut * unit_risk * contracts
        equity += pnl
        taken += 1
        busy_until[sym] = t["date"]
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
        if equity < 0.9 * peak:
            breach += 1
        curve.append((t["date"], equity, pnl, sym, t["rule"]))
    return {"final": equity, "pnl": equity - start, "max_dd": max_dd,
            "taken": taken, "skipped": skipped, "curve": curve, "breach": breach,
            "min_dd_pct": 100 * max_dd / start}


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
    ap.add_argument("--risk", type=float, default=0.01)
    ap.add_argument("--haircut", type=float, default=1.0, help="scale every R by this")
    ap.add_argument("--slip", type=int, default=None, help="slippage ticks (default: lab's 1)")
    ap.add_argument("--contracts-cap", type=int, default=10)
    ap.add_argument("--json", default="trading/target.json")
    args = ap.parse_args()

    all_trades = []
    per_rule = {}
    print("=" * 96)
    print(f"  TARGET — ${args.equity:,.0f} -> ${args.equity * args.target:,.0f}  "
          f"(+{100 * (args.target - 1):.1f}%)   risk {100 * args.risk:.1f}%/trade")
    print("=" * 96)
    print(f"\n  {'symbol':9}{'rule':17}{'trades':>7}{'yrs':>6}{'R total':>9}{'$/trade':>9}{'min risk':>10}")

    for symbol, rule, params in WATCHLIST:
        try:
            trades = load(symbol, rule, params, slip_ticks=args.slip)
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
        r = run_account(trades, args.equity, args.risk, args.contracts_cap, args.haircut)
        solo[label] = r
        print(f"  {label:<26}{r['taken']:>7}{r['skipped']:>9}{r['final']:>11,.0f}"
              f"{r['max_dd']:>10,.0f}{r['min_dd_pct']:>7.1f}")

    # --- combined
    comb = run_account(all_trades, args.equity, args.risk, args.contracts_cap, args.haircut)
    print(f"  {'ALL THREE TOGETHER':<26}{comb['taken']:>7}{comb['skipped']:>9}"
          f"{comb['final']:>11,.0f}{comb['max_dd']:>10,.0f}{comb['min_dd_pct']:>7.1f}"
          f"{('  -10% x' + str(comb['breach'])) if comb['breach'] else ''}")

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
            trades = load(symbol, rule, p, slip_ticks=args.slip)
            line.append(f"{list(p.values())[0]}={sum(t['net'] for t in trades):+.1f}R")
        print(f"    {symbol:8}{rule:17} " + "   ".join(line))

    out = {"equity": args.equity, "risk": args.risk, "haircut": args.haircut,
           "combined": {k: v for k, v in comb.items() if k != "curve"},
           "solo": {k: {kk: vv for kk, vv in v.items() if kk != "curve"} for k, v in solo.items()},
           "months_to_target": sorted(tt)}
    Path(args.json).write_text(json.dumps(out, indent=2))
    print(f"\n  written: {args.json}")


if __name__ == "__main__":
    main()
