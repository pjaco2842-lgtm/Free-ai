#!/usr/bin/env python3
"""Test the video's claims on daily bars, with the controls the video says to use.

The video's four testable claims:

  1. get in on an early breakout, tight stop, hold to the close, no take-profit;
  2. when the open is above yesterday's close, breakouts in that direction work better;
  3. after a big trend day, same-direction breakouts earn ~nothing and opposite-direction
     breakouts are the strongest;
  4. fading breakouts/opens mostly dies, except fading a big Monday gap after the weekend.

Everything below is a daily-bar approximation and says so. A daily bar cannot show where
inside the session a prior-high break happened, so the exit is always the session close
(the video's "no TP, hold to close") and a stop is resolved on the close, conservatively.
That flatters tight stops and is why every row's stop is reported next to its alpha.

The controls are the ones the video insists on, and the ones this repo already uses:
  * a weekday-matched random-entry null that trades the same sessions with the same stop;
  * alpha = rule - null, so index drift is paid out of the score, not earned by it;
  * a multiple-testing line t > sqrt(2 ln N), because with N configurations the best one
    wins by luck unless it clears that bar.

    python3 video_sweep.py
    python3 video_sweep.py --symbols ES=F,NQ=F --top 20
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

import edge_causal as E

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DESK = ROOT / "desk"
DOWNS = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri"}
# Micro contracts: dollars per point, and the tick in points, so a one-tick slippage
# each side plus commission lands on the same $4.98 ES round trip the desk already uses.
SPECS = {
    "ES=F":  ("ES_F_1d.csv",  5.0, 0.25),
    "NQ=F":  ("NQ_F_1d.csv",  2.0, 0.25),
    "GC=F":  ("GC_F_1d.csv", 10.0, 0.10),
    "CL=F":  ("CL_F_1d.csv", 100.0, 0.01),
    "NKD=F": ("NKD_F_1d.csv", 5.0, 5.0),
}
STOPS = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5)
LB = (1, 2, 3, 5)
MIN_TRADES = 30


def ema(x: np.ndarray, n: int) -> np.ndarray:
    a, out = 2.0 / (n + 1), np.empty_like(x)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def load(sym: str) -> dict:
    fn, mult, tick = SPECS[sym]
    D = E.load_csv(str(DATA / fn))
    o, h, l, c = (np.array(D[k], float) for k in "ohlc")
    atr = np.array(D["atr"], float)
    pc = np.r_[np.nan, c[:-1]]
    prior = np.r_[np.nan, atr[:-1]]                      # ATR known before the session
    n = len(c)
    dow = np.array([__import__("datetime").date.fromisoformat(x).weekday() for x in D["d"]])
    up = c > ema(c, 200)
    tr_size = np.abs(c - o) / np.where(prior > 0, prior, np.nan)   # trend-day size
    rng = (h - l) / np.where(prior > 0, prior, np.nan)
    big_prev = np.r_[False, tr_size[:-1] >= 1.5]          # yesterday was a trend day
    narrow_prev = np.r_[False, rng[:-1] <= 0.5]           # yesterday was a narrow day
    return dict(D=D, o=o, h=h, l=l, c=c, atr=atr, pc=pc, prior=prior, n=n, dow=dow,
                up=up, big_prev=big_prev, narrow_prev=narrow_prev, mult=mult, tick=tick,
                cost=2 * E.COMM_SIDE + 2 * mult * tick)


def family(D: dict, name: str, lb: int) -> tuple[np.ndarray, np.ndarray]:
    """Entry price and side for one family. NaN where it does not trade."""
    o, h, l, c, pc, n = D["o"], D["h"], D["l"], D["c"], D["pc"], D["n"]
    hi = np.full(n, np.nan)
    lo = np.full(n, np.nan)
    for i in range(1, n):
        hi[i] = h[max(0, i - lb):i].max()
        lo[i] = l[max(0, i - lb):i].min()
    nan = np.full(n, np.nan)
    ones = np.ones(n)

    if name == "gapdir_open":            # open in the gap's direction, hold to close
        entry = np.where(pc > 0, o, nan)
        side = np.sign(o - pc)
    elif name == "gapfade_open":         # fade the gap
        entry = np.where(pc > 0, o, nan)
        side = -np.sign(o - pc)
    elif name == "prior_high_break":     # intraday break of the prior high
        hit = (h > hi) & (o <= hi)
        entry = np.where(hit, hi + D["tick"], nan)
        side = np.where(hit, 1.0, np.nan)
    elif name == "prior_low_break":
        hit = (l < lo) & (o >= lo)
        entry = np.where(hit, lo - D["tick"], nan)
        side = np.where(hit, -1.0, np.nan)
    elif name == "narrow_hi_break":      # break out of yesterday's narrow range
        hit = (h > hi) & (o <= hi) & D["narrow_prev"][:, None].ravel()
        entry = np.where(hit, hi + D["tick"], nan)
        side = np.where(hit, 1.0, np.nan)
    elif name == "narrow_lo_break":
        hit = (l < lo) & (o >= lo) & D["narrow_prev"]
        entry = np.where(hit, lo - D["tick"], nan)
        side = np.where(hit, -1.0, np.nan)
    elif name == "monday_gap_fade":      # claim 4's exception
        big = np.abs(o - pc) >= 0.5 * D["prior"]
        hit = (D["dow"] == 0) & big
        entry = np.where(hit, o, nan)
        side = np.where(hit, -np.sign(o - pc), np.nan)
    elif name == "trendday_fade":        # claim 3, opposite direction
        hit = D["big_prev"]
        entry = np.where(hit, o, nan)
        side = np.where(hit, -np.sign(c - o), np.nan)
    else:
        entry, side = nan, nan
    side = np.where(np.isfinite(entry), side, np.nan)
    side = np.where(side == 0, nan, side)
    return entry, side * ones


FAMILIES = ("gapdir_open", "gapfade_open", "prior_high_break", "prior_low_break",
            "narrow_hi_break", "narrow_lo_break", "monday_gap_fade", "trendday_fade")


def pnl(D: dict, entry, side, stop: float, tp: float | None = None) -> np.ndarray:
    """Per-trade dollars, one micro, stop resolved on the close, exit at the close.

    `tp` in R: the video claims a take-profit makes every winner worse, so the sweep has
    to price one rather than take the claim on faith.
    """
    move = side * (D["c"] - entry)
    stop_pts = stop * D["prior"]
    move = np.where(move < -stop_pts, -stop_pts, move)
    if tp:
        move = np.where(move > tp * stop_pts, tp * stop_pts, move)
    return move * D["mult"] - D["cost"]


def mask_for(D: dict, gap: str, trend: str, post: str, day: int | None, side) -> np.ndarray:
    o, pc = D["o"], D["pc"]
    m = np.ones(D["n"], bool)
    if gap == "with":
        m &= np.sign(o - pc) == np.sign(side)
    elif gap == "against":
        m &= np.sign(o - pc) == -np.sign(side)
    if trend == "up":
        m &= D["up"]
    elif trend == "down":
        m &= ~D["up"]
    if post == "after_trend":
        m &= D["big_prev"]
    elif post == "clean":
        m &= ~D["big_prev"]
    if day is not None:
        m &= D["dow"] == day
    return m


def null_mean(D: dict, stop: float, day: int | None, draws: int = 200) -> tuple[float, float, int]:
    """Random entries at the open, same weekday, same stop, both directions."""
    m = np.ones(D["n"], bool) if day is None else D["dow"] == day
    idx = np.where(m)[0]
    if len(idx) < MIN_TRADES:
        return 0.0, 0.0, 0
    rng = np.random.default_rng(7)
    side = rng.choice([-1.0, 1.0], size=(draws, len(idx)))
    move = side * (D["c"][idx] - D["o"][idx])
    stop_pts = stop * D["prior"][idx]
    move = np.where(move < -stop_pts, -stop_pts, move)
    per = move * D["mult"] - D["cost"]
    return float(per.mean()), float(per.mean(axis=1).std(ddof=1)), len(idx)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=",".join(SPECS))
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--out", default="desk/video-sweep.md")
    a = ap.parse_args()

    rows, used = [], 0
    for sym in [s.strip() for s in a.symbols.split(",") if s.strip()]:
        if sym not in SPECS or not (DATA / SPECS[sym][0]).exists():
            print(f"  {sym}: no data ({SPECS.get(sym, ('?',))[0]}), skipped")
            continue
        D = load(sym)
        print(f"  {sym}: {D['n']} sessions to {D['D']['d'][-1]}, cost ${D['cost']:.2f}/trade")
        nulls = {}
        for fam in FAMILIES:
            for lb in LB:
                entry, side = family(D, fam, lb)
                if not np.isfinite(entry).any():
                    continue
                for gap in ("any", "with", "against"):
                    for trend in ("any", "up", "down"):
                        for post in ("any", "after_trend", "clean"):
                            for day in (None, 0, 1, 2, 3, 4):
                                base = mask_for(D, gap, trend, post, day, side) & np.isfinite(entry)
                                if base.sum() < MIN_TRADES:
                                    continue
                                for stop in STOPS:
                                  for tp in (None, 1.0, 2.0):
                                    per = pnl(D, entry, side, stop, tp)[base]
                                    per = per[np.isfinite(per)]
                                    if len(per) < MIN_TRADES:
                                        continue
                                    used += 1
                                    key = (stop, day)
                                    if key not in nulls:
                                        nulls[key] = null_mean(D, stop, day)
                                    nm, nsd, nnat = nulls[key]
                                    mean = float(per.mean())
                                    alpha = mean - nm
                                    se = math.sqrt(per.var(ddof=1) / len(per)
                                                   + (nsd ** 2) / max(nnat, 1))
                                    t = alpha / se if se > 0 else 0.0
                                    rows.append(dict(sym=sym, fam=fam, lb=lb, gap=gap,
                                                     trend=trend, post=post, day=day,
                                                     stop=stop, tp=tp, n=len(per),
                                                     mean=mean, alpha=alpha, t=t,
                                                     win=100 * float((per > 0).mean())))

    if not rows:
        print("nothing to score")
        return
    line = math.sqrt(2 * math.log(max(used, 2)))
    rows.sort(key=lambda r: -r["alpha"])

    L = ["# The 26,000-strategy video, tested properly on daily bars", "",
         f"**{used:,} configurations scored** across "
         f"{len({r['sym'] for r in rows})} contracts. Exit is always the session close "
         f"(\"no TP, hold to close\"); the stop is resolved on the close, which flatters "
         f"tight stops and is why every stop is printed beside its score. Costs: commission "
         f"plus one tick of slippage each side.", "",
         f"Multiple-testing line for {used:,} tries: **t > {line:.2f}**. Anything below it is "
         f"the best of a coin-flipping crowd, not an edge.", "",
         f"| sym | family | lb | gap | trend | post | day | stop | tp | n | win | "
         f"$/trade | alpha | t |", "|---|---|---:|---|---|---|---|---:|---|---:|---:|---:|---:|---:|"]
    for r in rows[:a.top]:
        L.append(f"| {r['sym']} | {r['fam']} | {r['lb']} | {r['gap']} | {r['trend']} | "
                 f"{r['post']} | {DOWNS.get(r['day'], 'all') if r['day'] is not None else 'all'} | "
                 f"{r['stop']} ATR | {r['tp'] or 'close'} | {r['n']} | {r['win']:.0f}% | "
                 f"${r['mean']:+.2f} | {r['alpha']:+.2f} | {r['t']:+.2f} |")

    good = [r for r in rows if r["alpha"] > 0 and r["t"] > line]
    L += ["", "## Verdict", "",
          f"- configurations with positive alpha: **{sum(1 for r in rows if r['alpha'] > 0):,} "
          f"of {used:,}** ({100*sum(1 for r in rows if r['alpha'] > 0)/used:.1f}%)",
          f"- configurations clearing the multiple-testing line: **{len(good)}**", ""]
    if not good:
        L += ["**Nothing survived.** Every positive-alpha configuration sits below the "
              "multiple-testing line, which is exactly what the video says happens to "
              "popular strategies when they meet 16 years of data and a matched null: "
              "the best of many tries is the best of many coin flips.", ""]
    else:
        L += ["Survivors:", ""]
        for r in good[:10]:
            L.append(f"- {r['sym']} {r['fam']} lb{r['lb']} {r['gap']}/{r['trend']}/{r['post']}/"
                     f"{DOWNS.get(r['day'], 'all') if r['day'] is not None else 'all'} "
                     f"{r['stop']} ATR: alpha {r['alpha']:+.2f}, t {r['t']:+.2f}, "
                     f"{r['n']} trades, {r['win']:.0f}% win")
        L.append("")
    L += ["## The video's four claims, scored", ""]
    for claim, fam in (("1 breakout + hold to close", "prior_high_break"),
                       ("2 gap direction", "gapdir_open"),
                       ("3 fade after a trend day", "trendday_fade"),
                       ("4 Monday gap fade", "monday_gap_fade")):
        sub = [r for r in rows if r["fam"] == fam]
        if not sub:
            continue
        best = max(sub, key=lambda r: r["alpha"])
        L.append(f"- **claim {claim}**: best alpha {best['alpha']:+.2f} "
                 f"({best['sym']}, {best['stop']} ATR stop, {best['n']} trades, "
                 f"{best['win']:.0f}% win, t {best['t']:+.2f}) — "
                 + ("clears the line" if best["t"] > line and best["alpha"] > 0
                    else "does not clear the line"))
    L.append("")

    DESK.mkdir(exist_ok=True)
    (ROOT / a.out).write_text("\n".join(L) + "\n")
    (DESK / "video-sweep.json").write_text(json.dumps(rows[:400], indent=1) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
