#!/usr/bin/env python3
"""A leg that trades every session: with the gap at the open, either side.

The book's prior-low limit fills about 44% of sessions, so some Mondays it does nothing. This
tests the alternative that cannot miss: at the open, take the direction of the gap (long if the
open is above yesterday's close, short if below), stop at k ATR, target at r R. Because the
entry is a market order at the open, the intraday high/low are causally legal here — the target
really does bind, unlike the close-resolved daily tests.

Scored the way the account keeps score: pass/blow over rolling 20-session windows, plus a random
side at the open with the same stop and target, so drift is paid out of the score.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import aggressive_eval as A
import edge_causal as E

ROOT = Path(__file__).resolve().parent
DESK = ROOT / "desk"
SYMS = {"ES=F": "ES_F_1d.csv", "GC=F": "GC_F_1d.csv",
        "CL=F": "CL_F_1d.csv", "NQ=F": "NQ_F_1d.csv"}
STOPS = (0.5, 1.0, 1.5, 2.0, 2.5)
TGTS = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0)
DRAWS, SEED = 500, 7


def pnl_vec(o, h, l, c, atr, side, stopk, tgt, mult, tick):
    entry = o
    risk = stopk * atr
    stop = entry - side * risk
    target = entry + side * tgt * risk
    adverse = np.where(side > 0, l <= stop, h >= stop)
    favour = np.where(side > 0, h >= target, l <= target)
    px = np.where(adverse, stop, np.where(favour, target, c))
    return (px - entry) * side * mult - (2 * E.COMM_SIDE + 2 * tick * mult)


def main() -> None:
    rows = []
    for sym, csv in SYMS.items():
        path = ROOT / "data" / csv
        if not path.exists():
            continue
        D = E.load_csv(str(path))
        mult, tick = E.SPECS[sym]["mult"], E.SPECS[sym]["tick"]
        o, h, l, c, atr = (np.asarray(D[k], float) for k in ("o", "h", "l", "c", "atr"))
        d = np.asarray(D["d"])
        pc = np.r_[np.nan, c[:-1]]
        idx = np.arange(21, D["n"])
        gap = o[idx] - pc[idx]
        side = np.sign(gap)
        ses = [x for x in d if x >= E.ERA]
        pos = {x: k for k, x in enumerate(ses)}
        # Score the same era the window sims use, so per-session and pass/blow agree.
        live = (side != 0) & (d[idx] >= E.ERA)
        idx, side = idx[live], side[live]
        fill = 100.0 * len(idx) / max(1, len(ses))
        last_atr = next(x for x in reversed(atr) if x > 0)
        print(f"  {sym}: {D['n']} bars, fires on {fill:.1f}% of sessions, ATR {last_atr:.2f}")
        for stopk in STOPS:
            for tgt in TGTS:
                raw = pnl_vec(o[idx], h[idx], l[idx], c[idx], atr[idx - 1], side,
                              stopk, tgt, mult, tick)
                ok = np.isfinite(raw)
                p = raw[ok]
                day = np.zeros(len(ses))
                for dt_, v in zip(d[idx][ok], p):
                    day[pos[dt_]] += v
                rng = np.random.default_rng(SEED)
                null = np.empty(DRAWS)
                for b in range(DRAWS):
                    s = rng.choice([-1.0, 1.0], size=len(idx))
                    pv = pnl_vec(o[idx], h[idx], l[idx], c[idx], atr[idx - 1], s,
                                 stopk, tgt, mult, tick)
                    null[b] = np.nanmean(pv)
                alpha = p.mean() - null.mean()
                t = alpha / null.std(ddof=1)
                e1, e2 = A.evaluate(day, 1, 20), A.evaluate(day, 2, 20)
                rows.append({"sym": sym, "stop": stopk, "tgt": tgt, "n": int(len(p)),
                             "win": 100 * (p > 0).mean(), "mean": float(p.mean()),
                             "per_sess": float(day.mean()), "alpha": float(alpha),
                             "t": float(t), "fill": fill, "stop_usd": stopk * last_atr * mult,
                             "pass1": e1["pass"], "blow1": e1["breach"], "net1": e1["net"],
                             "pass2": e2["pass"], "blow2": e2["breach"], "net2": e2["net"]})
    rows.sort(key=lambda r: (-r["net1"], -r["mean"]))
    L = ["# A leg that trades every session — with the gap at the open", "",
         f"120 settings: stop 0.5–2.5 ATR × target 0.5–3.0R, market entry at the open in the "
         f"direction of the gap, intraday stop/target, costs included. Null = random side at the "
         f"open, same bracket, {DRAWS} draws. Pass/blow over rolling 20-session windows.",
         "", "| contract | stop | target | trades | win | $/trade | $/session | stop $ | "
         "null alpha | t | pass x1 | blow x1 | net x1 | net x2 |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows[:24]:
        L.append(f"| {r['sym']} | {r['stop']}A | {r['tgt']}R | {r['n']} | {r['win']:.1f}% | "
                 f"{r['mean']:+.2f} | {r['per_sess']:+.2f} | {r['stop_usd']:.0f} | "
                 f"{r['alpha']:+.2f} | {r['t']:+.2f} | {r['pass1']:.1f}% | {r['blow1']:.1f}% | "
                 f"{r['net1']:+.1f} | {r['net2']:+.1f} |")
    L.append("")
    best = rows[0]
    L.append(f"Best by accounts won minus lost: **{best['sym']} {best['stop']}A stop, "
             f"{best['tgt']}R target** — {best['win']:.1f}% win, ${best['mean']:+.2f}/trade, "
             f"pass {best['pass1']:.1f}% / blow {best['blow1']:.1f}% at one micro, "
             f"alpha {best['alpha']:+.2f} (t {best['t']:+.2f}).")
    L.append("")
    Path(DESK / "open-desk.md").write_text("\n".join(L) + "\n")
    (DESK / "open-desk.json").write_text(json.dumps(rows, indent=1) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
