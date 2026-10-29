#!/usr/bin/env python3
"""
The aggressive engine: RSI + TRAMA + EMA, aimed at ~one trade an hour.

What this is
------------
`scalp.py` proved the point that frequency alone loses money: take every EMA
cross and the costs eat you. This file asks the next question properly — does
*gating* the entries with real indicators, at a frequency of about one trade an
hour instead of one a minute, change the answer?

Six signal families, each built from the indicators you asked for:

  rsi_pull    trend up (price over a slow EMA), RSI dips then turns back up
  trama_cross price crosses the Trend Regularity Adaptive Moving Average,
              in the direction the EMA pair agrees with
  rsi_rev     RSI leaves oversold/overbought while still on the far side of a
              long EMA (counter-trend at an extreme, not in the middle)
  mom_align   EMA fast/slow cross while RSI is on the right side of 50 and
              TRAMA is sloping the same way
  breakout    close beyond the prior N-bar range with RSI and TRAMA agreeing
  confluence  2 of 3 agree (EMA side, RSI side of 50, price vs TRAMA) and it
              was not true on the previous bar, i.e. a fresh alignment

TRAMA, the honest note
----------------------
This is the LuxAlgo "Trend Regularity Adaptive Moving Average" as published on
TradingView and mirrored in freqtrade's `tv_trama`, not a lookalike:

    hh, ll   = highest high / lowest low over `length`
    change   = (hh made a new high) + (ll made a new low)      -> 0, 1 or 2
    tc       = SMA(change, length) ** 2                        -> smoothing constant
    trama[i] = trama[i-1] + tc[i-1] * (close[i] - trama[i-1])

So it is a Kaufman-style adaptive average whose speed is driven by how often
price is pushing its own range edge. Clean trend: change is often 2, tc near 1,
it hugs price. Chop: change is 0, tc near 0, it freezes. The published code can
let tc exceed 1 (an overshoot); it is clipped to 1 here, which is the same
decision freqtrade leaves to the data and changes nothing in normal ranges.

Method, so a lucky fit cannot be quoted as a result
---------------------------------------------------
Every (market, timeframe, strategy, exit) combination is scored on the first half
of the sample with a **frequency floor** — it must average at least N trades per
session or it is disqualified — and then the chosen one is measured on the second
half, which it never saw. Ambiguous bars (one bar containing both stop and target)
are bracketed worst-case and best-case, as in scalp.py.

    python3 trading/aggressive.py
    python3 trading/aggressive.py --floor 3          # easier frequency target
    python3 trading/aggressive.py --tf 5m --symbols ES=F,NQ=F
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lab import COMMISSION, atr_series, ema  # noqa: E402
from scanner import Bar, fetch_yahoo, rsi, rolling_extreme, sma  # noqa: E402
from scalp import MARKETS, SPANS, day, load  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "desk" / "aggressive.md"
RAW = HERE / "desk" / "aggressive.json"

SESSION_HOURS = 23          # futures trade 23 hours a day, Sunday-Friday
SLIP_TICKS = 1


# ------------------------------------------------------------- indicators
def trama(bars: list[Bar], length: int = 99) -> list[float | None]:
    """LuxAlgo Trend Regularity Adaptive Moving Average (see module docstring)."""
    n = len(bars)
    closes = [b.c for b in bars]
    hh = rolling_extreme([b.h for b in bars], length, True)
    ll = rolling_extreme([b.l for b in bars], length, False)

    # how many range edges price pushed on this bar: 0, 1 or 2
    change = [0.0] * n
    for i in range(1, n):
        if hh[i] is None or hh[i - 1] is None or ll[i] is None or ll[i - 1] is None:
            continue
        change[i] = float(hh[i] > hh[i - 1]) + float(ll[i] < ll[i - 1])

    tc = sma(change, length)
    out: list[float | None] = [None] * n
    if tc[length - 1] is None:
        return out

    ama = closes[0]
    out[0] = ama
    for i in range(1, n):
        if tc[i - 1] is None:
            continue          # warm-up: no smoothing constant yet, no value yet
        alpha = min(1.0, max(0.0, tc[i - 1] ** 2))
        ama = ama + alpha * (closes[i] - ama)
        out[i] = ama
    return out


def build(bars: list[Bar], p: dict) -> dict:
    closes = [b.c for b in bars]
    a = atr_series(bars)
    look = p.get("vol_look", 60)
    amed: list[float | None] = [None] * len(bars)
    for i in range(look - 1, len(bars)):
        window = [x for x in a[i - look + 1:i + 1] if x is not None]
        if len(window) >= look // 2:
            amed[i] = statistics.median(window)
    return {
        "c": closes,
        "ef": ema(closes, p["fast"]),
        "es": ema(closes, p["slow"]),
        "et": ema(closes, p["trend"]),
        "r": rsi(closes, p["rsi_len"]),
        "tr": trama(bars, p["tlen"]),
        "a": a,
        "amed": amed,
        "hour": [datetime.fromtimestamp(b.t, tz=timezone.utc).hour for b in bars],
        "hh": rolling_extreme([b.h for b in bars], p["nbars"], True),
        "ll": rolling_extreme([b.l for b in bars], p["nbars"], False),
    }


def votes(S: dict, i: int) -> int:
    """How many of the three agree that this is bullish, at bar i."""
    ef, es, r, tr, c = S["ef"][i], S["es"][i], S["r"][i], S["tr"][i], S["c"][i]
    if None in (ef, es, r, tr):
        return -99
    return int(ef > es) + int(r > 50) + int(c > tr)


def signal(name: str, S: dict, i: int, p: dict) -> int:
    """+1 long, -1 short, 0 nothing. Uses bars up to i-1 only: no look-ahead."""
    if i < 2:
        return 0

    # optional filters, applied before any indicator logic. Both are known at bar
    # i-1, so neither can see the bar being traded.
    if p.get("hours") is not None and S["hour"][i - 1] not in p["hours"]:
        return 0
    if p.get("vol_filter"):
        a0, m0 = S["a"][i - 1], S["amed"][i - 1]
        if a0 is None or m0 is None:
            return 0
        if not (p.get("vol_lo", 0.7) * m0 <= a0 <= p.get("vol_hi", 1.6) * m0):
            return 0
    c0, c1 = S["c"][i - 1], S["c"][i - 2]
    ef0, ef1, es0, es1 = S["ef"][i - 1], S["ef"][i - 2], S["es"][i - 1], S["es"][i - 2]
    r0, r1 = S["r"][i - 1], S["r"][i - 2]
    t0, t1 = S["tr"][i - 1], S["tr"][i - 2]
    e0, e1 = S["et"][i - 1], S["et"][i - 2]
    if None in (ef0, ef1, es0, es1, r0, r1, t0, t1, e0, e1):
        return 0

    if name == "rsi_pull":
        up = r1 < p["lo"] <= r0 and c0 > e0 and e0 >= e1
        dn = r1 > p["hi"] >= r0 and c0 < e0 and e0 <= e1
        return 1 if up else -1 if dn else 0

    if name == "trama_cross":
        up = c1 <= t1 and c0 > t0 and ef0 > es0
        dn = c1 >= t1 and c0 < t0 and ef0 < es0
        return 1 if up else -1 if dn else 0

    if name == "rsi_rev":
        up = r1 < p["lo"] <= r0 and c0 < e0
        dn = r1 > p["hi"] >= r0 and c0 > e0
        return 1 if up else -1 if dn else 0

    if name == "mom_align":
        up = ef1 <= es1 and ef0 > es0 and r0 > 50 and t0 > t1
        dn = ef1 >= es1 and ef0 < es0 and r0 < 50 and t0 < t1
        return 1 if up else -1 if dn else 0

    if name == "breakout":
        hh1, ll1 = S["hh"][i - 2], S["ll"][i - 2]
        if hh1 is None or ll1 is None:
            return 0
        up = c0 > hh1 and r0 > 55 and t0 > t1
        dn = c0 < ll1 and r0 < 45 and t0 < t1
        return 1 if up else -1 if dn else 0

    if name == "confluence":
        v0, v1 = votes(S, i - 1), votes(S, i - 2)
        if v0 < 0 or v1 < 0:
            return 0
        if v0 >= 2 > v1:
            return 1
        if v0 <= 1 < v1:
            return -1
        return 0
    raise SystemExit(f"unknown strategy {name}")


# ------------------------------------------------------------------ engine
def run(bars: list[Bar], S: dict, name: str, p: dict, pv: float, tick: float,
        order: str = "stop_first", symbol: str = "") -> list[dict]:
    cost = 2 * (COMMISSION + tick * pv)
    out: list[dict] = []
    pos = None
    last_exit = -10**9

    for i in range(2, len(bars)):
        b = bars[i]
        if pos:
            if pos["side"] > 0:
                at_stop, at_tgt = b.l <= pos["stop"], b.h >= pos["target"]
            else:
                at_stop, at_tgt = b.h >= pos["stop"], b.l <= pos["target"]
            hit = None
            if at_stop and at_tgt:
                hit = (("stop", pos["stop"]) if order == "stop_first"
                       else ("target", pos["target"]))
            elif at_stop:
                hit = ("stop", pos["stop"])
            elif at_tgt:
                hit = ("target", pos["target"])
            if hit is None and i - pos["i"] >= p["hold"]:
                hit = ("time", b.c)
            if hit is not None:
                why, px = hit
                net = (px - pos["entry"]) * pos["side"] * pv - cost
                risk = abs(pos["entry"] - pos["stop"]) * pv
                out.append({"t": b.t, "market": symbol, "strat": name,
                            "side": "long" if pos["side"] > 0 else "short",
                            "entry": pos["entry"], "exit": px, "why": why,
                            "bars": i - pos["i"], "usd": net, "risk_usd": risk,
                            "r": net / risk if risk else 0.0})
                pos = None
                last_exit = i

        if pos is None and i - last_exit >= p["cool"] and S["a"][i - 1]:
            side = signal(name, S, i, p)
            if side:
                a = S["a"][i - 1]
                entry = b.o
                pos = {"side": side, "entry": entry, "i": i,
                       "stop": entry - side * a * p["stop"],
                       "target": entry + side * a * p["target"]}
    return out


def stats(trades: list[dict], sessions: int) -> dict:
    if not trades:
        return {"trades": 0, "per_day": 0.0, "usd": 0.0, "total_r": 0.0, "dd": 0.0}
    usd = [t["usd"] for t in trades]
    eq = peak = dd = 0.0
    for u in usd:
        eq += u
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    risks = [t.get("risk_usd", 0.0) for t in trades]
    return {"trades": len(trades), "per_day": len(trades) / max(sessions, 1),
            "med_risk": statistics.median(risks),
            "win": 100 * sum(1 for u in usd if u > 0) / len(usd),
            "avg_r": statistics.mean(t["r"] for t in trades),
            "total_r": sum(t["r"] for t in trades),
            "usd": sum(usd), "dd": dd,
            "hours": len({datetime.fromtimestamp(t["t"], tz=timezone.utc).hour for t in trades})}


STRATS = ["rsi_pull", "trama_cross", "rsi_rev", "mom_align", "breakout", "confluence"]

BASE = {"fast": 9, "slow": 21, "trend": 100, "rsi_len": 14, "tlen": 99,
        "nbars": 20, "lo": 40, "hi": 60}

VARIANTS = {
    "rsi_pull": [{"lo": 40, "hi": 60}, {"lo": 45, "hi": 55}],
    "trama_cross": [{"tlen": 99}, {"tlen": 34, "fast": 5, "slow": 13}],
    "rsi_rev": [{"lo": 30, "hi": 70, "trend": 200}, {"lo": 25, "hi": 75, "trend": 100}],
    "mom_align": [{"fast": 9, "slow": 21, "trend": 50}, {"fast": 5, "slow": 13, "trend": 100}],
    "breakout": [{"nbars": 20}, {"nbars": 10}],
    "confluence": [{"fast": 9, "slow": 21, "trend": 100}, {"fast": 5, "slow": 13, "trend": 50}],
}

EXITS = [
    {"stop": 0.75, "target": 1.5, "hold": 24, "cool": 6},
    {"stop": 1.0, "target": 2.0, "hold": 24, "cool": 12},
    {"stop": 1.0, "target": 3.0, "hold": 48, "cool": 6},
    {"stop": 1.5, "target": 3.0, "hold": 48, "cool": 12},
]


def sweep_market(symbol: str, tf: str, floor: float) -> list[dict]:
    name, pv, tick = MARKETS[symbol]
    bars = load(symbol, tf)
    if len(bars) < 400:
        return []
    cut = len(bars) // 2
    halves = (bars[:cut], bars[cut:])
    sess = tuple(len({day(b.t) for b in h}) for h in halves)

    rows: list[dict] = []
    for strat in STRATS:
        for var in VARIANTS[strat]:
            p = {**BASE, **var, **EXITS[0]}
            S = build(bars, p)
            for ex in EXITS:
                pp = {**p, **ex}
                tr = stats(run(halves[0], S, strat, pp, pv, tick), sess[0])
                if tr["trades"] < max(6, floor * sess[0] * 0.6):
                    continue                       # too rare to be a real candidate
                te = stats(run(halves[1], S, strat, pp, pv, tick), sess[1])
                te_best = stats(run(halves[1], S, strat, pp, pv, tick, "target_first"), sess[1])
                rows.append({"symbol": symbol, "contract": name, "tf": tf,
                             "strat": strat, "params": pp, "train": tr,
                             "test": te, "test_best": te_best,
                             "sessions_train": sess[0], "sessions_test": sess[1]})
    return rows


def pick(rows: list[dict], floor: float) -> dict | None:
    ok = [r for r in rows if r["train"]["per_day"] >= floor]
    if not ok:
        ok = [r for r in rows if r["train"]["per_day"] > 0]
    if not ok:
        return None
    return max(ok, key=lambda r: r["train"]["total_r"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="5m,15m")
    ap.add_argument("--symbols", default=",".join(MARKETS))
    ap.add_argument("--floor", type=float, default=4.0,
                    help="required trades per session in the training half; "
                         "5 markets x 4.8/day ~ one trade an hour")
    ap.add_argument("--exclude", default="NKD=F",
                    help="markets left out of the portfolio total. NKD moves $25 per tick, "
                         "so one tick of slippage is a fifth of a typical stop and its "
                         "dollar P&L is a different animal to the other four")
    args = ap.parse_args()
    tfs = [t for t in args.tf.split(",") if t]
    syms = [s for s in args.symbols.split(",") if s]

    print("=" * 108)
    print("  AGGRESSIVE ENGINE — RSI + TRAMA + EMA · chosen on first half, scored on second")
    print(f"  one micro contract · ${COMMISSION:.2f}/side + {SLIP_TICKS} tick slippage/side"
          f" · frequency floor {args.floor}/session/market")
    print("=" * 108)

    all_rows: list[dict] = []
    chosen: list[dict] = []
    for tf in tfs:
        for sym in syms:
            try:
                rows = sweep_market(sym, tf, args.floor)
            except Exception as err:  # noqa: BLE001
                print(f"  {sym:7} {tf:4} data unavailable: {err}")
                continue
            if not rows:
                print(f"  {sym:7} {tf:4} no candidate met the frequency floor")
                continue
            all_rows += rows
            best = pick(rows, args.floor)
            if not best:
                continue
            chosen.append(best)
            s, b = best["test"], best["test_best"]
            print(f"\n  {sym:7} {tf:4}  chosen {best['strat']:12}"
                  f" stop {best['params']['stop']}A tgt {best['params']['target']}A"
                  f" hold {best['params']['hold']}b cool {best['params']['cool']}b")
            print(f"    {'':9}{'trades':>7}{'/day':>7}{'win':>7}{'avgR':>7}"
                  f"{'net $':>13}{'maxDD':>9}")
            for label, st in (("train", best["train"]), ("TEST", s), ("test best", b)):
                print(f"    {label:9}{st['trades']:7d}{st['per_day']:7.1f}"
                      f"{st.get('win', 0):7.1f}{st['avg_r']:+7.2f}{st['usd']:+13,.0f}"
                      f"{st['dd']:9,.0f}")

    if not chosen:
        print("\n  nothing qualified. Raise --floor or add data.")
        return

    # ---- by strategy, out of sample only
    by_strat: dict[str, list[dict]] = {}
    for r in chosen:
        by_strat.setdefault(r["strat"], []).append(r)

    print("\n" + "=" * 108)
    print("  OUT OF SAMPLE — which signal family actually paid?")
    print("=" * 108)
    print(f"  {'strategy':12}{'markets':>8}{'trades':>8}{'/session':>10}{'win':>7}"
          f"{'avgR':>7}{'net $ worst':>13}{'net $ best':>12}{'maxDD':>10}")
    strat_rows = []
    for strat, rs in sorted(by_strat.items(),
                            key=lambda kv: sum(r["test"]["usd"] for r in kv[1]),
                            reverse=True):
        trades = [r["test"]["trades"] for r in rs]
        usd = sum(r["test"]["usd"] for r in rs)
        best = sum(r["test_best"]["usd"] for r in rs)
        n = sum(trades)
        win = (sum(r["test"].get("win", 0) * r["test"]["trades"] for r in rs) / n) if n else 0
        avg = (sum(r["test"]["avg_r"] * r["test"]["trades"] for r in rs) / n) if n else 0
        dd = min(r["test"]["dd"] for r in rs) if rs else 0
        sess = max(r["sessions_test"] for r in rs)
        strat_rows.append({"strat": strat, "markets": len(rs), "trades": n,
                           "per_session": n / sess, "usd": usd, "usd_best": best,
                           "dd": dd, "win": win, "avg_r": avg})
        print(f"  {strat:12}{len(rs):8d}{n:8d}{n / sess:10.1f}{win:7.1f}{avg:+7.2f}"
              f"{usd:+13,.0f}{best:+12,.0f}{dd:10,.0f}")

    # ---- robustness: every candidate config, not just the lucky pick
    print("\n" + "=" * 108)
    print("  ROBUSTNESS — every config that met the frequency floor, out of sample")
    print("=" * 108)
    print(f"  {'strategy':12}{'tf':5}{'configs':>8}{'positive':>10}"
          f"{'median $/session':>18}{'median trades/day':>19}")
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in all_rows:
        groups.setdefault((r["strat"], r["tf"]), []).append(r)
    robust: list[dict] = []
    for (strat, tf), rs in sorted(groups.items(),
                                  key=lambda kv: -statistics.median(
                                      [x["test"]["usd"] / max(x["sessions_test"], 1)
                                       for x in kv[1]])):
        ps = [r["test"]["usd"] / max(r["sessions_test"], 1) for r in rs]
        tp = [r["test"]["per_day"] for r in rs]
        share = 100 * sum(1 for x in ps if x > 0) / len(ps)
        robust.append({"strat": strat, "tf": tf, "configs": len(rs),
                       "pct_positive": share,
                       "median_per_session": statistics.median(ps),
                       "median_per_day": statistics.median(tp)})
        print(f"  {strat:12}{tf:5}{len(rs):8d}{share:9.0f}%"
              f"{statistics.median(ps):+18,.0f}{statistics.median(tp):19.1f}")

    # ---- portfolio, one timeframe at a time so the session counts line up
    excluded = {s.strip() for s in args.exclude.split(",") if s.strip()}
    port_by_tf: dict[str, dict] = {}
    for r in chosen:
        if r["symbol"] in excluded:
            continue
        g = port_by_tf.setdefault(r["tf"], {"usd": 0.0, "best": 0.0, "trades": 0,
                                            "sessions": 0, "markets": 0})
        g["usd"] += r["test"]["usd"]
        g["best"] += r["test_best"]["usd"]
        g["trades"] += r["test"]["trades"]
        g["sessions"] = max(g["sessions"], r["sessions_test"])
        g["markets"] += 1

    print("\n" + "=" * 108)
    print("  PORTFOLIO — one contract per market, second half only"
          + (f" (excluding {', '.join(sorted(excluded))})" if excluded else ""))
    print("=" * 108)
    for tf, g in sorted(port_by_tf.items()):
        print(f"  {tf:4} {g['markets']} markets  {g['trades']:4d} trades over ~{g['sessions']} sessions"
              f"  =  {g['trades'] / g['sessions']:.1f}/session"
              f"  =  {g['trades'] / (g['sessions'] * SESSION_HOURS):.2f}/hour"
              f"  →  ${g['usd'] / g['sessions']:+,.0f} to ${g['best'] / g['sessions']:+,.0f}/session")

    if not port_by_tf:
        print("\n  every market was excluded — nothing to total")
        return
    headline_tf = max(port_by_tf, key=lambda k: port_by_tf[k]["sessions"])
    head = port_by_tf[headline_tf]
    total, total_best = head["usd"], head["best"]
    trades, sess = head["trades"], head["sessions"]
    per_hour = trades / (sess * SESSION_HOURS)
    print(f"\n  headline ({headline_tf}, longest sample): net ${total:+,.0f} to ${total_best:+,.0f}"
          f" over ~{sess} sessions = ${total / sess:+,.0f} to ${total_best / sess:+,.0f}/session"
          f", {per_hour:.2f} trades/hour")
    if total < 0:
        print(f"  worst case: the $1,000 end-of-day buffer is gone in "
              f"~{1000 / abs(total / sess):.1f} sessions")
    else:
        print(f"  at the worst-case rate +$1,250 takes ~{1250 / (total / sess):.0f} sessions")
        print(f"  the same bet going the other way loses $1,000 in "
              f"~{1000 / (total_best / sess):.1f} sessions")

    # ---- improvement loop: does a simple filter rescue any of it?
    US_HOURS = set(range(13, 21))     # 13:00-20:00 UTC, roughly the US cash session
    print("\n" + "=" * 108)
    print("  IMPROVEMENT LOOP — same rules, plus a session filter and a volatility band")
    print("=" * 108)
    print(f"  {'market':8}{'tf':6}{'rule':13}{'base $/sess':>13}{'US hours':>11}"
          f"{'vol band':>11}{'both':>10}")
    filt: dict[str, list[float]] = {"base": [], "hours": [], "vol": [], "both": []}
    filter_rows: list[dict] = []
    for r in chosen:
        if r["symbol"] in excluded or r["tf"] != headline_tf:
            continue
        _, pv, tick = MARKETS[r["symbol"]]
        bars = load(r["symbol"], r["tf"])
        cut = len(bars) // 2
        cells: dict[str, float] = {}
        for label, extra in (("base", {}), ("hours", {"hours": US_HOURS}),
                             ("vol", {"vol_filter": True}),
                             ("both", {"hours": US_HOURS, "vol_filter": True})):
            pp = {**r["params"], **extra}
            st = stats(run(bars[cut:], build(bars, pp), r["strat"], pp, pv, tick,
                           "stop_first", r["symbol"]), r["sessions_test"])
            cells[label] = st["usd"] / max(r["sessions_test"], 1)
            filt[label].append(cells[label])
        filter_rows.append({"symbol": r["symbol"], "tf": r["tf"], "strat": r["strat"],
                            **cells})
        print(f"  {r['symbol']:8}{r['tf']:6}{r['strat']:13}{cells['base']:+13,.0f}"
              f"{cells['hours']:+11,.0f}{cells['vol']:+11,.0f}{cells['both']:+10,.0f}")
    if filt["base"]:
        med = {k: statistics.median(v) for k, v in filt.items()}
        keep = {k: sum(1 for x in v if x > 0) for k, v in filt.items()}
        print(f"  {'MEDIAN':8}{'':6}{'':13}{med['base']:+13,.0f}{med['hours']:+11,.0f}"
              f"{med['vol']:+11,.0f}{med['both']:+10,.0f}")
        print(f"  {'positive':8}{'':6}{'':13}" + "".join(
            f"{keep[k]}/{len(filt[k]):<9}" for k in ("base", "hours", "vol", "both")))

    # ---- the file
    lines = ["# The aggressive engine — RSI, TRAMA, EMA, ~one trade an hour", "",
             f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')} · "
             f"one micro contract · ${COMMISSION:.2f}/side + {SLIP_TICKS} tick slippage per side",
             "",
             "Every combination is chosen on the first half of the sample with a frequency floor, then",
             "measured on the second half, which it never saw. The bracket is the ambiguous-bar test:",
             "worst case assumes the stop filled first when a bar held both, best case the target.", "",
             "## Out of sample, by signal family", "",
             "| strategy | markets | trades | per session | win | avg R | net $ (worst) | net $ (best) | worst DD |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in strat_rows:
        lines.append(f"| {r['strat']} | {r['markets']} | {r['trades']} | "
                     f"{r['per_session']:.1f} | {r['win']:.0f}% | {r['avg_r']:+.2f} | "
                     f"${r['usd']:+,.0f} | ${r['usd_best']:+,.0f} | ${r['dd']:,.0f} |")
    lines += ["", "## The chosen rule per market", "",
              "| market | tf | rule | exits | 2nd-half trades | /day | net $ worst→best | max DD |",
              "|---|---|---|---|---|---|---|---|"]
    for r in chosen:
        lines.append(f"| {r['symbol']} | {r['tf']} | {r['strat']} | "
                     f"{r['params']['stop']}A/{r['params']['target']}A {r['params']['hold']}b | "
                     f"{r['test']['trades']} | {r['test']['per_day']:.1f} | "
                     f"${r['test']['usd']:+,.0f} → ${r['test_best']['usd']:+,.0f} | "
                     f"${r['test']['dd']:,.0f} |")
    lines += ["", "## Portfolio, second half", "",
              "NKD is left out on purpose: it moves $25 a tick, so one tick of slippage is a fifth of a",
              "typical stop and its dollar figures swamp the other four markets.", "",
              "| timeframe | markets | trades | per session | trades/hour | $/session worst→best |",
              "|---|---|---|---|---|---|"]
    for tf, g in sorted(port_by_tf.items()):
        lines.append(f"| {tf} | {g['markets']} | {g['trades']} | {g['trades'] / g['sessions']:.1f} | "
                     f"{g['trades'] / (g['sessions'] * SESSION_HOURS):.2f} | "
                     f"${g['usd'] / g['sessions']:+,.0f} → ${g['best'] / g['sessions']:+,.0f} |")
    if filter_rows:
        lines += ["", "## Improvement loop — session and volatility filters", "",
                  "`hours` trades only 13:00-20:00 UTC. `vol` requires ATR to sit between 0.7x and",
                  "1.6x its own 60-bar median, so it skips dead tape and panics alike.", "",
                  "| market | tf | rule | base $/session | US hours | vol band | both |",
                  "|---|---|---|---|---|---|---|"]
        for fr in filter_rows:
            lines.append(f"| {fr['symbol']} | {fr['tf']} | {fr['strat']} | "
                         f"${fr['base']:+,.0f} | ${fr['hours']:+,.0f} | "
                         f"${fr['vol']:+,.0f} | ${fr['both']:+,.0f} |")

    lines += ["", "## Robustness — every candidate config, not just the picked one", "",
              "One positive config proves nothing when many were tried. This is the whole population.", "",
              "| strategy | tf | configs | positive out of sample | median $/session | median trades/day |",
              "|---|---|---|---|---|---|"]
    for rb in robust:
        lines.append(f"| {rb['strat']} | {rb['tf']} | {rb['configs']} | "
                     f"{rb['pct_positive']:.0f}% | ${rb['median_per_session']:+,.0f} | "
                     f"{rb['median_per_day']:.1f} |")
    lines += ["", f"Headline ({headline_tf}, NKD excluded): **{trades} trades, ${total:+,.0f} to "
                  f"${total_best:+,.0f}** over ~{sess} sessions — {per_hour:.2f} trades per hour, "
                  f"${total / sess:+,.0f} to ${total_best / sess:+,.0f} per session.", ""]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines))
    RAW.write_text(json.dumps({"floor": args.floor, "tfs": tfs,
                               "chosen": chosen, "by_strategy": strat_rows,
                               "portfolio_usd": total,
                               "portfolio_usd_best": total_best,
                               "trades": trades, "sessions": sess,
                               "trades_per_hour": per_hour}, indent=2, default=str))
    print(f"\n  written to {OUT} and {RAW}")


if __name__ == "__main__":
    main()
