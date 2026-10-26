#!/usr/bin/env python3
"""
Test the "open breakout, hold to the close, no target" family.

Why this shape
--------------
A widely shared result (the two videos in this repo's history) claims three things
about the Nasdaq specifically:

  1. Get in on a breakout early in the day, tight stop, hold to the close, NO target.
     Every take-profit they added made the statistics worse.
  2. When the market opens above yesterday's close, breakouts in that same
     direction work better.
  3. After a huge trend day, breakouts in the SAME direction were worth nothing,
     and breakouts in the OPPOSITE direction were the strongest.

This script tests those three claims on daily bars, 2010-2026, with the same
honesty rules as research.py: decide on 2010-2020, open the 2020-2026 door once.

Why daily bars and what that costs
----------------------------------
Free intraday history is capped at about 60 days, which cannot answer a 16-year
question. Daily OHLC lets us approximate the idea: enter at the open, stop 1 ATR
away, exit at the close, no target. What it cannot see is the intraday path — a
day that opened above yesterday's high might have traded through the open, stopped
out, and still closed higher. The stop is assumed to fill before the close when the
low crosses it, which is the pessimistic assumption, so results lean conservative.

    python3 trading/breakout.py
    python3 trading/breakout.py --symbol NQ=F --stop-atr 1.0
    python3 trading/breakout.py --symbol ES=F --stop-atr 1.5

Costs: commission and one tick of slippage per side are charged, and reported both
gross and net, in R.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scanner import Bar  # noqa: E402

UA = {"User-Agent": "research-script/1.0 (local backtest)"}
IS_END = "2020-01-01"

# symbol -> (name, micro contract $ per point, tick size)
# Costs are charged on the MICRO contract, because that is what a 25k account trades.
# Charging MNQ numbers against CL (1000 barrels/point) turns a 0.05R cost into 1.5R,
# which is how a cost model silently invents a disaster. Keep these separate.
MARKETS = {
    "NQ=F": ("Nasdaq-100", 2.0, 0.25),      # MNQ
    "ES=F": ("S&P 500", 5.0, 0.25),         # MES
    "GC=F": ("Gold", 10.0, 0.10),           # MGC
    "CL=F": ("Crude oil", 100.0, 0.01),     # MCL
    "RTY=F": ("Russell 2000", 5.0, 0.10),   # M2K
}

COMMISSION_PER_SIDE = 1.24      # typical retail all-in per micro contract side
SLIP_TICKS = 1                  # one tick against you on entry and exit


def fetch_daily(symbol: str, start: int, end: int) -> list[Bar]:
    query = urllib.parse.urlencode({"period1": start, "period2": end, "interval": "1d"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?{query}"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode())
    result = data["chart"]["result"][0]
    stamps, quote = result["timestamp"], result["indicators"]["quote"][0]
    bars = []
    for i, t in enumerate(stamps):
        o, h, l, c = quote["open"][i], quote["high"][i], quote["low"][i], quote["close"][i]
        if None in (o, h, l, c):
            continue
        bars.append(Bar(int(t), float(o), float(h), float(l), float(c), float(quote["volume"][i] or 0)))
    return bars


def atr_series(bars: list[Bar], n: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(bars)
    trs: list[float] = []
    for i, b in enumerate(bars):
        if i == 0:
            trs.append(b.h - b.l)
            continue
        prev = bars[i - 1].c
        trs.append(max(b.h - b.l, abs(b.h - prev), abs(b.l - prev)))
        if i >= n:
            out[i] = sum(trs[i - n + 1:i + 1]) / n
    return out


def trades_for(bars: list[Bar], atr: list[float | None], pick, stop_atr: float,
               point_value: float, tick: float) -> list[dict]:
    """Run one position at a time. `pick(i)` returns 'long', 'short' or None."""
    cost_usd = 2 * (COMMISSION_PER_SIDE + SLIP_TICKS * tick * point_value)
    out = []
    busy_until = -1
    for i in range(2, len(bars)):
        if i <= busy_until:
            continue
        side = pick(i)
        if side is None:
            continue
        a = atr[i - 1]
        if not a:
            continue
        bar = bars[i]
        entry = bar.o
        risk = stop_atr * a
        if risk <= 0:
            continue
        if side == "long":
            stop = entry - risk
            stopped = bar.l <= stop
            exit_px = stop if stopped else bar.c
            r = (exit_px - entry) / risk
        else:
            stop = entry + risk
            stopped = bar.h >= stop
            exit_px = stop if stopped else bar.c
            r = (entry - exit_px) / risk
        cost_r = cost_usd / (risk * point_value)
        out.append({
            "i": i, "side": side, "r": r, "net": r - cost_r,
            "stopped": stopped, "date": datetime.fromtimestamp(bar.t, timezone.utc).strftime("%Y-%m-%d"),
        })
        busy_until = i  # one trade per day, exit same day
    return out


def stats(rows: list[dict]) -> dict:
    if not rows:
        return {"trades": 0}
    gross = [r["r"] for r in rows]
    net = [r["net"] for r in rows]
    return {
        "trades": len(rows),
        "win_rate": round(100 * sum(1 for r in net if r > 0) / len(rows), 1),
        "total_r": round(sum(gross), 2),
        "net_r": round(sum(net), 2),
        "avg_r": round(sum(net) / len(rows), 3),
        "stops": round(100 * sum(1 for r in rows if r["stopped"]) / len(rows), 1),
    }


def split(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    is_rows = [r for r in rows if r["date"] < IS_END]
    oos_rows = [r for r in rows if r["date"] >= IS_END]
    return is_rows, oos_rows


def build_rules(bars, atr):
    """Every rule decides from the PREVIOUS bar only — nothing from the future."""
    def prev(i, k=1):
        return bars[i - k]

    def open_break(i):
        p = prev(i)
        if bars[i].o > p.h:
            return "long"
        if bars[i].o < p.l:
            return "short"
        return None

    # Deliberately no "gap-aligned" variant: opening above yesterday's high already
    # implies opening above yesterday's close, so that filter never changes a single
    # trade. Adding it would report the same trades twice and look like two results.
    def trend_day_fade(i):
        p, p2 = prev(i), prev(i, 2)
        a = atr[i - 1]
        if not a or (p.h - p.l) <= 1.5 * a:
            return None
        up_day = p.c > p2.c
        if bars[i].o > p.h and up_day:          # breakout in BOTH directions: fade it
            return "short"
        if bars[i].o < p.l and not up_day:
            return "long"
        return None

    def trend_day_continue(i):
        p, p2 = prev(i), prev(i, 2)
        a = atr[i - 1]
        if not a or (p.h - p.l) <= 1.5 * a:
            return None
        up_day = p.c > p2.c
        if bars[i].o > p.h and up_day:
            return "long"
        if bars[i].o < p.l and not up_day:
            return "short"
        return None

    return {
        "open_break": open_break,
        "trend_day_fade": trend_day_fade,
        "trend_day_continue": trend_day_continue,
    }


def random_baseline(bars, atr, rows: list[dict], stop_atr: float, runs: int = 300,
                    point_value: float = 2.0, tick: float = 0.25) -> dict:
    """Same count, same stop, same hold-to-close — random days and sides.

    If random days do as well, the breakout timing added nothing.
    """
    n = len(rows)
    if n < 5:
        return {}
    pool = [r for r in rows if r["net"] > -99]
    real_net = sum(r["net"] for r in pool)
    usable = [i for i in range(2, len(bars)) if atr[i - 1]]
    cost_usd = 2 * (COMMISSION_PER_SIDE + SLIP_TICKS * tick * point_value)
    better = 0
    totals = []
    for _ in range(runs):
        picks = random.sample(usable, min(n, len(usable)))
        total = 0.0
        for i in picks:
            a = atr[i - 1]
            risk = stop_atr * a
            if risk <= 0:
                continue
            bar = bars[i]
            side = random.choice(("long", "short"))
            entry = bar.o
            if side == "long":
                r = (bar.c - entry) / risk if bar.l > entry - risk else -1.0
            else:
                r = (entry - bar.c) / risk if bar.h < entry + risk else -1.0
            total += r - cost_usd / (risk * point_value)
        totals.append(total)
        if total >= real_net:
            better += 1
    return {
        "p_value": round(better / runs, 3),
        "random_median": round(statistics.median(totals), 2),
        "percentile": round(100 * (1 - better / runs), 0),
    }


def run_market(symbol: str, spec: tuple[str, float, float], stop_atr: float, runs: int) -> dict:
    name, point_value, tick = spec
    start = int(datetime(2010, 1, 1, tzinfo=timezone.utc).timestamp())
    end = int(datetime.now(timezone.utc).timestamp())
    bars = fetch_daily(symbol, start, end)
    if len(bars) < 500:
        raise SystemExit(f"{symbol}: only {len(bars)} daily bars")
    atr = atr_series(bars)
    rules = build_rules(bars, atr)
    row = {"symbol": symbol, "name": name, "bars": len(bars), "stop_atr": stop_atr,
           "point_value": point_value, "tick": tick, "rules": {}}

    for rule_name, pick in rules.items():
        rows = trades_for(bars, atr, pick, stop_atr, point_value, tick)
        is_rows, oos_rows = split(rows)
        entry = {"all": stats(rows), "in_sample": stats(is_rows), "out_of_sample": stats(oos_rows)}
        if oos_rows:
            entry["coin_flip"] = random_baseline(bars, atr, oos_rows, stop_atr, runs,
                                                 point_value, tick)
        row["rules"][rule_name] = entry
    return row


def print_market(row: dict) -> None:
    print(f"\n{row['symbol']}  {row['name']}  · {row['bars']} daily bars · stop {row['stop_atr']} ATR · hold to close · no target")
    print(f"  {'rule':<24}{'trades':>7}{'win%':>7}{'gross R':>9}{'net R':>8}{'avg R':>7}{'stopped%':>9}")
    for rule, data in row["rules"].items():
        for label, key in (("IS 2010-2020", "in_sample"), ("OOS 2020-2026", "out_of_sample")):
            s = data[key]
            if not s.get("trades"):
                print(f"  {rule + ' ' + label:<24}{'—':>7}")
                continue
            print(f"  {rule + ' ' + label:<24}{s['trades']:>7}{s['win_rate']:>7.1f}"
                  f"{s['total_r']:>9.2f}{s['net_r']:>8.2f}{s['avg_r']:>7.3f}{s['stops']:>9.1f}")
        cf = data.get("coin_flip")
        if cf:
            print(f"  {'  coin flip (OOS)':<24}{'':>7}{'':>7}{'':>9}{'p=' + str(cf['p_value']):>8}"
                  f"{'pct ' + str(int(cf['percentile'])):>14}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Open-breakout / hold-to-close test.")
    ap.add_argument("--symbol", default="NQ=F")
    ap.add_argument("--stop-atr", type=float, default=1.0)
    ap.add_argument("--runs", type=int, default=300)
    ap.add_argument("--all-markets", action="store_true")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    if args.all_markets:
        symbols = MARKETS
    else:
        symbols = {args.symbol: MARKETS.get(args.symbol, (args.symbol, 2.0, 0.25))}
    rows = []
    for symbol, spec in symbols.items():
        rows.append(run_market(symbol, spec, args.stop_atr, args.runs))

    print("=" * 96)
    print("  Open breakout, hold to the close, no take-profit. Costs included.")
    print("  Rule chosen on 2010-2020; 2020-2026 is data the rule never saw.")
    print("=" * 96)
    for row in rows:
        print_market(row)

    if args.json:
        Path(args.json).write_text(json.dumps({"generated": datetime.now(timezone.utc).isoformat(),
                                               "stop_atr": args.stop_atr, "rows": rows}, indent=1))
        print(f"\nwritten: {args.json}")

    print("\nReading it: `gross R` ignores costs, `net R` is what you would keep.")
    print("A rule only counts if BOTH windows are positive and the coin flip says p<0.05.")


if __name__ == "__main__":
    main()
