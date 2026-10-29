#!/usr/bin/env python3
"""
The aggressive experiment: how fast can this actually trade, and what does it cost?

Why this file is separate
-------------------------
`desk.py` is deliberately slow: five markets, seven gates, a setup has to score
45/100, and it fires about once a month. That is the right shape for a $1,000
drawdown, and it is a terrible shape if you want to know how a high-frequency
version behaves.

So this is the opposite end of the same question, measured rather than asserted:

  * no gate chain at all — every EMA cross is taken, in both directions
  * the fastest timeframes free data actually offers
  * realistic costs on every single trade: commission per side plus one tick of
    slippage per side, because a scalper pays those hundreds of times a day and
    they are the entire story

What it is NOT
--------------
It is not a live trader, it is not wired into the desk, and it does not place
orders. It answers one question: if we loosened everything and traded every
signal, what would the paper record look like?

The honest limits, stated before the numbers
--------------------------------------------
1. **No seconds data exists for free.** Yahoo serves 1-minute bars for about
   seven days, 5-minute for a month, 15-minute for sixty days. A 5s/10s/15s test
   is not possible with this data source, so 1m is the floor here. Anything
   claiming to backtest seconds on free data is inventing the bars.

2. **The samples are short.** A 1-minute test covers about five sessions. That is
   enough to measure the *cost drag* precisely and nowhere near enough to prove
   an edge. The code therefore chooses parameters on the first half and reports
   the second half, so a lucky fit cannot be quoted as a result.

3. **The desk's own rules do not transfer.** Those were chosen on daily bars and
   validated on a decade. Intraday is a different animal with different noise.

    python3 trading/scalp.py                 # full sweep, all five markets
    python3 trading/scalp.py --tf 5m,15m     # one or two timeframes
    python3 trading/scalp.py --symbols ES=F  # one market
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lab import COMMISSION, COMMS, atr_series, ema  # noqa: E402
from scanner import Bar, fetch_yahoo  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "desk" / "scalp.md"
RAW = HERE / "desk" / "scalp.json"

# symbol: (micro contract, $ per point, tick size)
MARKETS = {
    "ES=F": ("MES", 5.0, 0.25),
    "NQ=F": ("MNQ", 2.0, 0.25),
    "GC=F": ("MGC", 10.0, 0.10),
    "CL=F": ("MCL", 100.0, 0.01),
    "NKD=F": ("NKD", 5.0, 5.0),
}

# interval: how much history Yahoo will actually give us
SPANS = {"1m": "7d", "5m": "1mo", "15m": "60d"}

# (fast, slow) x (stop ATR, target ATR) x max hold in bars
GRID = [
    {"fast": f, "slow": s, "stop": st, "target": tg, "hold": h}
    for f, s in ((5, 15), (8, 21), (13, 34))
    for st, tg in ((0.5, 1.0), (0.5, 1.5), (1.0, 2.0))
    for h in (6, 20)
]

CONTRACTS = 1          # one micro: the size a $25k account can actually carry
SLIP_TICKS = 1         # one tick against you on entry AND on exit


def day(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def load(symbol: str, tf: str) -> list[Bar]:
    bars = fetch_yahoo(symbol, tf, SPANS[tf])
    # Yahoo repeats the forming candle; a bar that has not closed cannot be traded.
    return bars[:-1] if bars else bars


def backtest(bars: list[Bar], pv: float, tick: float, comm: float, cfg: dict,
             order: str = "stop_first") -> list[dict]:
    """Every EMA cross, in both directions, with costs.

    When one bar contains both the stop and the target, the bar cannot tell you
    which came first. `order` decides, and both answers are reported: "stop_first"
    is the pessimistic bound, "target_first" the optimistic one. The truth is
    inside the bracket, and a result that is only positive under one of them is
    not a result.
    """
    closes = [b.c for b in bars]
    atr = atr_series(bars)
    ef, es = ema(closes, cfg["fast"]), ema(closes, cfg["slow"])
    slip = tick * pv
    cost = 2 * (COMMS.get("ES=F", COMMISSION) + slip)   # round trip, per contract
    out: list[dict] = []
    pos = None

    for i in range(2, len(bars)):
        b = bars[i]

        if pos:
            if pos["side"] > 0:
                at_stop, at_tgt = b.l <= pos["stop"], b.h >= pos["target"]
            else:
                at_stop, at_tgt = b.h >= pos["stop"], b.l <= pos["target"]
            hit = None
            if at_stop and at_tgt:                       # ambiguous bar
                hit = (("stop", pos["stop"]) if order == "stop_first"
                       else ("target", pos["target"]))
            elif at_stop:
                hit = ("stop", pos["stop"])
            elif at_tgt:
                hit = ("target", pos["target"])
            if hit is None and i - pos["i"] >= cfg["hold"]:
                hit = ("time", b.c)
            if hit is not None:
                why, px = hit
                gross = (px - pos["entry"]) * pos["side"] * pv
                net = gross - cost
                risk_usd = abs(pos["entry"] - pos["stop"]) * pv
                out.append({"date": day(b.t), "side": "long" if pos["side"] > 0 else "short",
                            "entry": pos["entry"], "exit": px, "why": why,
                            "bars": i - pos["i"], "usd": round(net, 2),
                            "r": round(net / risk_usd, 3) if risk_usd else 0.0})
                pos = None

        if pos is None and i - 1 >= 1 and atr[i - 1]:
            a, f0, s0, f1, s1 = atr[i - 1], ef[i - 2], es[i - 2], ef[i - 1], es[i - 1]
            if None in (f0, s0, f1, s1):
                continue
            side = 0
            if f0 <= s0 and f1 > s1:
                side = 1
            elif f0 >= s0 and f1 < s1:
                side = -1
            if side:
                stop_px = a * cfg["stop"]
                tgt_px = a * cfg["target"]
                entry = b.o
                pos = {"side": side, "entry": entry, "i": i,
                       "stop": entry - side * stop_px, "target": entry + side * tgt_px}
    return out


def summarise(trades: list[dict], sessions: int) -> dict:
    if not trades:
        return {"trades": 0}
    rs = [t["r"] for t in trades]
    usd = [t["usd"] for t in trades]
    wins = sum(1 for t in trades if t["usd"] > 0)
    eq = peak = dd = 0.0
    for u in usd:
        eq += u
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    streak = worst = 0
    for t in trades:
        streak = streak + 1 if t["usd"] <= 0 else 0
        worst = max(worst, streak)
    return {"trades": len(trades), "per_day": len(trades) / max(sessions, 1),
            "win": 100 * wins / len(trades), "avg_r": statistics.mean(rs),
            "total_r": sum(rs), "usd": sum(usd), "avg_usd": statistics.mean(usd),
            "dd": dd, "streak": worst,
            "days": len({t["date"] for t in trades})}


def pick(train: list[dict], minimum: int = 10) -> dict | None:
    usable = [c for c in train if c["test"]["trades"] >= 0 and c["train"]["trades"] >= minimum]
    if not usable:
        return None
    return max(usable, key=lambda c: c["train"]["total_r"])


def sweep(symbol: str, tf: str) -> dict | None:
    name, pv, tick = MARKETS[symbol]
    bars = load(symbol, tf)
    if len(bars) < 200:
        return None
    cut = len(bars) // 2
    half_a, half_b = bars[:cut], bars[cut:]
    sess_a = len({day(b.t) for b in half_a})
    sess_b = len({day(b.t) for b in half_b})
    sess_all = len({day(b.t) for b in bars})

    rows = []
    for cfg in GRID:
        a = summarise(backtest(half_a, pv, tick, COMMISSION, cfg), sess_a)
        b = summarise(backtest(half_b, pv, tick, COMMISSION, cfg), sess_b)
        c = summarise(backtest(bars, pv, tick, COMMISSION, cfg), sess_all)
        rows.append({"cfg": cfg, "train": a, "test": b, "all": c})

    winner = pick(rows)
    if winner is None:
        return None
    cfg = winner["cfg"]
    # The same chosen settings, scored the other way on every ambiguous bar.
    best_test = summarise(backtest(half_b, pv, tick, COMMISSION, cfg, "target_first"), sess_b)
    return {"symbol": symbol, "contract": name, "tf": tf, "bars": len(bars),
            "sessions": sess_all, "chosen": cfg,
            "train": winner["train"], "test": winner["test"], "all": winner["all"],
            "test_best": best_test,
            "grid_best_test_r": max(r["test"]["total_r"] for r in rows if r["test"]["trades"])}


def fmt(row: dict, key: str) -> str:
    s = row[key]
    if not s.get("trades"):
        return "        —"
    return (f"{s['trades']:4d} {s['per_day']:6.1f} {s['win']:5.1f}% {s['avg_r']:+6.2f} "
            f"{s['usd']:+8,.0f} {s['dd']:8,.0f} {s['streak']:5d}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="1m,5m,15m")
    ap.add_argument("--symbols", default=",".join(MARKETS))
    args = ap.parse_args()
    tfs = [t.strip() for t in args.tf.split(",") if t.strip()]
    syms = [s.strip() for s in args.symbols.split(",") if s.strip()]

    print("=" * 104)
    print("  SCALP EXPERIMENT — every EMA cross, both directions, no gate chain, costs on every trade")
    print(f"  one micro contract · commission ${COMMISSION:.2f}/side + {SLIP_TICKS} tick slippage/side")
    print("=" * 104)

    results = []
    for tf in tfs:
        for sym in syms:
            try:
                r = sweep(sym, tf)
            except Exception as err:  # noqa: BLE001
                print(f"  {sym:7} {tf:4} data unavailable: {err}")
                continue
            if not r:
                print(f"  {sym:7} {tf:4} not enough bars")
                continue
            results.append(r)
            print(f"\n  {sym:7} {r['contract']:5} {tf:4}  {r['bars']:5} bars  {r['sessions']:3} sessions"
                  f"  chosen {r['chosen']['fast']}/{r['chosen']['slow']}"
                  f" stop {r['chosen']['stop']}A target {r['chosen']['target']}A hold {r['chosen']['hold']}b")
            print(f"    {'':9} {'trades':>5} {'/day':>6} {'win':>7} {'avg R':>7} {'net $':>9} {'maxDD':>8} {'lostrek':>6}")
            print(f"    {'first half':9} {fmt(r, 'train')}")
            print(f"    {'second half':9} {fmt(r, 'test')}")
            print(f"    {'2nd, best case':9} {fmt(r, 'test_best')}")
            print(f"    {'full sample':9} {fmt(r, 'all')}")

    if not results:
        print("\n  nothing ran")
        return

    # The portfolio question: if all five traded this way at once, what would the day look like?
    test_usd = sum(r["test"].get("usd", 0) for r in results)
    best_usd = sum(r["test_best"].get("usd", 0) for r in results)
    test_trades = sum(r["test"].get("trades", 0) for r in results)
    all_usd = sum(r["all"].get("usd", 0) for r in results)
    all_trades = sum(r["all"].get("trades", 0) for r in results)
    sessions = max((r["sessions"] for r in results), default=1)

    print("\n" + "=" * 104)
    print("  PORTFOLIO — all five markets together, second half only (the part never used to pick settings)")
    print("=" * 104)
    print(f"  trades {test_trades}  ·  net ${test_usd:+,.0f} (worst case) to ${best_usd:+,.0f} (best case)"
          f"  ·  over roughly {sessions} sessions"
          f"  ·  ${test_usd / sessions:+,.0f} to ${best_usd / sessions:+,.0f} per session")
    print(f"  full sample: {all_trades} trades, ${all_usd:+,.0f}")
    if test_usd > 0:
        print(f"  at that rate, +$1,250 would take ~{-1250 / (test_usd / sessions):.0f} sessions")
        print(f"  and -$1,000 would take ~{1000 / (test_usd / sessions):.0f} sessions of bad luck")
    elif test_usd < 0:
        print(f"  at that rate, -$1,000 arrives in ~{1000 / abs(test_usd / sessions):.0f} sessions")

    RAW.parent.mkdir(parents=True, exist_ok=True)
    RAW.write_text(json.dumps({"tf": tfs, "results": results,
                               "portfolio_test_usd": test_usd,
                               "portfolio_test_trades": test_trades,
                               "sessions": sessions}, indent=2, default=str))

    lines = ["# The scalp experiment — paper, five markets, no gate chain", "",
             f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')} · "
             f"one micro contract · ${COMMISSION:.2f}/side commission + {SLIP_TICKS} tick slippage per side",
             "",
             "Every EMA cross, both directions, chosen on the first half of the sample and scored on",
             "the second. Not evidence of an edge — evidence of what the costs do to one.", "",
             "| market | tf | bars | sessions | chosen | 2nd-half trades | /day | win | avg R | net $ (worst→best) | max DD |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        c, s = r["chosen"], r["test"]
        if not s.get("trades"):
            continue
        lines.append(f"| {r['symbol']} | {r['tf']} | {r['bars']} | {r['sessions']} | "
                     f"{c['fast']}/{c['slow']} {c['stop']}A/{c['target']}A {c['hold']}b | {s['trades']} | "
                     f"{s['per_day']:.1f} | {s['win']:.0f}% | {s['avg_r']:+.2f} | "
                     f"${s['usd']:+,.0f} → ${r['test_best'].get('usd', 0):+,.0f} | ${s['dd']:,.0f} |")
    lines += ["", f"Portfolio, second half: **{test_trades} trades, ${test_usd:+,.0f} to ${best_usd:+,.0f}**"
                  f" over ~{sessions} sessions (${test_usd / sessions:+,.0f} to ${best_usd / sessions:+,.0f} per session).",
              "", "The range is the ambiguous-bar bracket: worst case assumes the stop filled first when a bar"
              "held both, best case the target. Neither is the truth; a strategy that only pays in the best"
              "case has not been shown to pay.", ""]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines))
    print(f"\n  written to {OUT} and {RAW}")


if __name__ == "__main__":
    main()
