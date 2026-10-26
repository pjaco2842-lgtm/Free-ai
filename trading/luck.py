#!/usr/bin/env python3
"""
The coin-flip test: does the strategy beat the same rules with random entries?

This is the check that kills most "edges". It keeps the stop, the target, the
holding limit and the trade frequency, and throws away only the one thing the
strategy claims to add — WHEN it enters. If random timing makes the same money,
the signal is decoration.

    python3 trading/luck.py --symbol NQ=F --start 2020-01-01 \
        --struct 30 --band 5 --sl-atr 1 --tp-r 2 --runs 500

Verdict lines:
    percentile  the share of random runs the real strategy beat
    p-value     share of random runs that matched or beat it
                 (0.05 = "one in twenty random runs did this")
    BEATS LUCK  p-value under 0.05 with a positive total
    NO EDGE     everything else — including a positive result that random
                timing matches just as easily
"""

from __future__ import annotations

import argparse
import random
import statistics
from datetime import datetime, timezone

from research import fetch_daily
from scanner import Bar, DEFAULTS, series, signals


def walk(bars: list[Bar], entry_flags: list[bool], side_long: list[bool],
         sl_atr: float, tp_r: float | None, max_hold: int, atr: list) -> list[float]:
    """Run one pass. One position at a time, entry next open, stop first."""
    results: list[float] = []
    i = 1
    while i < len(bars) - 1:
        if not entry_flags[i] or not atr[i]:
            i += 1
            continue
        risk = atr[i] * sl_atr
        entry = bars[i + 1].o
        long = side_long[i]
        stop = entry - risk if long else entry + risk
        target = None if tp_r is None else (entry + risk * tp_r if long else entry - risk * tp_r)

        outcome = None
        j = i + 1
        while j < len(bars) and j <= i + max_hold:
            if long:
                hit_stop = bars[j].l <= stop
                hit_target = target is not None and bars[j].h >= target
            else:
                hit_stop = bars[j].h >= stop
                hit_target = target is not None and bars[j].l <= target
            if hit_stop:
                outcome = -1.0
            elif hit_target:
                outcome = tp_r
            if outcome is not None:
                break
            j += 1
        if outcome is None:
            last = bars[min(j, len(bars) - 1)].c
            outcome = ((last - entry) if long else (entry - last)) / risk
        results.append(outcome)
        i = j + 1
    return results


def epoch(value: str) -> int:
    return int(datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def main() -> None:
    ap = argparse.ArgumentParser(description="Coin-flip test with identical risk rules.")
    ap.add_argument("--symbol", default="NQ=F")
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--struct", type=int, default=30)
    ap.add_argument("--band", type=float, default=5.0)
    ap.add_argument("--sl-atr", type=float, default=1.0)
    ap.add_argument("--tp-r", type=float, default=2.0, help="target in R; 0 means hold, no target")
    ap.add_argument("--max-hold", type=int, default=20)
    ap.add_argument("--runs", type=int, default=500)
    args = ap.parse_args()

    bars = fetch_daily(args.symbol, epoch(args.start), epoch(args.end))
    if len(bars) < 300:
        raise SystemExit(f"only {len(bars)} bars in that window")

    p = {**DEFAULTS, "struct": args.struct, "band": args.band}
    s = series(bars, p)
    longs, shorts = signals(s, p)
    tp = None if args.tp_r <= 0 else args.tp_r

    real_entries = [bool(longs[i] or shorts[i]) for i in range(len(bars))]
    real_sides = [bool(longs[i]) for i in range(len(bars))]
    eligible = sum(1 for i in range(1, len(bars) - 1) if s["atr"][i])
    real = walk(bars, real_entries, real_sides, args.sl_atr, tp, args.max_hold, s["atr"])
    if not real:
        raise SystemExit("the strategy took no trades in this window")

    real_total = sum(real)
    density = len(real) / max(eligible, 1)
    print(f"{args.symbol} · {args.start} → {args.end} · {len(bars)} daily bars")
    print(f"strategy: {len(real)} trades · total {real_total:+.1f}R · "
          f"avg {real_total / len(real):+.2f}R · win rate "
          f"{sum(1 for r in real if r > 0) / len(real) * 100:.0f}%")
    print(f"entry density {density:.3f} per bar · stop {args.sl_atr} ATR · "
          f"target {'none (hold)' if tp is None else f'{tp}R'} · max hold {args.max_hold} bars")
    print(f"\nrunning {args.runs} random-entry versions with the same rules…")

    rng = random.Random(1234)  # fixed seed so anyone can reproduce this
    totals: list[float] = []
    for _ in range(args.runs):
        flags, sides = [], []
        for i in range(len(bars)):
            fire = i > 1 and rng.random() < density
            flags.append(fire)
            sides.append(rng.random() < 0.5)
        totals.append(sum(walk(bars, flags, sides, args.sl_atr, tp, args.max_hold, s["atr"])))

    beaten = sum(1 for t in totals if t >= real_total)
    p_value = beaten / len(totals)
    percentile = 100 * (1 - p_value)
    print(f"random runs: mean {statistics.mean(totals):+.1f}R · median {statistics.median(totals):+.1f}R "
          f"· best {max(totals):+.1f}R · worst {min(totals):+.1f}R")
    print(f"percentile {percentile:.0f} (the strategy beat {percentile:.0f}% of random runs)")
    print(f"p-value {p_value:.3f} ({beaten}/{args.runs} random runs matched or beat it)")

    if p_value < 0.05 and real_total > 0:
        print("\nVERDICT: BEATS LUCK — worth more testing, still not a promise.")
    elif real_total > 0:
        print("\nVERDICT: NO EDGE — profitable, but random entries did it just as often.")
    else:
        print("\nVERDICT: NO EDGE — and it loses money. Drop it.")


if __name__ == "__main__":
    main()
