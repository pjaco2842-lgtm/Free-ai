#!/usr/bin/env python3
"""
Replay the trades ten thousand times before risking a dollar.

A backtest gives you one path through history. That path is a single sample, and
it is the sample that happened to occur. Resampling the *trade outcomes* answers
a different and more useful question: given this distribution of wins and losses,
how often does the account reach the goal before it breaches the limit?

    python3 trading/montecarlo.py --source backtest --paths 10000
    python3 trading/montecarlo.py --source ledger  --paths 10000
    python3 trading/montecarlo.py --source shadow

How the resampling is done, and why it matters
-----------------------------------------------
Trades are drawn in **blocks of three**, not one at a time. Losing streaks are
the thing that kills accounts, and independent draws destroy streaks by
construction — a naive bootstrap will always look kinder than reality. Block
resampling keeps short runs intact.

Costs are already inside every R in the ledger; the R-multiples are net. What is
*not* modelled is anything that makes a future trade different from a past one:
a new regime, a wider spread, a rule that quietly stopped working. A 40% pass
rate here is not a 40% chance of passing.

The Lucid consistency rule is applied as it actually is: a single day of profit
above half the target voids the pass even when the target is hit.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from account import ACCOUNT  # noqa: E402  (the firm's rulebook)
from basket import CONFIGS, HAIRCUT, contracts_for, trades_for  # noqa: E402
from lab import atr_series, ema, fetch_daily  # noqa: E402

DESK = HERE / "desk"
OUT = DESK / "montecarlo.json"

EQUITY = float(ACCOUNT["start_balance"])
TARGET = float(ACCOUNT["profit_target"])
MAX_LOSS = float(ACCOUNT["max_loss"])
CONSISTENCY = float(ACCOUNT["consistency"]["rule"])
BLOCK = 3


# ------------------------------------------------------------------- sources
def from_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("tradeable") is False:
            continue
        if row.get("contracts", 0) <= 0:
            continue
        out.append({"r": float(row.get("net_r", 0.0)),
                    "usd": float(row.get("usd", 0.0)),
                    "date": row.get("date", ""),
                    "symbol": row.get("symbol", "")})
    return out


def from_backtest(symbols: list[str] | None = None, honest: bool = False) -> list[dict]:
    """Every historical trade of the rules we actually trade, sized as the plan sizes.

    `honest` drops the one rule whose parameters were picked by looking at the
    whole sample (`ES inside_day`). Its trades are real, but its *selection* used
    the future, so including it in a probability is the same mistake in a
    different coat. What is left — the ES and CL fade rules, chosen on the first
    half and scored on the second — is the only set that has never seen the data
    it is being judged on.
    """
    out = []
    for symbol, configs in CONFIGS.items():
        if symbols and symbol not in symbols:
            continue
        try:
            bars = fetch_daily(symbol)
        except Exception:  # noqa: BLE001
            continue
        atr = atr_series(bars)
        emas = {k: ema([b.c for b in bars], k) for k in (20, 50, 200)}
        for cfg in configs:
            if not cfg["tradeable"]:
                continue
            if honest and cfg["rule"] == "inside_day":
                continue
            for t in trades_for(symbol, cfg, bars, atr, emas):
                n = contracts_for(t["risk_pts"], t["pv"], t["round_trip_cost_usd"])
                if n <= 0:
                    continue          # a signal the budget cannot size is not a trade
                out.append({"r": t["net"],
                            "usd": t["net"] * HAIRCUT * t["risk_pts"] * t["pv"] * n,
                            "date": t["date"], "symbol": symbol})
    out.sort(key=lambda r: r["date"])
    return out


# ------------------------------------------------------------------- replay
def replay(trades: list[dict], paths: int = 10_000, seed: int = 7,
           trades_per_path: int | None = None) -> dict:
    """Block-bootstrap the trade sequence. Returns the distribution, not a promise."""
    if len(trades) < 5:
        return {"error": f"only {len(trades)} trades — a replay of fewer than five "
                         "would be a random number with a chart", "paths": 0}
    rng = random.Random(seed)
    rs = [t["r"] for t in trades]
    usds = [t["usd"] for t in trades]
    n = len(rs)
    span = trades_per_path or 200
    mean_r = statistics.mean(rs)

    # A block draw is (average R, average USD) so the pair stays consistent.
    blocks = []
    for i in range(n):
        idx = [(i + k) % n for k in range(BLOCK)]
        blocks.append((statistics.mean(rs[j] for j in idx),
                       statistics.mean(usds[j] for j in idx)))

    hit_target = hit_loss = neither = 0
    trades_to_target: list[int] = []
    finals: list[float] = []
    max_dds: list[float] = []
    best_days: list[float] = []
    consistency_fails = 0

    for _ in range(paths):
        eq = peak = dd = best_day = 0.0
        done = False
        for t in range(span):
            _r_bar, usd_bar = blocks[rng.randrange(len(blocks))]
            eq += usd_bar
            best_day = max(best_day, usd_bar)
            peak = max(peak, eq)
            dd = max(dd, peak - eq)
            if eq >= TARGET:
                hit_target += 1
                trades_to_target.append(t + 1)
                if best_day > TARGET * CONSISTENCY:
                    consistency_fails += 1
                done = True
                break
            if eq <= -MAX_LOSS:
                hit_loss += 1
                done = True
                break
        if not done:
            neither += 1
        finals.append(eq)
        max_dds.append(dd)
        best_days.append(best_day)

    q = statistics.quantiles(finals, n=20) if len(finals) > 20 else [0.0]
    return {
        "paths": paths,
        "trades_in_sample": n,
        "trades_per_path": span,
        "block": BLOCK,
        "seed": seed,
        "mean_r": round(mean_r, 3),
        "p_target": round(100 * hit_target / paths, 2),
        "p_breach": round(100 * hit_loss / paths, 2),
        "p_neither": round(100 * neither / paths, 2),
        "consistency_fails": round(100 * consistency_fails / max(hit_target, 1), 1),
        "median_trades_to_target": (statistics.median(trades_to_target)
                                    if trades_to_target else None),
        "median_max_drawdown": round(statistics.median(max_dds), 0),
        "p95_max_drawdown": round(sorted(max_dds)[max(int(0.95 * len(max_dds)) - 1, 0)], 0),
        "final_usd_percentiles": {"p5": round(q[0]), "p50": round(q[9]),
                                  "p95": round(q[-1])},
        "median_best_day": round(statistics.median(best_days), 0),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=("backtest", "ledger", "shadow"), default="backtest")
    ap.add_argument("--since", default="2020-01-01",
                    help="only trades from this date onward (default: the holdout period)")
    ap.add_argument("--all", action="store_true",
                    help="include the pre-2020 trades used to CHOOSE the settings — hindsight")
    ap.add_argument("--honest", action="store_true",
                    help="drop the one rule that was selected using the whole sample")
    ap.add_argument("--paths", type=int, default=10_000)
    ap.add_argument("--span", type=int, default=200, help="trades per path")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.source == "ledger":
        trades = from_jsonl(DESK / "ledger.jsonl")
    elif args.source == "shadow":
        trades = from_jsonl(DESK / "shadow.jsonl")
    else:
        trades = from_backtest(honest=args.honest)

    hindsight = args.source == "backtest" and args.all
    if args.source == "backtest" and not args.all:
        # Default to the holdout window. A replay of the trades that were used to
        # pick the parameters is not a probability, it is a self-portrait: the
        # earlier version of this file returned a 99.8% pass rate from exactly
        # that mistake.
        trades = [t for t in trades if t.get("date", "") >= args.since]

    res = replay(trades, paths=args.paths, seed=args.seed, trades_per_path=args.span)
    if "error" in res:
        print(f"  {res['error']}")
        return

    res["source"] = args.source
    res["since"] = args.since if args.source == "backtest" and not hindsight else None
    res["hindsight"] = hindsight
    res["honest"] = bool(args.honest)
    res["at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    DESK.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2))

    if args.json:
        print(json.dumps(res, indent=2))
        return
    print("=" * 84)
    print(f"  MONTE CARLO — {res['paths']:,} replays of {res['trades_in_sample']} "
          f"historical trades ({res['source']}"
          f"{', ' + res['since'] + ' onward' if res.get('since') else ''})")
    print("=" * 84)
    if res.get("hindsight"):
        print("  WARNING: this window includes the trades the settings were chosen on.")
        print("  The pass rate below is a self-portrait, not a probability. Do not quote it.")
        print()
    print(f"  mean trade                        {res['mean_r']:+.3f}R")
    print(f"  reaches +${TARGET:,.0f} before -${MAX_LOSS:,.0f}   {res['p_target']:.1f}%")
    print(f"  breaches -${MAX_LOSS:,.0f} first            {res['p_breach']:.1f}%")
    print(f"  neither inside {res['trades_per_path']} trades     {res['p_neither']:.1f}%")
    print(f"  median trades to the target       {res['median_trades_to_target']}")
    print(f"  median worst drawdown             ${res['median_max_drawdown']:,.0f}")
    print(f"  drawdown you should plan for (95%)${res['p95_max_drawdown']:,.0f}")
    print(f"  final equity, 5th / 50th / 95th   ${res['final_usd_percentiles']['p5']:,.0f} / "
          f"${res['final_usd_percentiles']['p50']:,.0f} / "
          f"${res['final_usd_percentiles']['p95']:,.0f}")
    if res["p_target"]:
        print(f"  of the passes, {res['consistency_fails']:.0f}% would still fail the "
              f"{int(100 * CONSISTENCY)}% consistency rule")
    print()
    print(f"  written to {OUT}")


if __name__ == "__main__":
    main()
