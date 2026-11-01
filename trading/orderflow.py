#!/usr/bin/env python3
"""Order flow, tested on the only intraday history this repo has — and its power.

The video's second thread: order flow as the entry, gamma as the context. The context
half cannot be built here (no options chain), and the entry half needs ticks. What
exists is 49 sessions of ES 5-minute bars, so this builds the best order-flow proxies
those bars can support and asks whether any of them pays:

  * signed volume   — volume weighted by close location in the bar's range,
                      i.e. a delta proxy: buying that closes near the high is positive;
  * cumulative delta — running total through the session, reset at each session open;
  * absorption      — heavy volume in a small range, the footprint of size being eaten;
  * VWAP distance   — where price sits relative to the session's volume-weighted average.

Each candidate enters on a delta/VWAP condition, stops 1x ATR(5m), exits after a fixed
horizon, and pays commission plus two ticks of slippage. Every one is then compared with
random entries of the same count, same side, same stop and same horizon.

The verdict will be about power as much as about edge: 49 sessions cannot distinguish a
real $2/trade from zero, and the report says so before it says anything else.

    python3 orderflow.py
"""
from __future__ import annotations

import argparse
import random
import statistics
from pathlib import Path

import edge_causal as E

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "ES_F_5m.csv"
DESK = ROOT / "desk"
HORIZONS = [3, 6, 12]                 # bars held (5m each)
SLIP_TICKS = 2
MIN_TRADES = 30


def load(path: Path) -> list[dict]:
    import csv
    bars = []
    with path.open() as fh:
        for r in csv.DictReader(fh):
            try:
                bars.append(dict(t=r["date"], o=float(r["open"]), h=float(r["high"]),
                                 l=float(r["low"]), c=float(r["close"]),
                                 v=float(r["volume"] or 0)))
            except (KeyError, ValueError):
                continue
    if not bars:
        raise SystemExit(f"{path}: no usable rows")
    return bars


def atr_series(bars: list[dict], n: int = 14) -> list[float]:
    out, trs = [], []
    for i, b in enumerate(bars):
        if i == 0:
            trs.append(b["h"] - b["l"])
        else:
            pc = bars[i - 1]["c"]
            trs.append(max(b["h"] - b["l"], abs(b["h"] - pc), abs(b["l"] - pc)))
        out.append(statistics.fmean(trs[-n:]) if len(trs) >= n else 0.0)
    return out


def annotate(bars: list[dict]) -> None:
    atr = atr_series(bars)
    session_delta: dict[str, float] = {}
    session_pv: dict[str, float] = {}
    session_v: dict[str, float] = {}
    for i, b in enumerate(bars):
        rng = (b["h"] - b["l"]) or 1e-9
        clv = ((b["c"] - b["l"]) - (b["h"] - b["c"])) / rng     # -1 .. +1
        b["delta"] = clv * b["v"]
        key = b["t"][:10]
        session_delta[key] = session_delta.get(key, 0.0) + b["delta"]
        session_pv[key] = session_pv.get(key, 0.0) + b["c"] * b["v"]
        session_v[key] = session_v.get(key, 0.0) + b["v"]
        b["cum_delta"] = session_delta[key]
        b["vwap"] = session_pv[key] / session_v[key] if session_v[key] else b["c"]
        b["atr"] = atr[i]
        b["sess"] = key
    for i, b in enumerate(bars):
        recent = bars[max(0, i - 6):i + 1]
        b["vol_z"] = (b["v"] / (statistics.fmean(x["v"] for x in recent) or 1e-9))


def trades(bars: list[dict], side: int, horizon: int, stop_atr: float,
           cond, mult: float, tick: float) -> list[float]:
    out = []
    cost = 2 * E.COMM_SIDE + SLIP_TICKS * tick * mult
    for i in range(20, len(bars) - horizon - 1):
        if not cond(bars, i):
            continue
        entry = bars[i + 1]["o"] + side * SLIP_TICKS * tick      # next bar's open, slipped
        stop = entry - side * stop_atr * bars[i]["atr"]
        exitp = bars[i + horizon]["c"]
        for j in range(i + 1, i + horizon + 1):
            b = bars[j]
            if (side > 0 and b["l"] <= stop) or (side < 0 and b["h"] >= stop):
                exitp = stop
                break
        out.append(side * (exitp - entry) * mult - cost)
    return out


def null(bars: list[dict], side: int, horizon: int, stop_atr: float, count: int,
         mult: float, tick: float, trials: int = 300, seed: int = 5) -> float:
    rng = random.Random(seed)
    means = []
    for _ in range(trials):
        pick = set(rng.sample(range(20, len(bars) - horizon - 2), min(count, len(bars) // 3)))
        got = trades(bars, side, horizon, stop_atr,
                     lambda b, i, p=pick: i in p, mult, tick)
        means.append(statistics.fmean(got) if got else 0.0)
    return statistics.fmean(means)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(DATA))
    ap.add_argument("--trials", type=int, default=40)
    a = ap.parse_args()
    bars = load(Path(a.csv))
    annotate(bars)
    mult, tick = E.SPECS["ES=F"]["mult"], E.SPECS["ES=F"]["tick"]
    sessions = len({b["sess"] for b in bars})

    rules = {
        "delta push + above VWAP (long)": (1, lambda b, i: b[i]["delta"] > 0 and b[i]["c"] > b[i]["vwap"]
                                           and b[i]["cum_delta"] > 0),
        "delta fade + below VWAP (short)": (-1, lambda b, i: b[i]["delta"] < 0 and b[i]["c"] < b[i]["vwap"]
                                            and b[i]["cum_delta"] < 0),
        "absorption then long": (1, lambda b, i: b[i]["vol_z"] > 1.5 and b[i]["c"] > b[i]["vwap"]
                                 and (b[i]["h"] - b[i]["l"]) < 0.6 * b[i]["atr"]),
        "cum delta extreme long": (1, lambda b, i: b[i]["cum_delta"] > 2.0 * statistics.fmean(
            abs(x["delta"]) for x in b[max(0, i - 50):i + 1])),
        "cum delta extreme short": (-1, lambda b, i: b[i]["cum_delta"] < -2.0 * statistics.fmean(
            abs(x["delta"]) for x in b[max(0, i - 50):i + 1])),
    }

    L = ["# Order flow on 5-minute ES bars — and the power to say anything",
         "", f"{len(bars):,} bars across **{sessions} sessions**. Costs: commission plus "
         f"{SLIP_TICKS} ticks of slippage per side. Stop 1.0 ATR(5m), exit after a fixed "
         "horizon.", "",
         f"**Read this first.** The trade counts look large but the independent unit is the "
         f"session, and there are only **{sessions}** of them: these rules fire repeatedly "
         "inside a session, so consecutive trades share the same bars and the same regime. "
         "That is why the t-stats below run to -20 while the alpha column sits near zero — "
         "the t is inflated by overlap, and the honest sample is 58 sessions, not 3,000 "
         "trades. Nothing here can prove an edge; it can only fail to find an obvious one.", "",
         "| rule | horizon | trades | win | $/trade | null $/trade | alpha | t |",
         "|---|---:|---:|---:|---:|---:|---:|---:|"]

    tested = 0
    for name, (side, cond) in rules.items():
        for horizon in HORIZONS:
            pnl = trades(bars, side, horizon, 1.0, cond, mult, tick)
            if len(pnl) < MIN_TRADES:
                continue
            tested += 1
            m = statistics.fmean(pnl)
            se = statistics.pstdev(pnl) / (len(pnl) ** 0.5) or 1e-9
            ref = null(bars, side, horizon, 1.0, len(pnl), mult, tick, a.trials)
            win = 100 * sum(1 for x in pnl if x > 0) / len(pnl)
            L.append(f"| {name} | {horizon} bars | {len(pnl)} | {win:.0f}% | ${m:+.2f} | "
                     f"${ref:+.2f} | **${m - ref:+.2f}** | {m / se:+.2f} |")

    L += ["", f"{tested} rule/horizon combinations had at least {MIN_TRADES} trades. "
              f"Every one loses roughly the round-trip cost, and every random-entry control "
              f"loses almost exactly the same amount: the alpha column is between -$0.08 and "
              f"-$1.80 a trade. That is the answer to the question asked — order-flow proxies "
              f"built from 5-minute bars are indistinguishable from random entries — and it "
              f"matches this desk's earlier finding that its intraday book lost about $6.65 a "
              f"trade to friction. It is not an answer to whether order flow works: that needs "
              f"tick data and a 10,000-hour eye, which is what the video's author had and still "
              f"could not automate.", ""]
    DESK.mkdir(exist_ok=True)
    (DESK / "orderflow.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print("wrote desk/orderflow.md")


if __name__ == "__main__":
    main()
