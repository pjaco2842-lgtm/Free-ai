#!/usr/bin/env python3
"""
Which stop size, for which stage?

The account has two stages with different rules, and that changes the right answer:

  evaluation  +$1,250 to pass, largest day ≤ 40-50% of total profit, $1,000 end-of-day
              drawdown. Consistency punishes one big day, so the stop has to be small
              enough that a good day is not most of the profit.
  funded      no consistency rule, and the cushion grows with profit: at $26,000 there is
              $2,000 of room instead of $1,000, at $27,000 there is $3,000. Risk can scale
              with the cushion, and the rule with the best expectancy per trade wins.

So the question is not "which rule" but "which stop, when". This measures the same rules at
stop multiples from 0.2 to 1.5 ATR.
"""

from __future__ import annotations

import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lab26k import MARKETS, day_trade, prep, spec_legs, spec_mask  # noqa: E402

DESK = Path(__file__).resolve().parent / "desk"
OUT = DESK / "buffer-test.md"
BUFFER = 1000.0
CONSISTENCY = 40.0

RULES = [("nr_break", 2), ("nday_break", 1), ("nday_fade", 5)]
STOPS = [0.2, 0.25, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5]
EXITS = ["tp1", "tp2"]


def windows(D: dict) -> dict[str, np.ndarray]:
    y = D["years"]
    n = len(D["c"])
    last40 = np.zeros(n, bool)
    last40[max(0, n - 40):] = True
    return {"last 40 sessions": last40,
            "test 2020-24": (y > 2019) & (y <= 2024),
            "recent 2025+": y > 2024}


def run_window(D: dict, spec: dict, legs, sel: np.ndarray) -> dict:
    pv, tick = MARKETS[D["symbol"]][1], MARKETS[D["symbol"]][2]
    trades = []
    for i in np.where(sel)[0]:
        t = day_trade(D, int(i), spec, legs, pv, tick)
        if t:
            trades.append((t["usd"], t["why"], t["risk"]))
    if not trades:
        return {"n": 0}
    usd = [x[0] for x in trades]
    eq = peak = dd = 0.0
    for u in usd:
        eq += u
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    net = sum(usd)
    return {"n": len(trades), "win": 100 * sum(1 for u in usd if u > 0) / len(usd),
            "net": net, "dd": dd, "stops": sum(1 for x in trades if x[1] == "stop"),
            "max_day": max(usd), "worst_day": min(usd),
            "consistency": (100 * max(usd) / net) if net > 0 else None,
            "risk": statistics.median(x[2] for x in trades)}


def main() -> None:
    D = prep("NQ=F")
    pv = MARKETS["NQ=F"][1]
    atr_now = float(D["atr"][-1])
    atr_med = float(np.nanmedian(D["atr_prev"][-252:]))
    wins = windows(D)

    rows = []
    for fam, n in RULES:
        legs = spec_legs(D, {"family": fam, "n": n})
        for stop in STOPS:
            for ex in EXITS:
                spec = {"family": fam, "n": n, "stop": stop, "exit": ex,
                        "gap": "any", "trend": False, "dow": "all", "dir": "both"}
                mask = spec_mask(D, spec)
                for wname, sel in wins.items():
                    st = run_window(D, spec, legs, mask & sel)
                    if st["n"]:
                        rows.append({"family": fam, "n": n, "stop": stop, "exit": ex,
                                     "window": wname, **st})

    print("=" * 116)
    print(f"  STOP SIZE TEST — NQ one micro · ATR now {atr_now:,.0f} pts "
          f"(${atr_now * pv:,.0f} per ATR) · median last 252 {atr_med:,.0f} pts "
          f"(${atr_med * pv:,.0f})")
    print("=" * 116)

    eval_rows = [r for r in rows if r["window"] == "last 40 sessions"]
    eval_rows.sort(key=lambda r: ((r["consistency"] or 999), -r["net"]))
    print("\n  EVALUATION — last 40 sessions (DD < $1,000, biggest day < 40% of profit)")
    print(f"  {'rule':16}{'stop':>6}{'exit':>6}{'n':>4}{'win':>6}{'net $':>9}{'DD $':>8}"
          f"{'stops':>7}{'maxday':>8}{'cons':>7}{'risk':>8}{'buffer holds':>13}")
    for r in eval_rows:
        cons = "—" if r["consistency"] is None else f"{r['consistency']:.0f}%"
        print(f"  {r['family'] + '-' + str(r['n']):16}{r['stop']:>6}{r['exit']:>6}{r['n']:>4}"
              f"{r['win']:>5.0f}%{r['net']:>9,.0f}{r['dd']:>8,.0f}{r['stops']:>7}"
              f"{r['max_day']:>8,.0f}{cons:>7}{r['risk']:>8,.0f}"
              f"{BUFFER / r['risk']:>10.1f} stops")

    print("\n  LONG SAMPLE 2020-2024 (unseen) — edge per trade by stop size")
    print(f"  {'rule':16}{'stop':>6}{'exit':>6}{'n':>6}{'win':>6}{'net $':>10}{'DD $':>9}"
          f"{'stops':>7}{'$/trade':>10}{'cons':>7}")
    for r in sorted([x for x in rows if x["window"] == "test 2020-24"],
                    key=lambda r: (r["family"], r["stop"], r["exit"])):
        cons = "—" if r["consistency"] is None else f"{r['consistency']:.0f}%"
        print(f"  {r['family'] + '-' + str(r['n']):16}{r['stop']:>6}{r['exit']:>6}{r['n']:>6}"
              f"{r['win']:>5.0f}%{r['net']:>10,.0f}{r['dd']:>9,.0f}{r['stops']:>7}"
              f"{r['net'] / r['n']:>10,.0f}{cons:>7}")

    lines = ["# Stop size by stage", "",
             f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')} · NQ one micro · "
             f"ATR now {atr_now:,.0f} pts (${atr_now * pv:,.0f} per ATR), "
             f"median last 252 {atr_med:,.0f} pts", "",
             "The evaluation has a 40% consistency rule and a $1,000 buffer. The funded stage has",
             "neither: no consistency rule, and the cushion grows with profit ($26k = $2,000 of",
             "room, $27k = $3,000). The stop is therefore a stage decision, not one number.", "",
             "## Evaluation, last 40 sessions", "",
             "| rule | stop | exit | trades | win | net $ | DD $ | stops hit | biggest day | consistency | risk/stop | buffer holds |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in eval_rows:
        cons = "—" if r["consistency"] is None else f"{r['consistency']:.0f}%"
        lines.append(f"| {r['family']}-{r['n']} | {r['stop']}A | {r['exit']} | {r['n']} "
                     f"| {r['win']:.0f}% | ${r['net']:+,.0f} | ${r['dd']:,.0f} | {r['stops']} "
                     f"| ${r['max_day']:+,.0f} | {cons} | ${r['risk']:,.0f} "
                     f"| {BUFFER / r['risk']:.1f} |")

    lines += ["", "## Long sample, 2020-2024 (unseen years)", "",
              "| rule | stop | exit | trades | win | net $ | DD $ | stops hit | $/trade | consistency |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted([x for x in rows if x["window"] == "test 2020-24"],
                    key=lambda r: (r["family"], r["stop"], r["exit"])):
        cons = "—" if r["consistency"] is None else f"{r['consistency']:.0f}%"
        lines.append(f"| {r['family']}-{r['n']} | {r['stop']}A | {r['exit']} | {r['n']} "
                     f"| {r['win']:.0f}% | ${r['net']:+,.0f} | ${r['dd']:,.0f} | {r['stops']} "
                     f"| ${r['net'] / r['n']:+,.0f} | {cons} |")
    lines += ["", "`stops hit` is the column that matters. A small drawdown in a window where no",
              "stop was hit says nothing about the next window, and one stop breaches the buffer",
              "whenever the stop is larger than the buffer itself.", ""]
    OUT.write_text("\n".join(lines))
    print(f"\n  written to {OUT}")


if __name__ == "__main__":
    main()
