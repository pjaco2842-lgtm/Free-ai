#!/usr/bin/env python3
"""Does a high-win-rate setting beat a weekday-matched random long entry?

Win rate alone proves nothing: any long entry wins often in a market that drifts up. The
control is a random entry on the same weekdays, same stop, same target, long only, so the
drift is paid out of the score. Alpha is rule mean minus null mean; t is alpha over the
spread of the null means across draws. With two settings tested the bar is t > 2.12.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np

import edge_causal as E

ROOT = Path(__file__).resolve().parent
DESK = ROOT / "desk"
DRAWS, SEED = 200, 7


def analyze(csv, sym, stopk, tgt, label):
    D = E.load_csv(str(ROOT / "data" / csv))
    mult, tick = E.SPECS[sym]["mult"], E.SPECS[sym]["tick"]
    o, c, d = D["o"], D["c"], D["d"]
    keep = [i for i in range(21, D["n"]) if o[i] > c[i - 1]]
    vals = []
    for i in keep:
        p = E.trade_pnl(D, i, o[i], "open", stopk, tgt, mult, tick, "proven")
        if p is not None and np.isfinite(p):
            vals.append((d[i], p))
    r = np.array([p for _, p in vals])
    dow = np.array([dt.date.fromisoformat(x).weekday() for x in d])
    days = [dt.date.fromisoformat(x).weekday() for x, _ in vals]
    buckets = {}
    for k in range(5):
        v = np.where((dow == k))[0]
        v = v[v >= 21]
        if len(v):
            buckets[k] = v
    rng = np.random.default_rng(SEED)
    nm, nw = np.empty(DRAWS), np.empty(DRAWS)
    for b in range(DRAWS):
        pv = []
        for k in days:
            j = int(rng.choice(buckets[k]))
            p = E.trade_pnl(D, j, o[j], "open", stopk, tgt, mult, tick, "proven")
            if p is not None and np.isfinite(p):
                pv.append(p)
        pv = np.array(pv)
        nm[b], nw[b] = pv.mean(), 100 * (pv > 0).mean()
    alpha = r.mean() - nm.mean()
    t = alpha / nm.std(ddof=1)
    return {"label": label, "sym": sym, "n": len(r), "win": 100 * (r > 0).mean(),
            "mean": r.mean(), "null_mean": nm.mean(), "null_win": nw.mean(),
            "alpha": alpha, "t": t}


rows = [analyze("NQ_F_1d.csv", "NQ=F", 2.0, 0.1, "78.5% win, 0.1R target, 2.0 ATR stop"),
        analyze("CL_F_1d.csv", "CL=F", 1.0, 0.1, "82.8% win, 0.1R target, 1.0 ATR stop")]

L = ["# Does the high win rate survive the drift control?", "",
     "Random long entries on the same weekdays, same stop, same target, 200 draws. "
     "Alpha = rule − null. Bar for two settings: t > 2.12.", "",
     "| setting | trades | win | $/trade | null win | null $/trade | alpha | t | clears? |",
     "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
for r in rows:
    L.append(f"| {r['sym']} {r['label']} | {r['n']} | {r['win']:.1f}% | {r['mean']:+.2f} | "
             f"{r['null_win']:.1f}% | {r['null_mean']:+.2f} | {r['alpha']:+.2f} | {r['t']:+.2f} | "
             f"{'yes' if r['t'] > 2.12 else 'no'} |")
L.append("")
L.append("The null's win rate is the answer: most of a high win rate is the drift every long "
         "position collects, not the rule.")
L.append("")
Path(DESK / "null-check.md").write_text("\n".join(L) + "\n")
print("\n".join(L))
