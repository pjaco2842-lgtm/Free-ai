#!/usr/bin/env python3
"""
The 26,000-strategy test, run honestly.

What this replicates
--------------------
A widely shared video describes testing ~26,000 variants and finding 29 survivors.
The method is the valuable part:

  1. train on old years, score on years the rule never saw
  2. the winner must beat random entries with the *same stop and exit* — a coin flip
     with a different stop is not a fair coin flip
  3. parameter plateau: if it works at 40 but not 39 or 41, it is a coincidence
  4. check the recent regime separately (2025 on), because old edges go flat

Rules that this file enforces on itself, because a backtest lies in the details
-----------------------------------------------------------------------------
* **One position per market per session.** If a day would fill both a long and a
  short order, which filled first is unknowable from a daily bar, so the day is
  skipped in both the sweep and the forward record. (The first version booked both
  and the vector/scalar check caught it.)
* **Yesterday's ATR.** The stop is sized from the ATR known before the session; the
  first version used the bar's own ATR, which is information from the future.
* **Two implementations, cross-checked.** The vectorised sweep and the scalar
  day-by-day replay used by the paper trader must agree over 17 years or the run
  fails loudly (it did, first time).
* **The whole population is reported**, including the configs that lost, or the
  "which axis works" tables are just a list of winners.

What this cannot see
--------------------
The video's edge is "break out early in the day, tight stop, hold to the close".
Free intraday history is 7 days at 1m and 60 days at 15m, so 17 years of it does not
exist here. The daily-bar version: a stop order at a level derived from prior days
(prior high, N-day extreme, a gap), filled at that level — or at the open if the
session gapped through it — stop intraday, exit at the close. Same rules, coarser
clock, and fills are mildly optimistic: the level is assumed to trade at the level.

    python3 trading/lab26k.py
    python3 trading/lab26k.py --symbols NQ=F,ES=F --runs 500
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lab import COMMISSION, atr_series, fetch_daily  # noqa: E402
from scanner import sma  # noqa: E402
from scalp import MARKETS  # noqa: E402

HERE = Path(__file__).resolve().parent
DESK = HERE / "desk"
BOOK = DESK / "oracle-book.json"
SAFE_BOOK = DESK / "oracle-safe.json"
REPORT = DESK / "oracle26k.md"
RAW = DESK / "oracle26k.json"

LOOKBACKS = [1, 2, 5, 10, 20]
STOPS = [0.25, 0.5, 0.75, 1.0, 1.5]
DIRS = ["both", "long", "short"]
GAPS = ["any", "with", "against"]
TRENDS = [False, True]
EXITS = ["close", "tp1", "tp2"]
DOWS = ["all", "mon", "fri"]
TP_R = {"close": None, "tp1": 1.0, "tp2": 2.0}

N_FAMILIES = ["nday_break", "nday_fade", "nr_break", "gap_cont", "gap_fade", "ma_pull"]
FAMILIES = N_FAMILIES + ["inside_break", "trendday_cont", "trendday_fade",
                         "prevclose_break", "vol_expand_break"]
PAIRS = len(FAMILIES) + len(N_FAMILIES) * (len(LOOKBACKS) - 1)
SPACE = PAIRS * len(STOPS) * len(EXITS) * len(GAPS) * len(TRENDS) * len(DOWS) * len(DIRS)

TRAIN_LAST = 2019
TEST_FIRST, TEST_LAST = 2020, 2024
KEYS = ("family", "n", "stop", "exit", "gap", "trend", "dow", "dir")


# ------------------------------------------------------------------ plumbing
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
    """x[i-k], NaN where it does not exist. Every lag in this file goes through here."""
    out = np.full(len(x), np.nan)
    if k < len(x):
        out[k:] = x[:-k]
    return out


def prep(symbol: str) -> dict:
    bars = fetch_daily(symbol)
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
    return D


def spec_legs(D: dict, spec: dict) -> tuple[dict, dict]:
    """Two orders, long-side and short-side: side, trigger direction, level, ok mask."""
    fam, n = spec["family"], spec["n"]
    o, h, l, c = D["o"], D["h"], D["l"], D["c"]
    p1h, p1l, p1c, p1o = back(h, 1), back(l, 1), back(c, 1), back(o, 1)
    p1rng, p1atr = back(D["rng"], 1), back(D["atr"], 1)
    s20, s50 = back(D["sma20"], 1), back(D["sma50"], 1)
    p2h, p2l = back(h, 2), back(l, 2)
    allok = ~np.isnan(p1h)

    if fam == "nday_break":
        ok = ~np.isnan(D["hiN"][n])
        legL = dict(mode="stop", side=1, trig=1, level=D["hiN"][n], ok=ok)
        legS = dict(mode="stop", side=-1, trig=-1, level=D["loN"][n], ok=ok.copy())
    elif fam == "nday_fade":
        legL = dict(mode="stop", side=1, trig=-1, level=D["loN"][n],
                    ok=~np.isnan(D["loN"][n]))
        legS = dict(mode="stop", side=-1, trig=1, level=D["hiN"][n],
                    ok=~np.isnan(D["hiN"][n]))
    elif fam == "nr_break":
        narrow = np.zeros(len(c), bool)
        for i in range(n, len(c)):
            narrow[i] = D["rng"][i - 1] <= D["rng"][i - n:i].min()
        ok = narrow & allok
        legL = dict(mode="stop", side=1, trig=1, level=p1h, ok=ok)
        legS = dict(mode="stop", side=-1, trig=-1, level=p1l, ok=ok.copy())
    elif fam == "inside_break":
        ok = (p1h <= p2h) & (p1l >= p2l) & allok
        legL = dict(mode="stop", side=1, trig=1, level=p1h, ok=ok)
        legS = dict(mode="stop", side=-1, trig=-1, level=p1l, ok=ok.copy())
    elif fam in ("trendday_cont", "trendday_fade"):
        up = (p1c > p1o) & (p1rng > 1.2 * p1atr) & ((p1c - p1o) > 0.6 * p1rng) & allok
        dn = (p1c < p1o) & (p1rng > 1.2 * p1atr) & ((p1o - p1c) > 0.6 * p1rng) & allok
        if fam == "trendday_cont":
            legL = dict(mode="stop", side=1, trig=1, level=p1h, ok=up)
            legS = dict(mode="stop", side=-1, trig=-1, level=p1l, ok=dn)
        else:
            legL = dict(mode="stop", side=1, trig=1, level=p1h, ok=dn)
            legS = dict(mode="stop", side=-1, trig=-1, level=p1l, ok=up)
    elif fam in ("gap_cont", "gap_fade"):
        trend_up, trend_dn = p1c > back(c, 1 + n), p1c < back(c, 1 + n)
        gap_up, gap_dn = o > p1c, o < p1c
        okb = ~np.isnan(p1c)
        if fam == "gap_cont":
            legL = dict(mode="open", side=1, trig=1, level=None, ok=okb & gap_up & trend_up)
            legS = dict(mode="open", side=-1, trig=-1, level=None, ok=okb & gap_dn & trend_dn)
        else:
            legL = dict(mode="open", side=1, trig=1, level=None, ok=okb & gap_dn)
            legS = dict(mode="open", side=-1, trig=-1, level=None, ok=okb & gap_up)
    elif fam == "ma_pull":
        okL = (p1c > s50) & (p1l <= s20) & allok
        okS = (p1c < s50) & (p1h >= s20) & allok
        legL = dict(mode="stop", side=1, trig=1, level=p1h, ok=okL)
        legS = dict(mode="stop", side=-1, trig=-1, level=p1l, ok=okS)
    elif fam == "prevclose_break":
        legL = dict(mode="stop", side=1, trig=1, level=p1c, ok=allok)
        legS = dict(mode="stop", side=-1, trig=-1, level=p1c, ok=allok.copy())
    elif fam == "vol_expand_break":
        ok = (p1rng < 0.6 * p1atr) & allok
        legL = dict(mode="stop", side=1, trig=1, level=p1h, ok=ok)
        legS = dict(mode="stop", side=-1, trig=-1, level=p1l, ok=ok.copy())
    else:
        raise SystemExit(f"unknown family {fam}")
    return legL, legS


def spec_mask(D: dict, spec: dict) -> np.ndarray:
    """Day-level filters: gap alignment and day of week. Trend is side-aware, in spec_bits."""
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


def leg_pnl(D: dict, leg: dict, stop_k: float, tp_r: float | None,
            pv: float, tick: float) -> tuple[np.ndarray, np.ndarray]:
    o, h, l, c = D["o"], D["h"], D["l"], D["c"]
    ok_atr = ~np.isnan(D["atr_prev"])      # no stop size, no trade
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
        exit_px = np.where(hit, snapped, exit_px)      # pessimistic: stop wins a tie
        pnl = (exit_px - fill) * side * pv - cost
    return np.where(trig, pnl, 0.0), trig


def spec_bits(D: dict, spec: dict, legs: tuple[dict, dict] | None = None):
    """(pnl, trig, side) for the whole series. The single source of the rules."""
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

    conflict = tL & tS
    at_open_L = np.zeros(n, bool)
    at_open_S = np.zeros(n, bool)
    if conflict.any():
        # A session can fill both orders. Which filled first is unknowable from a daily
        # bar, and taking only the days that ran one way is look-ahead — the first
        # version did exactly that and produced a 93% win rate on 153 trades, which is
        # the fingerprint of a rule that trades the days it already knows the answer to.
        # The one resolution knowable at the entry price is which side the open was
        # already beyond, so use that, and skip the day when the open says neither.
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


def spec_pnl(D: dict, spec: dict, legs=None):
    pnl, trig, _ = spec_bits(D, spec, legs)
    return pnl, trig


def day_trade(D: dict, i: int, spec: dict, legs: tuple[dict, dict],
              pv: float, tick: float) -> dict | None:
    """Scalar version of the same rules, used by the forward paper trader.

    Kept separate on purpose: `verify` replays the whole series both ways, so any drift
    between the sweep and the paper record shows up instead of quietly redefining what
    is being traded.
    """
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

    cands: list[tuple[int, float]] = []
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
        # both orders would fill: keep the side the open was already beyond, else skip
        at_open = [c for c in cands if c[2]]
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
def agg(pnl: np.ndarray, trig: np.ndarray, mask: np.ndarray) -> dict:
    m = trig & mask
    n = int(m.sum())
    if not n:
        return {"trades": 0, "net": 0.0, "win": 0.0, "dd": 0.0}
    vals = pnl[m]
    eq = np.cumsum(vals)
    return {"trades": n, "net": float(vals.sum()),
            "win": 100.0 * float((vals > 0).sum()) / n,
            "dd": float((eq - np.maximum.accumulate(eq)).min())}


def splits(D: dict) -> dict:
    y = D["years"]
    return {"train": y <= TRAIN_LAST,
            "test": (y > TRAIN_LAST) & (y <= TEST_LAST),
            "recent": y > TEST_LAST}


def sweep(D: dict, floor_train: int = 100, floor_test: int = 60):
    """Returns (all configs, configs that passed the sample and unseen-year floors)."""
    sp = splits(D)
    pv = MARKETS[D["symbol"]][1]
    sess = {k: len({D["dates"][i] for i in np.where(m)[0]}) for k, m in sp.items()}
    legcache = {(fam, n): spec_legs(D, {"family": fam, "n": n})
                for fam in FAMILIES for n in (LOOKBACKS if fam in N_FAMILIES else [None])}

    allrows: list[dict] = []
    passed: list[dict] = []
    for fam in FAMILIES:
        for n in (LOOKBACKS if fam in N_FAMILIES else [None]):
            legs = legcache[(fam, n)]
            for stop in STOPS:
                for ex in EXITS:
                    for gap in GAPS:
                        for dow in DOWS:
                            for trend in TRENDS:
                                for dirn in DIRS:
                                    spec = {"family": fam, "n": n, "stop": stop, "exit": ex,
                                            "gap": gap, "dow": dow, "trend": trend, "dir": dirn}
                                    pnl, trig = spec_pnl(D, spec, legs)
                                    mask = spec_mask(D, spec)
                                    tr = agg(pnl, trig, mask & sp["train"])
                                    te = agg(pnl, trig, mask & sp["test"])
                                    re_ = agg(pnl, trig, mask & sp["recent"])
                                    row = {"symbol": D["symbol"], **spec, "train": tr,
                                           "test": te, "recent": re_,
                                           "sessions_test": sess["test"]}
                                    allrows.append(row)
                                    if (tr["trades"] >= floor_train and tr["net"] > 0
                                            and te["trades"] >= floor_test and te["net"] > 0):
                                        # risk per stop at *current* volatility, not the
                                        # 17-year average: a 1 ATR stop was $176 on NQ in
                                        # 2009 and is $1,155 today, and only the second
                                        # number decides whether the buffer survives.
                                        row["med_risk"] = float(
                                            spec["stop"] * np.nanmedian(D["atr_prev"][-252:]) * pv)
                                        passed.append(row)
    return allrows, passed


def neighbors(spec: dict) -> list[dict]:
    out = []
    if spec["n"] is not None:
        k = LOOKBACKS.index(spec["n"])
        out += [{**spec, "n": LOOKBACKS[j]} for j in (k - 1, k + 1)
                if 0 <= j < len(LOOKBACKS)]
    k = STOPS.index(spec["stop"])
    out += [{**spec, "stop": STOPS[j]} for j in (k - 1, k + 1) if 0 <= j < len(STOPS)]
    k = EXITS.index(spec["exit"])
    out += [{**spec, "exit": EXITS[j]} for j in (k - 1, k + 1) if 0 <= j < len(EXITS)]
    return out


def test_net(D: dict, spec: dict) -> float:
    pnl, trig = spec_pnl(D, spec)
    return float(pnl[trig & splits(D)["test"]].sum())


def luck_test(D: dict, spec: dict, rng: np.random.Generator, runs: int) -> dict:
    """Same days, same side, same stop, same exit, same costs — only the fill price is random.

    Randomising the *day* is too easy to beat (any momentum entry beats buying the open
    on a random day), so this asks the sharper question: on the days this rule traded,
    did its level get a better outcome than a random fill inside the same day's range?
    """
    pv, tick = MARKETS[D["symbol"]][1], MARKETS[D["symbol"]][2]
    sp = splits(D)
    mask = spec_mask(D, spec)
    pnl, trig, side = spec_bits(D, spec)
    live = np.where(trig & mask & sp["test"])[0]
    observed = float(pnl[live].sum())
    k = len(live)
    if not k:
        return {"pct": 100.0, "observed": observed, "runs": 0, "beat_all": False}
    lo, hi = D["l"][live], D["h"][live]
    op, cl, atr = D["o"][live], D["c"][live], D["atr_prev"][live]
    sd = side[live]
    span = spec["stop"] * atr
    cost = 2 * (COMMISSION + tick * pv)
    tp_r = TP_R[spec["exit"]]
    nets = []
    for _ in range(runs):
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
        nets.append(float(((exit_px - fill) * sd * pv - cost).sum()))
    nets.sort()
    return {"pct": 100.0 * sum(1 for x in nets if x < observed) / len(nets),
            "observed": observed, "runs": len(nets), "beat_all": observed > nets[-1]}


def verify(D: dict, spec: dict) -> tuple[float, float]:
    pv, tick = MARKETS[D["symbol"]][1], MARKETS[D["symbol"]][2]
    legs = spec_legs(D, spec)
    pnl, trig = spec_pnl(D, spec, legs)
    mask = spec_mask(D, spec)
    vec = float(pnl[trig & mask].sum())
    scalar = 0.0
    for i in range(2, len(D["c"])):
        t = day_trade(D, i, spec, legs, pv, tick)
        if t:
            scalar += t["usd"]
    return vec, scalar


def pick_book(gated: list[dict], data: dict, top: int) -> list[dict]:
    """One rule per row: dedupe by the sessions a config actually trades.

    Deduping on results only catches exact copies. The 5-day fade at a 0.75 ATR stop and
    the same fade at 0.5 ATR take *the same trades* with different stops, so they are one
    position sized twice — two micros of exposure the account never chose. Two configs
    whose trade days overlap 90% or more are treated as one.
    """
    out: list[dict] = []
    taken: list[set[int]] = []
    for g in gated:
        D = data[g["symbol"]]
        _, trig = spec_pnl(D, g["spec"])
        days = set(np.where(trig & spec_mask(D, g["spec"]))[0].tolist())
        if not days:
            continue
        if any(len(days & t) / len(days | t) >= 0.9 for t in taken):
            continue
        taken.append(days)
        out.append({**g["spec"], "symbol": g["symbol"],
                    "test_net": round(g["test"]["net"], 2),
                    "test_trades": g["test"]["trades"],
                    "test_win": round(g["test"]["win"], 1),
                    "med_risk": round(float(g.get("med_risk", 0.0)), 2),
                    "luck_pct": round(g["luck"]["pct"], 1),
                    "plateau": round(g["plateau"], 2)})
        if len(out) >= top:
            break
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="NQ=F")
    ap.add_argument("--risk-cap", type=float, default=250.0,
                    help="per-stop dollars a buffer-safe variant may risk")
    ap.add_argument("--exclude-family", default="",
                    help="families kept out of the main book, comma separated")
    ap.add_argument("--pin", default="",
                    help="force one config into the book as family:n, e.g. nr_break:2")
    ap.add_argument("--runs", type=int, default=500)
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--candidates", type=int, default=60,
                    help="how many top configs go through the luck test (it is the pricey gate)")
    args = ap.parse_args()

    rng = np.random.default_rng(20261029)
    print("=" * 96)
    print(f"  THE 26,000 TEST — {SPACE:,} configurations · one micro contract")
    print("=" * 96)

    data, allrows, passed = {}, [], []
    for sym in [s for s in args.symbols.split(",") if s]:
        try:
            D = prep(sym)
        except Exception as err:  # noqa: BLE001
            print(f"  {sym}: data unavailable ({err})")
            continue
        data[sym] = D
        a, p = sweep(D)
        print(f"  {sym}: {len(D['c'])} bars ({D['dates'][0]} → {D['dates'][-1]}) · "
              f"{SPACE:,} configs · {len(p):,} positive in train AND test")
        allrows += a
        passed += p
    if not data:
        raise SystemExit("no data")

    # gates, cheapest first
    ranked = sorted(passed, key=lambda r: r["test"]["net"], reverse=True)[:args.candidates]
    gated = []
    for r in ranked:
        spec = {k: r[k] for k in KEYS}
        D = data[r["symbol"]]
        nb = neighbors(spec)
        plateau = sum(1 for s2 in nb if test_net(D, s2) > 0) / max(len(nb), 1)
        if plateau < 4 / 6:
            continue
        if not (r["recent"]["net"] >= 0 or r["recent"]["trades"] == 0):
            continue
        luck = luck_test(D, spec, rng, args.runs)
        if luck["pct"] < 95:
            continue
        gated.append({**r, "spec": spec, "plateau": plateau, "luck": luck})

    tested_top = len(ranked)
    print(f"\n  {len(passed):,} positive in both halves → top {tested_top} sent through the "
          f"luck plateau/2025 gates → {len(gated)} survived all of them")
    if tested_top:
        print(f"  chance alone would pass about {0.05 * tested_top:.0f} of those "
              f"{tested_top} on a 95th-percentile luck gate")

    excluded = {f.strip() for f in args.exclude_family.split(",") if f.strip()}
    book_pool = [g for g in gated if g["spec"]["family"] not in excluded]
    if args.pin:
        # Ranking cannot express "the narrow-range one": nr_break with n=1 out-earns n=2
        # but is the prior-day rule renamed, so a spec has to be named, not inferred.
        fam, _, num = args.pin.partition(":")
        want = int(num) if num else None
        book_pool = [g for g in book_pool
                     if g["spec"]["family"] == fam and g["spec"]["n"] == want]
    book = pick_book(book_pool, data, args.top)
    print(f"  book families: {', '.join(sorted({b['family'] for b in book})) or 'none'}"
          + (f" (excluded: {', '.join(sorted(excluded))})" if excluded else ""))

    # The account this is for has a $1,000 end-of-day buffer, so a "best net" book whose
    # stop is $1,155 a trade has already failed before it starts. This is the same search
    # with the sizing constraint applied first, ranked by win rate instead of net.
    safe_pool = sorted([g for g in gated
                        if g.get("med_risk", 9e9) <= args.risk_cap
                        and g["test"]["trades"] >= 100],
                       key=lambda g: (-g["test"]["win"], -g["test"]["net"]))
    safe = pick_book(safe_pool, data, args.top)
    unvalidated = False
    if not book:
        unvalidated = True
        for r in ranked[:args.top]:
            book.append({**{k: r[k] for k in KEYS}, "symbol": r["symbol"],
                         "test_net": round(r["test"]["net"], 2),
                         "test_trades": r["test"]["trades"],
                         "luck_pct": None, "unvalidated": True})

    checks = []
    for b in book:
        spec = {k: b[k] for k in KEYS}
        vec, scalar = verify(data[b["symbol"]], spec)
        checks.append({"symbol": b["symbol"], "vector": round(vec, 2),
                       "scalar": round(scalar, 2), "match": abs(vec - scalar) < 1.0})
    print("  sweep vs scalar replay: " + "; ".join(
        f"{c['symbol']} {c['vector']:+,.0f} / {c['scalar']:+,.0f} "
        f"{'OK' if c['match'] else 'MISMATCH'}" for c in checks))
    if not all(c["match"] for c in checks):
        raise SystemExit("the sweep and the paper replay disagree — refusing to write a book")

    yearly = []
    for b in book:
        spec = {k: b[k] for k in KEYS}
        D = data[b["symbol"]]
        pnl, trig = spec_pnl(D, spec)
        row = {"label": f"{spec['family']}{'' if spec['n'] is None else '-' + str(spec['n'])} "
                        f"{spec['stop']}A {spec['exit']} {spec['dir']}",
               "symbol": spec and b["symbol"]}
        for yy in sorted(set(D["years"])):
            m = (D["years"] == yy) & trig
            row[str(yy)] = [round(float(pnl[m].sum())), int(m.sum())]
        yearly.append(row)

    BOOK.parent.mkdir(parents=True, exist_ok=True)
    BOOK.write_text(json.dumps(book, indent=2))
    SAFE_BOOK.write_text(json.dumps(safe, indent=2))
    if safe:
        print("  buffer-safe challenger (win rate first):")
        for b in safe:
            print(f"    {b['family']}-{b['n']} {b['stop']}A {b['exit']} {b['dir']}: "
                  f"{b['test_trades']} trades, {b['test_win']:.0f}% win, "
                  f"${b['test_net']:+,.0f}, risk ${b['med_risk']:,.0f}/stop")

    # ---------------------------------------------------------------- report
    def by(key):
        groups: dict[str, list[float]] = {}
        for r in allrows:
            groups.setdefault(str(key(r)), []).append(r["test"]["net"])
        return {k: {"n": len(v),
                    "pct": 100 * sum(1 for x in v if x > 0) / len(v),
                    "median": statistics.median(v)} for k, v in groups.items()}

    lines = ["# The 26,000-strategy test", "",
             f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')} · "
             f"{SPACE:,} configurations per market · one micro contract", "",
             f"Train ≤ {TRAIN_LAST} · test {TEST_FIRST}-{TEST_LAST} · recent "
             f"{TEST_LAST + 1} onward.", "",
             "Fill model: a stop at a derived level fills at the level, or at the open when the "
             "session gapped through it; stop intraday from the previous session's ATR; exit at "
             "the close or a fixed R target; $1.24/side plus one tick of slippage per side. If a "
             "session would fill both a long and a short order, the day is skipped — the daily "
             "bar cannot say which filled first.", "",
             "## Gates", "",
             "| gate | rule | why |", "|---|---|---|",
             "| unseen years | positive in train AND test | two good years are not an edge |",
             "| sample | ≥100 train trades, ≥60 test trades | a handful of trades is noise |",
             "| plateau | ≥4 of 6 parameter neighbours positive | 40 but not 39 is a coincidence |",
             "| regime | 2025 onward not negative | old edges go flat |",
             f"| luck | beats the 95th percentile of {args.runs} random fills on the same days, same side, same stop | a coin flip with different rules is not a coin flip |",
             "", "## Survivors", ""]

    if gated:
        lines += ["| market | family | n | stop | exit | dir | gap | trend | dow | train $ | test $ | trades | win | luck pct | plateau | 2025+ $ |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for g in gated[:15]:
            s = g["spec"]
            lines.append(f"| {g['symbol']} | {s['family']} | {s['n']} | {s['stop']}A | {s['exit']} "
                         f"| {s['dir']} | {s['gap']} | {'yes' if s['trend'] else 'no'} | {s['dow']} "
                         f"| ${g['train']['net']:+,.0f} | ${g['test']['net']:+,.0f} "
                         f"| {g['test']['trades']} | {g['test']['win']:.0f}% "
                         f"| {g['luck']['pct']:.0f} | {g['plateau'] * 100:.0f}% "
                         f"| ${g['recent']['net']:+,.0f} |")
    else:
        lines += [f"**None of the top {tested_top} configs passed every gate.** "
                  f"{len(passed):,} of {SPACE * len(data):,} were positive in both halves — "
                  "about what chance produces at this many trials — but each failed a plateau, "
                  "lost to random fills on its own days, or went flat in 2025.", "",
                  "That is the video's conclusion reproduced: a good in-sample number is not an "
                  "edge. The book below holds the top scorers marked `unvalidated` so they can be "
                  "watched forward, not trusted."]

    if safe:
        lines += ["", "## Buffer-safe challenger — win rate first", "",
                  f"Same sweep, but only configs whose median stop is ≤ ${args.risk_cap:,.0f} — "
                  "so a normal losing run fits inside the $1,000 buffer — ranked by "
                  "out-of-sample win rate instead of net profit.", "",
                  "| market | family | n | stop | exit | dir | trades | win | net $ | median risk/stop |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for b in safe:
            lines.append(f"| {b['symbol']} | {b['family']} | {b['n']} | {b['stop']}A | {b['exit']} "
                         f"| {b['dir']} | {b['test_trades']} | {b['test_win']:.0f}% "
                         f"| ${b['test_net']:+,.0f} | ${b['med_risk']:,.0f} |")

    lines += ["", "## What the whole population says", "",
              f"All {len(allrows):,} configurations, including the losers — otherwise this is "
              "just a list of winners. `positive` is the share with a positive test result.", ""]
    for title, table in (("Exit style", by(lambda r: r["exit"])),
                         ("Stop distance", by(lambda r: r["stop"])),
                         ("Gap alignment", by(lambda r: r["gap"])),
                         ("Trend filter", by(lambda r: "on" if r["trend"] else "off")),
                         ("Day of week", by(lambda r: r["dow"])),
                         ("Family", by(lambda r: r["family"]))):
        lines += [f"**{title}**", "", "| value | configs | positive | median test $ |",
                  "|---|---|---|---|"]
        for k, v in sorted(table.items(), key=lambda kv: -kv[1]["median"]):
            lines.append(f"| {k} | {v['n']} | {v['pct']:.0f}% | ${v['median']:+,.0f} |")
        lines.append("")

    lines += ["## Year by year for the book", ""]
    years_all = sorted({k for y in yearly for k in y if k.isdigit()})
    lines += ["| market | rule | " + " | ".join(years_all) + " |",
              "|---|---|" + "---|" * len(years_all)]
    for y in yearly:
        cells = []
        for yy in years_all:
            v = y.get(yy)
            cells.append("—" if not v else f"${v[0]:+,.0f} ({v[1]})")
        lines.append(f"| {y['symbol']} | {y['label']} | " + " | ".join(cells) + " |")

    lines += ["", "## Replay check", "",
              "The vectorised sweep and the scalar replay the paper trader uses must agree.",
              "", "| market | sweep | scalar replay | match |", "|---|---|---|---|"]
    for c in checks:
        lines.append(f"| {c['symbol']} | ${c['vector']:+,.0f} | ${c['scalar']:+,.0f} | "
                     f"{'yes' if c['match'] else '**NO**'} |")
    lines += ["", f"{len(passed):,} configurations were positive in both halves out of "
                  f"{SPACE * len(data):,} tested. With this many trials, some win by chance; "
                  "the plateau and luck gates exist to throw those out, and the number that "
                  "survives them is the honest answer to \"how many real edges are in here\".", ""]

    # log every idea before it is believed (desk rule: count the variations out loud)
    log = HERE / "paper" / "research-log.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    book_names = "; ".join(f"{b['family']}-{b['n']} {b['stop']}A {b['exit']} {b['dir']}"
                           for b in book)
    with log.open("a") as fh:
        fh.write(f"\n## {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')} — "
                 f"{SPACE:,}-config sweep on {', '.join(data)}\n"
                 f"- gates: unseen years, plateau, 2025 regime, {args.runs}-run luck\n"
                 f"- {len(passed):,} positive in both halves, {len(gated)} through all gates\n"
                 f"- paper book: {book_names}\n")

    REPORT.write_text("\n".join(lines))
    RAW.write_text(json.dumps({"space": SPACE, "both_halves": len(passed),
                               "gated": len(gated), "book": book, "yearly": yearly,
                               "checks": checks}, indent=2, default=str))
    print(f"  book   → {BOOK}\n  report → {REPORT}")


if __name__ == "__main__":
    main()
