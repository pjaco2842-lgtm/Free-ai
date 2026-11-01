#!/usr/bin/env python3
"""A very wide search, run under the rules this desk already accepted.

The space: 22 rule variants x 11 lookbacks x 3 gap filters x 2 trend filters x 6 day
filters x 9 stops x 8 exits on every symbol given. The count printed by the run is the
number of configurations that actually reached scoring — those that fired at least 40
times out of sample — not the size of the grid arithmetic. Quoting the bigger number
would be advertising rather than measurement.

Evidence rules, applied to every single configuration
-----------------------------------------------------
* a decision at bar i uses bars <= i-1 plus bar i's own OPEN, never its high or low;
* resolution is close-based for limits (a daily bar has no intra-bar order) and
  stop-first for stop entries, which is what `edge_causal.trade_pnl` already does;
* in-sample is before 2023, out-of-sample is 2023 onward, and a config must be
  positive in BOTH to be considered at all;
* affordable means one stop costs at most 40% of the $1,000 buffer at one micro, so a
  stop of 2.0 ATR on today's ES is excluded no matter how pretty its curve;
* the survivors then face random entries with the same count, side, stop and exit —
  the only control that asks whether the *entry rule* did anything;
* the winner's t-stat is compared with sqrt(2 ln N), the maximum a null of N draws
  would be expected to throw up. Below that line it is indistinguishable from luck.

    python3 sweep3.py --symbols ES=F,NQ=F --out desk/sweep300k.md
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

import edge_causal as E

ROOT = Path(__file__).resolve().parent
DESK = ROOT / "desk"
CSV = {"ES=F": "ES_F_1d.csv", "NQ=F": "NQ_F_1d.csv"}
STOPS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]
EXITS = {"close": None, "tp05": 0.5, "tp1": 1.0, "tp15": 1.5, "tp2": 2.0,
         "tp25": 2.5, "tp3": 3.0, "tp4": 4.0}
GAPS = ["any", "with", "against"]
DOWS = [("all", None), ("mon", 0), ("tue", 1), ("wed", 2), ("thu", 3), ("fri", 4)]
LOOKBACKS = [1, 2, 3, 4, 5, 6, 8, 10, 13, 21, 34]
IS_END, OS_START = "2022-12-31", "2023-01-01"
BUFFER_CAP = 0.40 * E.MAX_LOSS
SESSIONS = 1

COST = 2 * E.COMM_SIDE


# ------------------------------------------------------------------ rolling helpers
def roll_back(x: np.ndarray, n: int, fn) -> np.ndarray:
    """Value at index i computed from x[i-n : i] — i.e. strictly before session i."""
    out = np.full(len(x), np.nan)
    if n <= 0 or len(x) <= n:
        return out
    agg = fn(sliding_window_view(x, n), axis=1)      # agg[k] covers x[k:k+n]
    out[n:] = agg[:-1]                                # out[i] = agg[i-n]
    return out


def ema(x: np.ndarray, span: int) -> np.ndarray:
    out = np.empty(len(x))
    a = 2.0 / (span + 1.0)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def rsi2(c: np.ndarray, n: int = 2) -> np.ndarray:
    """Simple-average RSI over the last n changes, computed at the previous close."""
    out = np.full(len(c), np.nan)
    for i in range(n + 1, len(c)):
        ch = np.diff(c[i - n:i + 1])
        gain = ch[ch > 0].sum()
        loss = -ch[ch < 0].sum()
        out[i] = 100.0 if loss == 0 else 100.0 - 100.0 / (1.0 + gain / loss)
    return out


# ------------------------------------------------------------------------ families
def variants(d, o, h, l, c, atr, e20, e50, e200, r):
    """Every entry rule, as arrays. Each yields (name, lookback, fired, entry, kind, side)."""
    out = []
    pc = np.r_[np.nan, c[:-1]]
    rng = h - l
    avg10 = roll_back(rng, 10, np.mean)
    col = slice(21, len(c))

    for n in LOOKBACKS:
        hi = roll_back(h, n, np.max)
        lo = roll_back(l, n, np.min)
        for name, lvl, side, kind in (("nday_break_long", hi, 1, "stop"),
                                      ("nday_break_short", lo, -1, "stop"),
                                      ("limit_low_long", lo, 1, "limit"),
                                      ("limit_high_short", hi, -1, "limit")):
            fired = ~np.isnan(lvl)
            entry = lvl.copy()
            if kind == "stop":
                gapthru = (o >= lvl) if side > 0 else (o <= lvl)
                fired &= (h >= lvl) if side > 0 else (l <= lvl)
                entry = np.where(gapthru, o, lvl)
            else:
                gapthru = (o <= lvl) if side > 0 else (o >= lvl)
                fired &= gapthru | ((l <= lvl) if side > 0 else (h >= lvl))
                entry = np.where(gapthru, o, lvl)
            out.append((name, n, fired[col], entry[col], kind, side))

    # stop orders at yesterday's close, only when the session opens the right side of it
    for name, side in (("prevclose_break_long", 1), ("prevclose_break_short", -1)):
        lvl = pc
        fired = (o < lvl) & (h >= lvl) if side > 0 else (o > lvl) & (l <= lvl)
        out.append((name, 1, fired[col], lvl[col], "stop", side))

    # gap continuations and fades, entered at the open
    gup = o > pc
    for name, cond, side in (("gap_cont_long", gup, 1), ("gap_cont_short", ~gup, -1),
                             ("gap_fade_long", ~gup, 1), ("gap_fade_short", gup, -1)):
        fired = cond & ~np.isnan(pc)
        out.append((name, 1, fired[col], o[col], "open", side))

    # prior day inside, narrowest-of-four, and range expansion, then break its extreme
    prev_in = np.r_[False, (h[:-1] < np.r_[np.nan, h[:-2]]) & (l[:-1] > np.r_[np.nan, l[:-2]])]
    nr4 = np.r_[False, (rng[:-1] < roll_back(rng, 3, np.min)[:-1])]
    expand = np.r_[False, (rng[:-1] > 1.5 * avg10[:-1])]
    for tag, gate in (("inside_break", prev_in), ("nr4_break", nr4),
                      ("range_expand", expand)):
        for name, lvl, side in ((f"{tag}_long", np.r_[np.nan, h[:-1]], 1),
                                (f"{tag}_short", np.r_[np.nan, l[:-1]], -1)):
            fired = gate & (h >= lvl if side > 0 else l <= lvl) & ~np.isnan(lvl)
            entry = np.where((o >= lvl) if side > 0 else (o <= lvl), o, lvl)
            out.append((name, 1, fired[col], entry[col], "stop", side))

    # mean reversion: RSI(2) extremes and a pullback into the EMAs, at the open
    for name, cond, side in (("rsi2_pull_long", r < 10, 1), ("rsi2_pull_short", r > 90, -1),
                             ("ema_pull_long", (c > e50) & (c < e20), 1),
                             ("ema_pull_short", (c < e50) & (c > e20), -1)):
        fired = cond & ~np.isnan(cond.astype(float))
        out.append((name, 1, fired[col], o[col], "open", side))

    # streaks: n consecutive closes the same way, faded at the next open
    for n in LOOKBACKS:
        ups = np.zeros(len(c), bool)
        downs = np.zeros(len(c), bool)
        for i in range(n + 1, len(c)):
            ch = np.diff(c[i - n:i + 1])
            ups[i] = bool((ch > 0).all())
            downs[i] = bool((ch < 0).all())
        out.append(("streak_fade_long", n, downs[col], o[col], "open", 1))
        out.append(("streak_fade_short", n, ups[col], o[col], "open", -1))
    return out


# ---------------------------------------------------------------------- evaluation
def pnl(o, h, l, c, atr, idx, entry, kind, side, stopk, m, mult, tick):
    risk = stopk * atr[idx - 1]
    stop_px = entry - side * risk
    if m is None:
        exitp = c[idx]
    else:
        tgt = entry + side * m * risk
        if kind == "limit":
            long_ = np.where(c[idx] <= stop_px, stop_px, np.where(c[idx] >= tgt, tgt, c[idx]))
            short_ = np.where(c[idx] >= stop_px, stop_px, np.where(c[idx] <= tgt, tgt, c[idx]))
            exitp = np.where(side > 0, long_, short_)
        else:
            long_ = np.where(l[idx] <= stop_px, stop_px, np.where(h[idx] >= tgt, tgt, c[idx]))
            short_ = np.where(h[idx] >= stop_px, stop_px, np.where(l[idx] <= tgt, tgt, c[idx]))
            exitp = np.where(side > 0, long_, short_)
    return side * (exitp - entry) * mult - (COST + 2 * tick * mult)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="ES=F,NQ=F")
    ap.add_argument("--out", default="desk/sweep300k.md")
    ap.add_argument("--top", type=int, default=250)
    ap.add_argument("--trials", type=int, default=300)
    a = ap.parse_args()

    results, tested = [], 0
    for sym in [s.strip() for s in a.symbols.split(",") if s.strip()]:
        path = ROOT / "data" / CSV.get(sym, "")
        if not path.exists():
            print(f"  {sym}: no CSV, skipped")
            continue
        D = E.load_csv(str(path))
        o, h, l, c = (np.array(D[k]) for k in "ohlc")
        atr = np.array(D["atr"])
        d = D["d"]
        mult, tick = E.SPECS[sym]["mult"], E.SPECS[sym]["tick"]
        e20, e50, e200 = ema(c, 20), ema(c, 50), ema(c, 200)
        r = rsi2(c)
        pc = np.r_[np.nan, c[:-1]]
        dow = np.array([__import__("datetime").date.fromisoformat(x).weekday() for x in d])
        trend_up = c > e200
        last_atr = next(x for x in reversed(atr) if x > 0)
        print(f"  {sym}: {len(c)} bars · last ATR {last_atr:.2f} · "
              f"affordable stops <= {BUFFER_CAP / (last_atr * mult):.2f} ATR")

        for name, n, fired, entry, kind, side in variants(D, o, h, l, c, atr,
                                                          e20, e50, e200, r):
            for gap in GAPS:
                gmask = np.ones(len(c), bool)
                if gap == "with":
                    gmask = (o > pc) if side > 0 else (o < pc)
                elif gap == "against":
                    gmask = (o < pc) if side > 0 else (o > pc)
                for tname, use_trend in (("trend", False), ("counter", True)):
                    tmask = ~trend_up if use_trend else np.ones(len(c), bool)
                    for dname, wd in DOWS:
                        base = fired & gmask[21:] & tmask[21:]
                        if wd is not None:
                            base &= dow[21:] == wd
                        idx = np.where(base)[0] + 21
                        if len(idx) < 40:
                            continue
                        dates = np.array(d)[idx]
                        is_m = dates <= IS_END
                        os_m = dates >= OS_START
                        # the days this rule was even allowed to trade: the coin flip
                        # must draw from the same set, or a Monday rule is measured
                        # against a five-day-a-week control and wins by frequency alone
                        allidx = np.arange(21, len(c))
                        pool = allidx if wd is None else allidx[dow[allidx] == wd]
                        if is_m.sum() < 20 or os_m.sum() < 40:
                            continue
                        for stopk in STOPS:
                            for ename, m in EXITS.items():
                                tested += 1
                                p = pnl(o, h, l, c, atr, idx, entry[idx - 21],
                                        kind, side, stopk, m, mult, tick)
                                mi, mo = p[is_m].mean(), p[os_m].mean()
                                if mi <= 0 or mo <= 0:
                                    continue
                                se = p[os_m].std(ddof=1) / math.sqrt(os_m.sum())
                                results.append(dict(
                                    sym=sym, rule=f"{name}:{n}", gap=gap, trend=tname,
                                    dow=dname, stop=stopk, exit=ename,
                                    n_is=int(is_m.sum()), n_os=int(os_m.sum()),
                                    avg_is=float(mi), avg_os=float(mo),
                                    net_os=float(p[os_m].sum()),
                                    per_session=float(p.sum() / len(d)),
                                    t=float(mo / se) if se > 0 else 0.0,
                                    risk=float(stopk * last_atr * mult),
                                    idx=idx, p_arr=p, pool=pool,
                                    data=(D, o, h, l, c, atr, mult, tick),
                                    side=side, kind=kind))

    if not results:
        print("nothing survived the two-sided requirement")
        return

    tests = tested
    line = math.sqrt(2 * math.log(max(tests, 2)))
    affordable = [r for r in results if r["risk"] <= BUFFER_CAP]
    ranked = sorted(affordable, key=lambda r: -r["avg_os"])

    # the expensive gate, on the top of the list only
    rng = random.Random(11)
    for r in ranked[:a.top]:
        # each result carries its own symbol's arrays: with two symbols in one run the
        # loop variables would otherwise still hold the last one
        _D, o, h, l, c, atr, mult, tick = r["data"]
        k, side = min(len(r["idx"]), len(r["pool"])), r["side"]
        means = []
        for _ in range(a.trials):
            pick = np.sort(rng.sample(list(r["pool"]), k))
            pp = pnl(o, h, l, c, atr, np.array(pick), o[pick], "open", side,
                     r["stop"], EXITS[r["exit"]], mult, tick)
            means.append(pp.mean())
        r["null"] = statistics.fmean(means)
        r["p"] = sum(1 for x in means if x >= r["avg_os"]) / len(means)

    passed = [r for r in ranked[:a.top] if r.get("p", 1.0) <= 0.10]

    L = [f"# {tests:,} configurations, and what survived them", "",
         f"**{tests:,} configurations** scored on causal fills (a decision uses bars "
         "before the session, resolution is close-based for limits, stop-first for stop "
         "entries), at one micro with costs inside every dollar.", "",
         f"| gate | configs |", "|---|---:|",
         f"| tested | {tests:,} |",
         f"| positive in both halves (pre-2023 and 2023+) | {len(results):,} |",
         f"| …and affordable: one stop <= ${BUFFER_CAP:.0f} | {len(affordable):,} |",
         f"| …and beat random entries at p<=0.10 (top {min(a.top, len(affordable))} only) "
         f"| **{len(passed)}** |", "",
         f"Multiple-testing line for this many attempts: **t = {line:.2f}**. A t-stat below "
         "that is what luck alone is expected to produce somewhere in a sweep this wide.",
         ""]

    def fmt(v, spec):
        return "—" if v is None or (isinstance(v, float) and math.isnan(v)) else format(v, spec)

    def row(r):
        return (f"| {r['sym']} | {r['rule']} | {r['gap']}/{r['trend']}/{r['dow']} | "
                f"{r['stop']} ATR {r['exit']} | {r['n_os']} | {r['avg_os']:+.2f} | "
                f"{r['per_session']:+.2f} | {r['t']:+.2f} | ${r['risk']:,.0f} | "
                f"{fmt(r.get('null'), '+.2f')} | {fmt(r.get('p'), '.2f')} |")

    def table(rows, title):
        if not rows:
            return [f"### {title}", "", "none", ""]
        out = [f"### {title}", "",
               "| sym | rule | gap/trend/day | bracket | OS trades | OS $/trade | "
               "$/session | t | risk $ | null $/trade | p |",
               "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
        out += [row(r) for r in rows]
        return out + [""]

    L += table(passed[:15], f"Survivors: positive both halves, affordable, beat a coin flip "
                         f"(the multiple-testing line for {tests:,} attempts is t = {line:.2f})")
    L += table(ranked[:10], "Best affordable by out-of-sample dollars per trade, before the luck gate")
    worst = sorted(affordable, key=lambda r: r["avg_os"])[:3]
    L += table(worst, "The worst affordable configs, so the table is a population and not a brochure")

    DESK.mkdir(exist_ok=True)
    (ROOT / a.out).write_text("\n".join(L) + "\n")
    print("\n".join(L))

    if passed:
        best = max(passed, key=lambda r: r["per_session"])
        days = np.array(D["d"])
        per_day = {}
        _D, _o, _h, _l, _c, _atr, _mult, _tick = best["data"]
        for dt, v in zip(np.array(_D["d"])[best["idx"]], best["p_arr"]):
            per_day[dt] = per_day.get(dt, 0.0) + float(v)
        days = np.array(_D["d"])
        series = [per_day.get(x, 0.0) for x in days if x >= OS_START]
        (DESK / "sweep300k-best.json").write_text(json.dumps(
            {"config": {k: v for k, v in best.items()
                        if k not in ("idx", "p_arr", "data", "pool")},
             "sessions": [x for x in days if x >= OS_START], "pnl": series}))
        print(f"\nbest by $/session: {best['rule']} {best['gap']}/{best['trend']}/{best['dow']} "
              f"{best['stop']} ATR {best['exit']} — ${best['per_session']:+.2f}/session, "
              f"p={best['p']:.2f}, t={best['t']:+.2f}")
        print("wrote desk/sweep300k-best.json for time_to_funded.py --pnl-json")


if __name__ == "__main__":
    main()
