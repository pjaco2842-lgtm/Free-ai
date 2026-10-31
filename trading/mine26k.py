#!/usr/bin/env python3
"""
The wide sweep: every market the desk trades, every rule I can state, tested the way
the video says to test it — and then scored against the account that actually has to
pass, not against net profit.

The protocol (all four of the video's gates, plus two of the desk's own)
-----------------------------------------------------------------------
  1. **Unseen years.** Train 2009-2019, test 2020-2024. A rule has to be positive in
     both. Two good years are not an edge.
  2. **Parameter plateau.** A rule that works at a 1.0 ATR stop but not 0.75 or 1.5 is
     a coincidence. At least 4 of its 6 neighbours must also be positive out of sample.
  3. **Recent regime.** 2025 onward must not be negative. Edges go flat; this is where
     they show it.
  4. **Luck.** 500 random fills on the *same days, same side, same stop, same exit,
     same costs* — only the fill price is randomised inside that day's range. The rule
     must beat the 95th percentile. The video's point is exactly right: a coin flip with
     a different stop loss is not a coin flip.
  5. **Account.** $25,000, +$1,250 target, $1,000 end-of-day trailing floor that locks
     at $25,100, consistency ≤40%. Walked forward from *every* starting trade.
  6. **Speed.** How often the target is reached inside three sessions — the user's ask.

What is swept, per market
-------------------------
    rules    21 lookback variants of four break/fade families
             14 single-shape rules: inside/outside day, low-range expansion, gap
             continuation, gap fade, trend-day continuation and fade, MA pullback,
             prior-close break ("Oracle") and its fade, Monday big-gap fade, pin-bar
             break, strong-body continuation, and a walk-forward ridge model
    stops    0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5 x yesterday's ATR
    exits    close, 0.5R, 1R, 2R
    filters  gap alignment (3) x day of week (3) x 50-day trend (2) x direction (3)
    markets  ES, NQ, GC, CL, NKD  (micro contracts, one each)

Counted honestly: the space is large, so some winners are luck. The number that
matters at the end is survivors *after* the gates, compared with the 5% the luck gate
lets through by construction.

    python3 trading/mine26k.py
    python3 trading/mine26k.py --markets ES=F,GC=F --top 80 --runs 200
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lab import COMMISSION, atr_series, fetch_daily  # noqa: E402
from lab26k import day_trade as lab_day_trade, prep as lab_prep, spec_legs as lab_legs  # noqa: E402
from scalp import MARKETS  # noqa: E402
from scanner import sma  # noqa: E402

HERE = Path(__file__).resolve().parent
DESK = HERE / "desk"
MINE = DESK / "mined-book.json"
REPORT = DESK / "mine26k.md"
RAW = DESK / "mine26k.json"
LOG = HERE / "RESEARCH-LOG.md"

LOOKBACKS = [1, 2, 3, 5, 7, 10, 20]
STOPS = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5]
EXITS = ["close", "tp05", "tp1", "tp2"]
TP_R = {"close": None, "tp05": 0.5, "tp1": 1.0, "tp2": 2.0}
GAPS = ["any", "with", "against"]
DOWS = ["all", "mon", "fri"]
TRENDS = [False, True]
DIRS = ["both", "long", "short"]

FAM_N = {"nday_break": LOOKBACKS, "nday_fade": LOOKBACKS, "nr_break": LOOKBACKS,
         "streak_break": [2, 3, 4]}
SINGLES = ["inside_break", "outside_break", "vol_expand_break", "gap_cont", "gap_fade",
           "trendday_cont", "trendday_fade", "ma_pull", "prevclose_break",
           "prevclose_fade", "mon_gap_fade", "pin_break", "body_cont", "model"]
FAMILIES = list(FAM_N) + SINGLES
PAIRS = sum(len(v) for v in FAM_N.values()) + len(SINGLES)
COMBOS = len(GAPS) * len(DOWS) * len(TRENDS) * len(DIRS)
SPACE = PAIRS * len(STOPS) * len(EXITS) * COMBOS

TRAIN_LAST, TEST_FIRST, TEST_LAST = 2019, 2020, 2024
KEYS = ("family", "n", "stop", "exit", "gap", "trend", "dow", "dir")

# the 25K LucidFlex evaluation, same constants pick_book.py walks
START, FLOOR, LOCKED, TARGET_EQ, CONSISTENCY = 25_000.0, 24_000.0, 25_100.0, 26_250.0, 40.0

CACHE = Path(tempfile.gettempdir()) / "desk-bars"


# ------------------------------------------------------------------ data
def fetch_cached(symbol: str) -> list:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{symbol.replace('=', '_')}.json"
    if f.exists() and time.time() - f.stat().st_mtime < 3 * 3600:
        rows = json.loads(f.read_text())
        from scanner import Bar
        return [Bar(int(t), float(o), float(h), float(l), float(c), float(v))
                for t, o, h, l, c, v in rows]
    bars = fetch_daily(symbol)
    f.write_text(json.dumps([[b.t, b.o, b.h, b.l, b.c, getattr(b, "v", 0) or 0]
                             for b in bars]))
    return bars


def ffill(a: np.ndarray) -> np.ndarray:
    out = a.copy()
    last = np.nan
    for i in range(len(out)):
        if np.isnan(out[i]):
            out[i] = last
        else:
            last = out[i]
    return out


def to_np(values) -> np.ndarray:
    return np.array([np.nan if v is None else v for v in values], float)


def back(x: np.ndarray, k: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if 0 < k < len(x):
        out[k:] = x[:-k]
    return out


def model_pred(X: np.ndarray, y: np.ndarray, years: np.ndarray) -> np.ndarray:
    """Walk-forward ridge: fit only on years before the one being predicted.

    No shuffling, no k-fold, no hyper-parameter search — one lambda, refit once a year
    on everything older, predict the year it has never seen. That is the only way a
    daily learner can be judged, and it is why this family is in the sweep at all.
    """
    pred = np.full(len(y), np.nan)
    for yy in sorted(set(years.tolist())):
        tr = (years < yy) & ~np.isnan(y)
        cur = (years == yy) & ~np.isnan(X).any(1)
        if tr.sum() < 300 or not cur.any():
            continue
        mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-9
        Xt = (X[tr] - mu) / sd
        w = np.linalg.solve(Xt.T @ Xt + np.eye(X.shape[1]), Xt.T @ y[tr])
        pred[cur] = ((X[cur] - mu) / sd) @ w
    return pred


def prep(symbol: str) -> dict:
    bars = fetch_cached(symbol)
    ts = np.array([b.t for b in bars], int)
    o = np.array([b.o for b in bars], float)
    h = np.array([b.h for b in bars], float)
    l = np.array([b.l for b in bars], float)
    c = np.array([b.c for b in bars], float)
    dates = [datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d") for t in ts]
    atr = ffill(to_np(atr_series(bars)))
    D = {"symbol": symbol, "ts": ts, "o": o, "h": h, "l": l, "c": c, "dates": dates,
         "years": np.array([int(d[:4]) for d in dates]),
         "dow": np.array([datetime.fromtimestamp(t, tz=timezone.utc).weekday() for t in ts]),
         "atr": atr, "atr_prev": back(atr, 1),
         "sma20": ffill(to_np(sma(list(c), 20))),
         "sma50": ffill(to_np(sma(list(c), 50))),
         "rng": h - l, "body": c - o}
    D["hiN"], D["loN"] = {}, {}
    for n in LOOKBACKS:
        hi, lo = np.full(len(c), np.nan), np.full(len(c), np.nan)
        for i in range(n, len(c)):
            hi[i] = h[i - n:i].max()
            lo[i] = l[i - n:i].min()
        D["hiN"][n], D["loN"][n] = hi, lo

    # consecutive closes in one direction, counted up to the bar *before* the trade
    up = np.zeros(len(c), int)
    dn = np.zeros(len(c), int)
    for i in range(1, len(c)):
        up[i] = up[i - 1] + 1 if c[i] > c[i - 1] else 0
        dn[i] = dn[i - 1] + 1 if c[i] < c[i - 1] else 0
    D["up_streak"], D["dn_streak"] = up, dn

    # walk-forward ridge model: predict the open-to-close move of the *next* session
    a = D["atr_prev"]
    with np.errstate(invalid="ignore", divide="ignore"):
        X = np.column_stack([
            back(c, 1) / back(c, 2) - 1,
            back(c, 1) / back(c, 3) - 1,
            back(c, 1) / back(c, 6) - 1,
            back(c, 1) / back(c, 11) - 1,
            (back(c, 1) - back(D["sma20"], 1)) / a,
            (back(c, 1) - back(D["sma50"], 1)) / a,
            back(D["atr"], 1) / (back(atr, 61) + 1e-9),
            (o - back(c, 1)) / a,
            (back(c, 1) - back(l, 1)) / (back(D["rng"], 1) + 1e-9) - 0.5,
            np.log(back(D["rng"], 1) / (a + 1e-9)),
        ])
    y = np.clip((c - o) / a, -3, 3)
    X[~np.isfinite(X)] = np.nan
    y[~np.isfinite(y)] = np.nan
    D["features"] = X
    D["pred"] = model_pred(X, y, D["years"])
    return D


# ------------------------------------------------------------------ rules
def spec_legs(D: dict, spec: dict) -> tuple[dict, dict]:
    """Long-side and short-side orders for one rule. Same contract as lab26k."""
    fam, n = spec["family"], spec["n"]
    o, h, l, c = D["o"], D["h"], D["l"], D["c"]
    p1h, p1l, p1c, p1o = back(h, 1), back(l, 1), back(c, 1), back(o, 1)
    p1rng, p1atr = back(D["rng"], 1), back(D["atr"], 1)
    s20, s50 = back(D["sma20"], 1), back(D["sma50"], 1)
    p2h, p2l = back(h, 2), back(l, 2)
    allok = ~np.isnan(p1h)
    big = p1rng > 1.2 * p1atr
    up_body = (p1c > p1o) & (p1rng > 1.2 * p1atr) & ((p1c - p1o) > 0.6 * p1rng)
    dn_body = (p1c < p1o) & (p1rng > 1.2 * p1atr) & ((p1o - p1c) > 0.6 * p1rng)

    if fam == "nday_break":
        ok = ~np.isnan(D["hiN"][n])
        return (dict(mode="stop", side=1, trig=1, level=D["hiN"][n], ok=ok),
                dict(mode="stop", side=-1, trig=-1, level=D["loN"][n], ok=ok.copy()))
    if fam == "nday_fade":
        return (dict(mode="stop", side=1, trig=-1, level=D["loN"][n],
                     ok=~np.isnan(D["loN"][n])),
                dict(mode="stop", side=-1, trig=1, level=D["hiN"][n],
                     ok=~np.isnan(D["hiN"][n])))
    if fam == "nr_break":
        narrow = np.zeros(len(c), bool)
        for i in range(n, len(c)):
            narrow[i] = D["rng"][i - 1] <= D["rng"][i - n:i].min()
        ok = narrow & allok
        return (dict(mode="stop", side=1, trig=1, level=p1h, ok=ok),
                dict(mode="stop", side=-1, trig=-1, level=p1l, ok=ok.copy()))
    if fam == "streak_break":
        okL = (back(D["up_streak"], 1) >= n) & allok
        okS = (back(D["dn_streak"], 1) >= n) & allok
        return (dict(mode="stop", side=1, trig=1, level=p1h, ok=okL),
                dict(mode="stop", side=-1, trig=-1, level=p1l, ok=okS))
    if fam == "inside_break":
        ok = (p1h <= p2h) & (p1l >= p2l) & allok
        return (dict(mode="stop", side=1, trig=1, level=p1h, ok=ok),
                dict(mode="stop", side=-1, trig=-1, level=p1l, ok=ok.copy()))
    if fam == "outside_break":
        ok = (p1h > p2h) & (p1l < p2l) & allok
        return (dict(mode="stop", side=1, trig=1, level=p1h, ok=ok),
                dict(mode="stop", side=-1, trig=-1, level=p1l, ok=ok.copy()))
    if fam == "vol_expand_break":
        ok = (p1rng < 0.6 * p1atr) & allok
        return (dict(mode="stop", side=1, trig=1, level=p1h, ok=ok),
                dict(mode="stop", side=-1, trig=-1, level=p1l, ok=ok.copy()))
    if fam in ("trendday_cont", "trendday_fade"):
        if fam == "trendday_cont":
            return (dict(mode="stop", side=1, trig=1, level=p1h, ok=up_body),
                    dict(mode="stop", side=-1, trig=-1, level=p1l, ok=dn_body))
        return (dict(mode="stop", side=1, trig=1, level=p1h, ok=dn_body),
                dict(mode="stop", side=-1, trig=-1, level=p1l, ok=up_body))
    if fam in ("gap_cont", "gap_fade"):
        trend_up, trend_dn = p1c > back(c, 1 + max(n or 1, 1)), p1c < back(c, 1 + max(n or 1, 1))
        gap_up, gap_dn = o > p1c, o < p1c
        okb = ~np.isnan(p1c)
        if fam == "gap_cont":
            return (dict(mode="open", side=1, trig=1, level=None, ok=okb & gap_up & trend_up),
                    dict(mode="open", side=-1, trig=-1, level=None, ok=okb & gap_dn & trend_dn))
        return (dict(mode="open", side=1, trig=1, level=None, ok=okb & gap_dn),
                dict(mode="open", side=-1, trig=-1, level=None, ok=okb & gap_up))
    if fam == "mon_gap_fade":
        okb = (~np.isnan(p1c)) & (np.abs(o - p1c) > 0.25 * p1atr)
        return (dict(mode="open", side=1, trig=1, level=None, ok=okb & (o < p1c)),
                dict(mode="open", side=-1, trig=-1, level=None, ok=okb & (o > p1c)))
    if fam == "ma_pull":
        okL = (p1c > s50) & (p1l <= s20) & allok
        okS = (p1c < s50) & (p1h >= s20) & allok
        return (dict(mode="stop", side=1, trig=1, level=p1h, ok=okL),
                dict(mode="stop", side=-1, trig=-1, level=p1l, ok=okS))
    if fam == "prevclose_break":
        return (dict(mode="stop", side=1, trig=1, level=p1c, ok=allok),
                dict(mode="stop", side=-1, trig=-1, level=p1c, ok=allok.copy()))
    if fam == "prevclose_fade":
        return (dict(mode="stop", side=1, trig=-1, level=p1c, ok=allok),
                dict(mode="stop", side=-1, trig=1, level=p1c, ok=allok.copy()))
    if fam == "pin_break":
        body = np.abs(p1c - p1o)
        up_w = p1h - np.maximum(p1c, p1o)
        dn_w = np.minimum(p1c, p1o) - p1l
        bull = (dn_w > 1.5 * body) & (dn_w > 0.3 * p1rng) & allok
        bear = (up_w > 1.5 * body) & (up_w > 0.3 * p1rng) & allok
        return (dict(mode="stop", side=1, trig=1, level=p1h, ok=bull),
                dict(mode="stop", side=-1, trig=-1, level=p1l, ok=bear))
    if fam == "body_cont":
        return (dict(mode="stop", side=1, trig=1, level=p1c, ok=up_body),
                dict(mode="stop", side=-1, trig=-1, level=p1c, ok=dn_body))
    if fam == "model":
        p = D["pred"]
        ok = ~np.isnan(p) & (np.abs(p) >= 0.05)
        return (dict(mode="open", side=1, trig=1, level=None, ok=ok & (p > 0)),
                dict(mode="open", side=-1, trig=-1, level=None, ok=ok & (p < 0)))
    raise SystemExit(f"unknown family {fam}")


def spec_mask(D: dict, spec: dict) -> np.ndarray:
    m = np.ones(len(D["c"]), bool)
    gap_up = D["o"] > back(D["c"], 1)
    if spec["gap"] == "with":
        m &= gap_up
    elif spec["gap"] == "against":
        m &= ~gap_up
    if spec["dow"] == "mon":
        m &= D["dow"] == 0
    elif spec["dow"] == "fri":
        m &= D["dow"] == 4
    return m


def leg_pnl(D, leg, stop_k, tp_r, pv, tick):
    o, h, l, c = D["o"], D["h"], D["l"], D["c"]
    ok_atr = ~np.isnan(D["atr_prev"])
    cost = 2 * (COMMISSION + tick * pv)
    side = leg["side"]
    if leg["mode"] == "open":
        trig = leg["ok"] & ok_atr
        fill = o.copy()
    else:
        lvl = leg["level"]
        if leg["trig"] > 0:
            trig = leg["ok"] & (h >= lvl) & ok_atr
            fill = np.where(o > lvl, o, lvl)
        else:
            trig = leg["ok"] & (l <= lvl) & ok_atr
            fill = np.where(o < lvl, o, lvl)
    span = stop_k * D["atr_prev"]
    with np.errstate(invalid="ignore"):
        if side > 0:
            stop = fill - span
            hit = l <= stop
            snapped = np.where(o <= stop, o, stop)
        else:
            stop = fill + span
            hit = h >= stop
            snapped = np.where(o >= stop, o, stop)
        exit_px = c.copy()
        if tp_r:
            target = fill + side * tp_r * span
            reached = (h >= target) if side > 0 else (l <= target)
            exit_px = np.where(reached, target, exit_px)
        exit_px = np.where(hit, snapped, exit_px)   # a tie goes to the stop
        pnl = (exit_px - fill) * side * pv - cost
    return np.where(trig, pnl, 0.0), trig


def spec_bits(D, spec, legs=None):
    pv, tick = MARKETS[D["symbol"]][1], MARKETS[D["symbol"]][2]
    if legs is None:
        legs = spec_legs(D, spec)
    n = len(D["c"])
    pL, tL = leg_pnl(D, legs[0], spec["stop"], TP_R[spec["exit"]], pv, tick)
    pS, tS = leg_pnl(D, legs[1], spec["stop"], TP_R[spec["exit"]], pv, tick)
    if spec["trend"]:
        up = back(D["c"], 1) > back(D["sma50"], 1)
        pL, tL = np.where(up, pL, 0.0), tL & up
        pS, tS = np.where(~up, pS, 0.0), tS & ~up
    if spec["dir"] == "long":
        pS, tS = np.zeros(n), np.zeros(n, bool)
    elif spec["dir"] == "short":
        pL, tL = np.zeros(n), np.zeros(n, bool)
    at_open_L = np.zeros(n, bool)
    at_open_S = np.zeros(n, bool)
    if (tL & tS).any():
        legL, legS = legs
        if legL["mode"] == "stop":
            at_open_L = ((D["o"] >= legL["level"]) if legL["trig"] > 0
                         else (D["o"] <= legL["level"]))
        if legS["mode"] == "stop":
            at_open_S = ((D["o"] >= legS["level"]) if legS["trig"] > 0
                         else (D["o"] <= legS["level"]))
    sel_long = tL & (~tS | (at_open_L & ~at_open_S))
    sel_short = tS & (~tL | (at_open_S & ~at_open_L))
    pnl = np.where(sel_long, pL, 0.0) + np.where(sel_short, pS, 0.0)
    trig = sel_long | sel_short
    side = np.where(sel_long, 1, np.where(sel_short, -1, 0))
    return pnl, trig, side


def day_trade(D, i, spec, legs, pv, tick):
    """Scalar replay — the paper trader's version of the same rules."""
    if spec["dow"] == "mon" and D["dow"][i] != 0:
        return None
    if spec["dow"] == "fri" and D["dow"][i] != 4:
        return None
    o, h, l, c = (D[k][i] for k in ("o", "h", "l", "c"))
    atr = D["atr_prev"][i]
    if np.isnan(atr):
        return None
    p1c, s50 = D["c"][i - 1], D["sma50"][i - 1]
    if spec["gap"] == "with" and not o > p1c:
        return None
    if spec["gap"] == "against" and o > p1c:
        return None
    cands = []
    for side in ([1, -1] if spec["dir"] == "both"
                 else ([1] if spec["dir"] == "long" else [-1])):
        if spec["trend"]:
            if side > 0 and not p1c > s50:
                continue
            if side < 0 and not p1c < s50:
                continue
        leg = legs[0] if side > 0 else legs[1]
        if not bool(leg["ok"][i]):
            continue
        if leg["mode"] == "open":
            cands.append((side, o, True))
            continue
        lvl = leg["level"][i]
        if np.isnan(lvl):
            continue
        if leg["trig"] > 0:
            if h < lvl:
                continue
            cands.append((side, max(o, lvl), o >= lvl))
        else:
            if l > lvl:
                continue
            cands.append((side, min(o, lvl), o <= lvl))
    if not cands:
        return None
    if len(cands) == 1:
        side, fill, _ = cands[0]
    else:
        at_open = [x for x in cands if x[2]]
        if len(at_open) != 1:
            return None
        side, fill, _ = at_open[0]
    cost = 2 * (COMMISSION + tick * pv)
    span = spec["stop"] * atr
    stop = fill - side * span
    if side > 0:
        hit, snapped = l <= stop, min(o, stop)
    else:
        hit, snapped = h >= stop, max(o, stop)
    why, exit_px = "close", c
    tp_r = TP_R[spec["exit"]]
    if tp_r:
        target = fill + side * tp_r * span
        if (h >= target) if side > 0 else (l <= target):
            why, exit_px = "target", target
    if hit:
        why, exit_px = "stop", snapped
    return {"side": side, "entry": float(fill), "exit": float(exit_px), "why": why,
            "risk": float(span * pv), "usd": float((exit_px - fill) * side * pv - cost)}


# ------------------------------------------------------------------ sweep
def splits(D) -> dict:
    y = D["years"]
    return {"train": y <= TRAIN_LAST,
            "test": (y > TRAIN_LAST) & (y <= TEST_LAST),
            "recent": y > TEST_LAST}


def agg(pnl, trig, mask):
    m = trig & mask
    k = int(m.sum())
    if not k:
        return 0, 0.0, 0.0
    v = pnl[m]
    return k, float(v.sum()), 100.0 * float((v > 0).sum()) / k


def rows_of(D, floor_train=150, floor_test=100):
    """Every configuration in the space, with the ones that pass the first two gates kept."""
    sp = splits(D)
    mask_tr, mask_te, mask_re = sp["train"], sp["test"], sp["recent"]
    passed = []
    axis = {"family": {}, "stop": {}, "exit": {}, "gap": {}, "dow": {}, "trend": {}, "dir": {}}
    for fam in FAMILIES:
        for n in (FAM_N[fam] if fam in FAM_N else [None]):
            legs = spec_legs(D, {"family": fam, "n": n})
            for stop in STOPS:
                for ex in EXITS:
                    for trend in TRENDS:
                        for dirn in DIRS:
                            spec = {"family": fam, "n": n, "stop": stop, "exit": ex,
                                    "gap": "any", "trend": trend, "dow": "all", "dir": dirn}
                            pnl, trig, _ = spec_bits(D, spec, legs)
                            gap_up = D["o"] > back(D["c"], 1)
                            for gap in GAPS:
                                gmask = (np.ones(len(pnl), bool) if gap == "any"
                                         else (gap_up if gap == "with" else ~gap_up))
                                for dow in DOWS:
                                    dmask = (np.ones(len(pnl), bool) if dow == "all"
                                             else (D["dow"] == (0 if dow == "mon" else 4)))
                                    m = gmask & dmask
                                    tr = agg(pnl, trig, mask_tr & m)
                                    te = agg(pnl, trig, mask_te & m)
                                    re_ = agg(pnl, trig, mask_re & m)
                                    row = {"symbol": D["symbol"], "family": fam, "n": n,
                                           "stop": stop, "exit": ex, "gap": gap,
                                           "dow": dow, "trend": trend, "dir": dirn,
                                           "train": tr, "test": te, "recent": re_}
                                    for key, val in (("family", fam), ("stop", stop),
                                                     ("exit", ex), ("gap", gap), ("dow", dow),
                                                     ("trend", "on" if trend else "off"),
                                                     ("dir", dirn)):
                                        b = axis[key].setdefault(val, [0, []])
                                        b[0] += 1
                                        b[1].append(te[1])
                                    if (tr[0] >= floor_train and tr[1] > 0
                                            and te[0] >= floor_test and te[1] > 0):
                                        passed.append(row)
    return passed, axis


def neighbors(spec):
    out = []
    if spec["n"] is not None:
        k = LOOKBACKS.index(spec["n"]) if spec["n"] in LOOKBACKS else None
        if k is not None:
            out += [{**spec, "n": LOOKBACKS[j]} for j in (k - 1, k + 1)
                    if 0 <= j < len(LOOKBACKS)]
    k = STOPS.index(spec["stop"])
    out += [{**spec, "stop": STOPS[j]} for j in (k - 1, k + 1) if 0 <= j < len(STOPS)]
    k = EXITS.index(spec["exit"])
    out += [{**spec, "exit": EXITS[j]} for j in (k - 1, k + 1) if 0 <= j < len(EXITS)]
    return out


def test_net(D, spec) -> float:
    pnl, trig, _ = spec_bits(D, spec)
    return float(pnl[trig & spec_mask(D, spec) & splits(D)["test"]].sum())


def luck_test(D, spec, rng, runs) -> dict:
    """500 random fills on the same days, same side, same stop, same exit, same costs."""
    pv, tick = MARKETS[D["symbol"]][1], MARKETS[D["symbol"]][2]
    pnl, trig, side = spec_bits(D, spec)
    live = np.where(trig & spec_mask(D, spec) & splits(D)["test"])[0]
    if not len(live):
        return {"pct": 100.0, "observed": 0.0, "runs": 0}
    lo, hi = D["l"][live], D["h"][live]
    op, cl, atr = D["o"][live], D["c"][live], D["atr_prev"][live]
    sd = side[live]
    span = spec["stop"] * atr
    cost = 2 * (COMMISSION + tick * pv)
    tp_r = TP_R[spec["exit"]]
    obs = float(pnl[live].sum())
    k = len(live)
    nets = np.empty(runs)
    for r in range(runs):
        fill = lo + rng.random(k) * (hi - lo)
        stop = fill - sd * span
        hit = np.where(sd > 0, lo <= stop, hi >= stop)
        snapped = np.where(sd > 0, np.minimum(op, stop), np.maximum(op, stop))
        exit_px = cl.copy()
        if tp_r:
            target = fill + sd * tp_r * span
            reached = np.where(sd > 0, hi >= target, lo <= target)
            exit_px = np.where(reached, target, exit_px)
        exit_px = np.where(hit, snapped, exit_px)
        nets[r] = float(((exit_px - fill) * sd * pv - cost).sum())
    return {"pct": 100.0 * float((nets < obs).sum()) / runs, "observed": obs, "runs": runs}


# ------------------------------------------------------------------ the account
def trades_of(D, spec) -> list[dict]:
    pv, tick = MARKETS[D["symbol"]][1], MARKETS[D["symbol"]][2]
    legs = spec_legs(D, spec)
    out = []
    for i in range(2, len(D["c"])):
        t = day_trade(D, i, spec, legs, pv, tick)
        if t:
            out.append({**t, "date": D["dates"][i], "market": D["symbol"]})
    return out


def walk(trades, start_i=0):
    """$25,000 → +$1,250 with a $1,000 end-of-day trailing floor that locks at +$100."""
    eq = high = START
    days = []
    for k in range(start_i, len(trades)):
        eq += trades[k]["usd"]
        high = max(high, eq)
        floor = max(FLOOR, min(high - (START - FLOOR), LOCKED))
        if k == start_i or trades[k]["date"] != trades[k - 1]["date"]:
            days.append(0.0)
        days[-1] += trades[k]["usd"]
        if eq <= floor:
            return {"pass": False, "breach": True, "sessions": len(days), "eq": eq}
        if eq >= TARGET_EQ:
            best = max(days)
            return {"pass": True, "breach": False, "sessions": len(days), "eq": eq,
                    "consistency": 100 * best / (eq - START)}
    return {"pass": False, "breach": False, "unfinished": True, "sessions": len(days), "eq": eq}


def rolling(trades) -> dict:
    res = [walk(trades, i) for i in range(len(trades))]
    if not res:
        return {"starts": 0}
    passed = [r for r in res if r["pass"]]
    ok = [r for r in passed if r["consistency"] <= CONSISTENCY]
    done = [r for r in res if not r.get("unfinished")]
    fast = [r for r in ok if r["sessions"] <= 3]
    return {"starts": len(res), "pass_pct": 100 * len(passed) / len(res),
            "cons_pct": 100 * len(ok) / len(res),
            "breach_pct": 100 * sum(1 for r in done if r["breach"]) / max(len(done), 1),
            "p3_pct": 100 * len(fast) / len(res),
            "p5_pct": 100 * sum(1 for r in ok if r["sessions"] <= 5) / len(res),
            "p10_pct": 100 * sum(1 for r in ok if r["sessions"] <= 10) / len(res),
            "p15_pct": 100 * sum(1 for r in ok if r["sessions"] <= 15) / len(res),
            "med_sessions": statistics.median([r["sessions"] for r in ok]) if ok else None,
            "med_consistency": statistics.median([r["consistency"] for r in ok]) if ok else None}


def record(trades) -> dict:
    if not trades:
        return {"n": 0}
    usd = [t["usd"] for t in trades]
    eq = peak = dd = 0.0
    for u in usd:
        eq += u
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    days = {}
    for t in trades:
        days[t["date"]] = days.get(t["date"], 0.0) + t["usd"]
    return {"n": len(trades), "net": sum(usd), "per": sum(usd) / len(usd),
            "win": 100 * sum(1 for u in usd if u > 0) / len(usd), "dd": dd,
            "risk": statistics.median(t["risk"] for t in trades), "days": len(days),
            "best_day": max(days.values())}


def risk_per_session(trades, n=60) -> float:
    by_day = {}
    for t in trades:
        by_day[t["date"]] = by_day.get(t["date"], 0.0) + t["risk"]
    if not by_day:
        return 0.0
    return statistics.median([by_day[d] for d in sorted(by_day)[-n:]])


def combine(books) -> list[dict]:
    by_date = {}
    for b in books:
        for t in b:
            by_date.setdefault(t["date"], []).append(t)
    return [t for d in sorted(by_date) for t in by_date[d]]


def day_overlap(a, b) -> float:
    da, db = {t["date"] for t in a}, {t["date"] for t in b}
    return len(da & db) / max(len(da | db), 1)


def parity_check() -> str:
    """The new replay must reproduce the old one on the book that is live today."""
    D_new, D_old = prep("ES=F"), lab_prep("ES=F")
    spec = {"family": "nday_fade", "n": 5, "stop": 0.5, "exit": "tp1",
            "gap": "any", "trend": False, "dow": "all", "dir": "both", "symbol": "ES=F"}
    legs_new, legs_old = spec_legs(D_new, spec), lab_legs(D_old, spec)
    pv, tick = MARKETS["ES=F"][1], MARKETS["ES=F"][2]
    a = [(D_new["dates"][i], round(t["usd"], 2))
         for i in range(2, len(D_new["c"]))
         for t in [day_trade(D_new, i, spec, legs_new, pv, tick)] if t]
    b = [(D_old["dates"][i], round(t["usd"], 2))
         for i in range(2, len(D_old["c"]))
         for t in [lab_day_trade(D_old, i, spec, legs_old, pv, tick)] if t]
    if a == b:
        return f"parity OK — {len(a)} trades identical to the live replay"
    return (f"PARITY FAILED — {len(a)} vs {len(b)} trades, "
            f"first difference {next((x for x, y in zip(a, b) if x != y), 'length')}")


# ------------------------------------------------------------------ main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--markets", default="ES=F,NQ=F,GC=F,CL=F,NKD=F")
    ap.add_argument("--top", type=int, default=120, help="candidates per market through the gates")
    ap.add_argument("--runs", type=int, default=500)
    ap.add_argument("--legs", type=int, default=3, help="max rules in the book")
    ap.add_argument("--risk-cap", type=float, default=500.0,
                    help="median session risk the book may carry (buffer is $1,000)")
    ap.add_argument("--since", default="2023-01-01",
                    help="era the account is judged in — stops scale with price level")
    args = ap.parse_args()
    rng = np.random.default_rng(20261031)

    print("=" * 110)
    print(f"  WIDE SWEEP — {SPACE:,} configurations per market · one micro contract · "
          f"4 gates + the 25K account")
    print("=" * 110)
    pmsg = parity_check()
    print(f"  {pmsg}")
    if "FAILED" in pmsg:
        raise SystemExit("the new replay disagrees with the live one — refusing to mine")

    data, allpass, axes = {}, [], {}
    defs = {}
    for sym in [s for s in args.markets.split(",") if s]:
        D = prep(sym)
        data[sym] = D
        p, ax = rows_of(D)
        print(f"  {sym:7} {len(D['c']):5d} bars ({D['dates'][0]} → {D['dates'][-1]}) · "
              f"{SPACE:,} configs · {len(p):,} positive in train AND test")
        allpass += p
        axes[sym] = ax
        defs[sym] = dict(
            risk=float(np.nanmedian(D["atr_prev"][-252:]) * MARKETS[sym][1]),
            atr=float(np.nanmedian(D["atr_prev"][-252:])))
    if not data:
        raise SystemExit("no data")

    print(f"\n  {len(allpass):,} of {SPACE * len(data):,} passed the two-sample gate alone")

    gated = []
    for sym, D in data.items():
        ranked = sorted([r for r in allpass if r["symbol"] == sym],
                        key=lambda r: r["test"][1], reverse=True)[:args.top]
        kept = 0
        for r in ranked:
            spec = {k: r[k] for k in KEYS}
            nb = neighbors(spec)
            plateau = sum(1 for s2 in nb if test_net(D, s2) > 0) / max(len(nb), 1)
            if plateau < 4 / 6:
                continue
            if r["recent"][1] < 0 and r["recent"][0] >= 20:
                continue
            luck = luck_test(D, spec, rng, args.runs)
            if luck["pct"] < 95:
                continue
            kept += 1
            gated.append({**r, "spec": spec, "plateau": plateau, "luck": luck})
        print(f"  {sym:7} top {len(ranked)} through plateau/2025/luck → {kept} survived")

    expected = 0.05 * args.top * len(data)
    print(f"  chance alone would pass about {expected:.0f} of those "
          f"{args.top * len(data)} on a 95th-percentile luck gate")

    for g in gated:
        D = data[g["symbol"]]
        spec = {k: g["spec"][k] for k in KEYS}
        tr = trades_of(D, spec)
        g["trades"] = tr
        g["rec"] = record(tr)
        g["risk_now"] = risk_per_session(tr)
        g["acct"] = rolling(tr)
        # The stop is a property of the price level, so the account has to be judged in the
        # era whose prices it faces. NKD at a 0.75 ATR stop "passes 55%" of attempts only
        # because most of those attempts were made when the index was a fifth of today's
        # level; at today's volatility the same stop is $6,300 against a $1,000 buffer.
        rt = [t for t in tr if t["date"] >= args.since]
        g["trades_recent"] = rt
        g["rec_recent"] = record(rt)
        g["acct_recent"] = rolling(rt) if len(rt) >= 60 else {"starts": 0, "cons_pct": 0.0,
                                                             "med_sessions": None}

    cap = args.risk_cap
    pool = [g for g in gated
            if g["rec_recent"].get("n", 0) >= 100
            and g["risk_now"] <= cap
            and g["acct_recent"].get("starts")]
    # rank for speed with the consistency rule intact: fastest median pass, then the odds of
    # getting there inside three sessions, then the win rate the user asked for
    def score(g):
        a = g["acct_recent"]
        return (int(a["cons_pct"] >= 75), -(a["med_sessions"] or 999),
                a["p3_pct"], g["rec_recent"]["win"])
    pool.sort(key=score, reverse=True)
    if not pool:
        raise SystemExit(f"nothing survives the {cap:,.0f} session-risk cap in {args.since}+")

    def metrics(legs):
        tr = combine([l["trades_recent"] for l in legs]) if legs else []
        return (rolling(tr) if len(tr) >= 60 else {"starts": 0, "cons_pct": 0.0,
                                                   "med_sessions": None}), record(tr)

    # One leg is slower than three, three are riskier than one: build every prefix the cap
    # allows, then keep the fastest book that still clears the consistency rule.
    trials, book = [], []
    for g in pool:
        if len(book) >= args.legs:
            break
        if any(day_overlap(g["trades"], b["trades"]) >= 0.8 for b in book):
            continue
        if sum(b["risk_now"] for b in book) + g["risk_now"] > cap:
            continue
        book = book + [g]
        a, r = metrics(book)
        trials.append((list(book), a, r))
    ok = [t for t in trials if t[1]["cons_pct"] >= 75] or trials
    book, book_acct, book_rec = min(ok, key=lambda t: (t[1]["med_sessions"] or 999,
                                                       -t[1]["cons_pct"]))
    combined_full = combine([b["trades"] for b in book]) if book else []
    book_full = rolling(combined_full) if combined_full else {"starts": 0}

    print("\n" + "-" * 110)
    print(f"  {'market':7} {'rule':30}{'n':>5}{'win':>5}{'$/tr':>7}{'pass%':>7}{'cons%':>7}"
          f"{'≤3':>6}{'≤5':>6}{'breach':>8}{'sess→':>7}{'risk':>7}")
    for g in book:
        a, r = g["acct_recent"], g["rec_recent"]
        print(f"  {g['symbol']:7} {label(g['spec']):30}{r['n']:5d}{r['win']:4.0f}%"
              f"{r['per']:7,.0f}{a['pass_pct']:6.0f}%{a['cons_pct']:6.0f}%{a['p3_pct']:5.0f}%"
              f"{a['p5_pct']:5.0f}%{a['breach_pct']:7.0f}%{(a['med_sessions'] or 0):7.0f}"
              f"{g['risk_now']:7,.0f}")
    if book_acct.get("starts"):
        print(f"  BOOK: {book_rec['n']} trades, {book_rec['win']:.0f}% win, "
              f"${book_rec['per']:+,.0f}/trade, pass {book_acct['pass_pct']:.0f}%, "
              f"consistency {book_acct['cons_pct']:.0f}%, ≤3 sessions {book_acct['p3_pct']:.0f}%, "
              f"breach {book_acct['breach_pct']:.0f}%, median "
              f"{book_acct['med_sessions']:.0f} sessions")

    write_report(args, data, allpass, gated, pool, book, book_acct, book_rec, axes, defs,
                 pmsg, book_full)

    rows = []
    for g in book:
        spec = {k: g["spec"][k] for k in KEYS}
        rows.append({**spec, "symbol": g["symbol"], "market": MARKETS[g["symbol"]][0],
                     "test_net": round(g["test"][1], 2), "test_trades": g["test"][0],
                     "test_win": round(g["test"][2], 1),
                     "all_net": round(g["rec"]["net"], 2), "all_trades": g["rec"]["n"],
                     "all_win": round(g["rec"]["win"], 1),
                     "risk_now": round(g["risk_now"], 2),
                     "luck_pct": round(g["luck"]["pct"], 1),
                     "plateau": round(g["plateau"], 2),
                     "pass_pct": round(g["acct"]["pass_pct"], 1),
                     "cons_pct": round(g["acct"]["cons_pct"], 1),
                     "p3_pct": round(g["acct"]["p3_pct"], 1),
                     "breach_pct": round(g["acct"]["breach_pct"], 1)})
    MINE.write_text(json.dumps(rows, indent=2))
    print(f"\n  book → {MINE}  ({len(rows)} rules)")


def label(spec) -> str:
    n = "" if spec["n"] is None else f"-{spec['n']}"
    bits = [f"{spec['family']}{n}", f"{spec['stop']}A", spec["exit"]]
    if spec["gap"] != "any":
        bits.append(f"gap{spec['gap']}")
    if spec["dow"] != "all":
        bits.append(spec["dow"])
    if spec["trend"]:
        bits.append("trend")
    if spec["dir"] != "both":
        bits.append(spec["dir"])
    return " ".join(bits)


def write_report(args, data, allpass, gated, pool, book, book_acct, book_rec, axes, defs,
                 pmsg, book_full) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    n_cfg = SPACE * len(data)
    lines = [
        "# The wide sweep",
        "",
        f"Generated {stamp} · **{SPACE:,} configurations per market · {n_cfg:,} in total** · "
        "one micro contract · five markets",
        "",
        "Markets: " + ", ".join(f"{s} ({MARKETS[s][0]}, ${MARKETS[s][1]:g}/pt)"
                                for s in data) + ". Data 2009 → today, daily bars from Yahoo.",
        "",
        f"`{pmsg}` — the scalar replay that the paper trader uses reproduces the older "
        "replay trade-for-trade, so this sweep is measuring the same fills the desk trades.",
        "",
        "## The space, exactly",
        "",
        f"| axis | values |",
        "|---|---|",
        f"| rule families | {len(FAMILIES)}: " + ", ".join(FAMILIES) + " |",
        f"| lookbacks | {LOOKBACKS} (per family, where it takes one) |",
        f"| rule variants | {PAIRS} (lookback × family) |",
        f"| stops | {', '.join(str(s) + ' ATR' for s in STOPS)} |",
        f"| exits | {', '.join(e + (' (' + str(TP_R[e]) + 'R)' if TP_R[e] else '') for e in EXITS)} |",
        f"| filters | gap {GAPS} × day {DOWS} × 50-day trend {['off', 'on']} × direction {DIRS} "
        f"= {COMBOS} |",
        f"| per market | {PAIRS} × {len(STOPS)} × {len(EXITS)} × {COMBOS} = **{SPACE:,}** |",
        f"| in total | **{n_cfg:,}** |",
        "",
        "## Gates, and how many made it through each",
        "",
        "| gate | rule | survivors |",
        "|---|---|---|",
        f"| start | — | {n_cfg:,} |",
        f"| unseen years | positive in 2009-2019 **and** 2020-2024, ≥150 train and ≥100 test "
        f"trades | {len(allpass):,} |",
        f"| plateau | ≥4 of 6 parameter neighbours positive out of sample | "
        f"{len([g for g in gated if g['plateau'] >= 4 / 6]):,} |",
        f"| regime | 2025-2026 not negative | "
        f"{len([g for g in gated if g['recent'][1] >= 0 or g['recent'][0] < 20]):,} |",
        f"| luck | beats the 95th percentile of {args.runs} random fills on the same days, "
        f"same side, same stop, same exit | {len(gated):,} |",
        f"| sample | ≥100 trades across all history | {len(pool):,} |",
        "",
        f"At {args.top} candidates per market through the expensive gates, "
        f"**{len(gated)}** survived. Pure chance at a 95th-percentile luck gate would let "
        f"about **{0.05 * args.top * len(data):.0f}** through. "
        + ("So the survivors are at or below what luck alone produces — no claim of a "
           "population-wide edge is being made here."
           if len(gated) <= 0.05 * args.top * len(data) else
           "That is above chance, which is a reason to test forward, not a proof."),
        "",
        "## The book the sweep chose",
        "",
        "Ranked by **how often the $25,000 evaluation reaches +$1,250 inside three sessions "
        "with the 40% consistency rule intact**, not by net profit.",
        "",
        "| market | rule | stop | exit | trades | win | $/trade | pass% | with consistency "
        "| ≤3 sessions | ≤5 | breached | median sessions | risk/session |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for g in book:
        a, r, s = g["acct_recent"], g["rec_recent"], g["spec"]
        lines.append(
            f"| {g['symbol']} | {s['family']}{'' if s['n'] is None else '-' + str(s['n'])} "
            f"| {s['stop']}A | {s['exit']} | {r['n']} | {r['win']:.0f}% | ${r['per']:+,.0f} "
            f"| {a['pass_pct']:.0f}% | {a['cons_pct']:.0f}% | {a['p3_pct']:.0f}% "
            f"| {a['p5_pct']:.0f}% | {a['breach_pct']:.0f}% | {a['med_sessions'] or 0:.0f} "
            f"| ${g['risk_now']:,.0f} |")
    if book_acct.get("starts"):
        lines += ["", f"**Book, {args.since} onward** (the era whose prices this account "
                      f"faces): {book_rec['n']} trades, {book_rec['win']:.0f}% win, "
                      f"${book_rec['per']:+,.2f}/trade, worst drawdown ${book_rec['dd']:,.0f}. "
                      f"Walked from all {book_acct['starts']} starting trades: "
                      f"**pass {book_acct['pass_pct']:.0f}%**, "
                      f"**with consistency {book_acct['cons_pct']:.0f}%**, "
                      f"**inside 3 sessions {book_acct['p3_pct']:.1f}%**, inside 5 "
                      f"{book_acct['p5_pct']:.0f}%, inside 10 {book_acct['p10_pct']:.0f}%, "
                      f"inside 15 {book_acct['p15_pct']:.0f}%, breached "
                      f"{book_acct['breach_pct']:.0f}%, median "
                      f"{book_acct['med_sessions'] or 0:.0f} sessions to the target, "
                      f"median consistency {book_acct['med_consistency'] or 0:.0f}%.", "",
                      f"Full history (2009 onward), for reference: pass "
                      f"{book_full.get('pass_pct', 0):.0f}%, with consistency "
                      f"{book_full.get('cons_pct', 0):.0f}%, median "
                      f"{book_full.get('med_sessions') or 0:.0f} sessions, breach "
                      f"{book_full.get('breach_pct', 0):.0f}%. The older half of that "
                      "history was traded at a fifth of today's index prices, so it is the "
                      f"{args.since}+ row above that describes this account.", ""]

    lines += ["## The three-session question, answered with the numbers", ""]
    if book_acct.get("starts"):
        lines += [
            f"${TARGET_EQ - START:,.0f} in three sessions is ${(TARGET_EQ - START) / 3:,.0f} a "
            f"session, and one micro has to do it. Of the book's own history, the target was "
            f"reached inside three sessions from **{book_acct['p3_pct']:.1f}%** of starting "
            f"points with the consistency rule intact, and the floor was lost from "
            f"**{book_acct['breach_pct']:.0f}%** of attempts that finished.",
            "",
            "That is the honest trade: three sessions is a sprint that has to be paid for with "
            "risk, and on a $1,000 buffer the payment is the account. Read the row above as "
            "odds, not as a target to be aimed at.",
            ""]

    lines += ["## What the whole population says (losers included)", ""]
    for axis in ("family", "stop", "exit", "gap", "dow", "trend", "dir"):
        merged = {}
        for ax in axes.values():
            for k, (cnt, nets) in ax[axis].items():
                m = merged.setdefault(k, [0, []])
                m[0] += cnt
                m[1] += nets
        lines += [f"**{axis}**", "", "| value | configs | positive out of sample | median test $ |",
                  "|---|---|---|---|"]
        for k, (cnt, nets) in sorted(merged.items(), key=lambda kv: -statistics.median(kv[1][1])):
            pos = 100 * sum(1 for x in nets if x > 0) / len(nets)
            lines.append(f"| {k} | {cnt:,} | {pos:.0f}% | ${statistics.median(nets):+,.0f} |")
        lines.append("")

    if pool:
        lines += ["## Top of the pile, whatever the book took", "",
                  "| market | rule | trades | win | $/trade | pass% | cons% | ≤3 | luck | plateau | 2025+ $ |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for g in pool[:15]:
            r, a = g["rec_recent"], g["acct_recent"]
            lines.append(f"| {g['symbol']} | {label(g['spec'])} | {r['n']} | {r['win']:.0f}% "
                         f"| ${r['per']:+,.0f} | {a['pass_pct']:.0f}% | {a['cons_pct']:.0f}% "
                         f"| {a['p3_pct']:.0f}% | {g['luck']['pct']:.0f} | "
                         f"{g['plateau'] * 100:.0f}% | ${g['recent'][1]:+,.0f} |")
        lines.append("")

    lines += ["## What this cannot see", "",
              "Daily bars cannot order the events inside a session. When the stop and the "
              "target are both touched the fill code takes the stop, which is the pessimistic "
              "reading and the right one, but the true sequence could only be worse in ways "
              "the open already models. Slippage is one tick per side. A session that fills "
              "both a long and a short order is skipped unless the open already says which "
              "side, because the bar cannot say which filled first — taking only the good "
              "half of those days is exactly the look-ahead that once produced a 93% win rate "
              "on the prior-close rule.",
              "",
              "The luck gate is a 95th-percentile threshold, so it rejects 95% of strategies "
              "*with no edge* and still lets through 5%. With this many trials, one survivor "
              "is not evidence; a survivor that also trades well forward is.",
              "",
              f"Contract sizes matter more than win rates here: {', '.join(f'{s} one ATR = ${defs[s]['risk']:,.0f}' for s in defs)} "
              "at today's volatility. NKD is a $5/point contract on an index that moves "
              "hundreds of points a day — at 25K only its smallest stops are even reachable.",
              ""]
    REPORT.write_text("\n".join(lines))
    RAW.write_text(json.dumps({
        "generated": stamp, "space_per_market": SPACE, "configs": n_cfg,
        "passed_two_samples": len(allpass), "gated": len(gated), "pool": len(pool),
        "parity": pmsg,
        "book": [{"symbol": g["symbol"], "spec": {k: g["spec"][k] for k in KEYS},
                  "record": g["rec"], "account": g["acct"], "risk_now": g["risk_now"],
                  "luck": g["luck"], "plateau": g["plateau"]} for g in book],
        "book_account": book_acct, "book_record": book_rec,
        "survivors": [{k: v for k, v in g.items() if k not in ("trades",)} for g in pool[:60]],
    }, indent=2, default=str))

    # log the idea before it is believed
    with LOG.open("a") as fh:
        fh.write(f"\n## {stamp} — wide sweep: {n_cfg:,} configurations across five markets\n\n"
                 f"- space: {SPACE:,}/market ({PAIRS} rule variants x {len(STOPS)} stops x "
                 f"{len(EXITS)} exits x {COMBOS} filters)\n"
                 f"- gates: unseen years, plateau, 2025 regime, {args.runs}-run luck "
                 f"(same days/side/stop/exit), ≥100 trades\n"
                 f"- {len(allpass):,} positive in both halves, {len(gated)} through every gate "
                 f"(chance would pass ~{0.05 * args.top * len(data):.0f})\n"
                 f"- book: " + "; ".join(f"{g['symbol']} {label(g['spec'])}" for g in book) + "\n"
                 f"- book account: pass {book_acct.get('pass_pct', 0):.0f}%, with consistency "
                 f"{book_acct.get('cons_pct', 0):.0f}%, ≤3 sessions {book_acct.get('p3_pct', 0):.0f}%, "
                 f"breach {book_acct.get('breach_pct', 0):.0f}%, median "
                 f"{book_acct.get('med_sessions') or 0:.0f} sessions\n")
    print(f"  report → {REPORT}\n  raw → {RAW}")


if __name__ == "__main__":
    main()
