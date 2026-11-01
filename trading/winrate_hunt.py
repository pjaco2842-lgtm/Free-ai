#!/usr/bin/env python3
"""Win rate is a dial, not a discovery. Turn it and watch what it costs.

The ask is always the same shape: "make the win rate 70-80%, I don't care about the risk."
Win rate is set by geometry, not by skill — shrink the target against the stop and the win rate
goes up mechanically, because the price now has to travel less to pay you. That is why the dial
is worth measuring rather than arguing about: the same rule is swept across a 0.1R-3.0R target
grid at five stops, and every setting is reported with the three numbers that decide whether it
is tradeable:

  * win rate;
  * dollars per trade at one micro, costs included, so the target has to outrun friction;
  * how many micros it takes to make $500 in a session, and therefore what one stop costs as a
    share of the $1,000 buffer.

A setting that cannot make $500 a session at any size the buffer allows is not a strategy for
this account, however high its win rate. Close resolution for limit entries (the proven engine):
the stop is only triggered by a close through it, which flatters tight stops.

    python3 winrate_hunt.py
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import numpy as np

import aggressive_eval as A
import edge_causal as E

ROOT = Path(__file__).resolve().parent
DESK = ROOT / "desk"
SYMS = {"ES=F": "ES_F_1d.csv", "GC=F": "GC_F_1d.csv",
        "CL=F": "CL_F_1d.csv", "NQ=F": "NQ_F_1d.csv"}
FAMS = ("limit_low", "prevclose_break", "nr_break", "open_gap")
LBS = (1, 3, 5)
STOPS = (0.5, 1.0, 1.5, 2.0, 2.5)
TGTS = tuple(round(0.1 * i, 1) for i in range(1, 31))
GAPS = ("any", "with")
MIN_N = 40
DAY_GOAL = 500.0
BUFFER = E.MAX_LOSS


def entries(D, fam, lb, gap):
    """Every entry this rule would take, once, so the target grid can reuse it."""
    out = []
    for i in range(21, D["n"]):
        sig = E.signal(D, i, fam, lb, gap)
        if sig:
            out.append((i, sig[0], sig[1]))
    return out


def score(D, ent, stopk, tgt, mult, tick):
    pnls = []
    for i, entry, kind in ent:
        p = E.trade_pnl(D, i, entry, kind, stopk, tgt, mult, tick, "proven")
        if p is not None:
            pnls.append((D["d"][i], p))
    if len(pnls) < MIN_N:
        return None
    v = [p for _, p in pnls]
    win = 100.0 * sum(1 for x in v if x > 0) / len(v)
    return {"n": len(v), "win": win, "mean": statistics.fmean(v), "net": sum(v),
            "trades": pnls}


def day_series(D, trades):
    """One number per session from ERA onward, zero on days the rule did not trade."""
    by = {}
    for d, p in trades:
        by[d] = by.get(d, 0.0) + p
    days = [d for d in D["d"] if d >= E.ERA]
    return np.array([by.get(d, 0.0) for d in days], float), days


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=20)
    ap.add_argument("--out", default="desk/winrate-hunt.md")
    a = ap.parse_args()

    rows = []
    for sym, csv in SYMS.items():
        path = ROOT / "data" / csv
        if not path.exists():
            continue
        D = E.load_csv(str(path))
        mult, tick = E.SPECS[sym]["mult"], E.SPECS[sym]["tick"]
        last_atr = next(x for x in reversed(D["atr"]) if x > 0)
        print(f"  {sym}: {D['n']} bars, ATR {last_atr:.2f}")
        for fam in FAMS:
            for lb in LBS:
                if fam == "open_gap" and lb != 1:
                    continue
                for gap in GAPS:
                    ent = entries(D, fam, lb, gap)
                    if len(ent) < MIN_N:
                        continue
                    for stopk in STOPS:
                        for tgt in TGTS:
                            s = score(D, ent, stopk, tgt, mult, tick)
                            if not s:
                                continue
                            ds, days = day_series(D, s["trades"])
                            per_sess = ds.mean()
                            need = DAY_GOAL / per_sess if per_sess > 0 else None
                            stop_d = need * stopk * last_atr * mult if need else None
                            rows.append({
                                "sym": sym, "fam": fam, "lb": lb, "gap": gap,
                                "stop": stopk, "tgt": tgt, "n": s["n"], "win": s["win"],
                                "mean": s["mean"], "net": s["net"],
                                "sessions": len(days), "per_sess": per_sess,
                                "need_micros": need, "stop_share": stop_d / BUFFER if stop_d else None,
                                "day_pnl": ds,
                            })
    print(f"  scored {len(rows)} settings")

    # The dial, on the desk's own rule, so the trade-off is one clean row per target.
    dial = [r for r in rows if r["sym"] == "ES=F" and r["fam"] == "limit_low" and r["lb"] == 1
            and r["gap"] == "any" and r["stop"] == 1.0]
    dial.sort(key=lambda r: r["tgt"])

    def best(pred):
        c = [r for r in rows if pred(r)]
        return max(c, key=lambda r: r["win"]) if c else None

    top_win = best(lambda r: True)
    win_pos = best(lambda r: r["mean"] > 0)
    win_70 = best(lambda r: r["win"] >= 70 and r["mean"] > 0)
    win_70_fit = best(lambda r: r["win"] >= 70 and r["mean"] > 0
                      and r["need_micros"] is not None and r["stop_share"] <= 1.0)

    # Account outcome for the interesting ones, at the size each would need.
    for r in rows:
        size = 2
        r["at2"] = A.evaluate(r["day_pnl"], size, a.horizon)
    for r in (top_win, win_pos, win_70, win_70_fit):
        if r:
            r["fit"] = A.evaluate(r["day_pnl"], max(1, round(r["need_micros"] or 1)), a.horizon)

    L = []
    L.append("# Win rate is a dial — measured, 2026-11-01")
    L.append("")
    L.append(f"Every setting below is one rule family swept over a 0.1R–3.0R target grid at five "
             f"stops, on daily bars, costs included (commission + a tick of slippage a side), "
             f"close resolution. {len(rows)} settings scored. "
             f"`need` = micros required to earn ${DAY_GOAL:.0f} in the average session at that "
             f"setting; `stop share` = one stop at that size as a share of the ${BUFFER:.0f} buffer.")
    L.append("")
    L.append("## The dial: ES prior-low limit, 1.0 ATR stop, target from 0.2R to 3.0R")
    L.append("")
    L.append("| target | trades | win | $/trade | $/session | micros for $500 | stop share | pass@x2 | blow@x2 |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in dial:
        need = "—" if r["need_micros"] is None else f"x{r['need_micros']:.0f}"
        share = "—" if r["stop_share"] is None else f"{100*r['stop_share']:.0f}%"
        at2 = r.get("at2") or {}
        L.append(f"| {r['tgt']:.1f}R | {r['n']} | {r['win']:.1f}% | {r['mean']:+.2f} | "
                 f"{r['per_sess']:+.2f} | {need} | {share} | "
                 f"{at2.get('pass', float('nan')):.1f}% | {at2.get('breach', float('nan')):.1f}% |")
    L.append("")

    def block(title, r, note):
        L.append(f"## {title}")
        L.append("")
        if not r:
            L.append(note)
            L.append("")
            return
        L.append(note)
        L.append("")
        L.append(f"**{r['sym']} {r['fam']} lb{r['lb']} gap={r['gap']}, {r['stop']} ATR stop, "
                 f"{r['tgt']:.1f}R target** — {r['n']} trades, **{r['win']:.1f}% win rate**, "
                 f"${r['mean']:+.2f}/trade, ${r['per_sess']:+.2f}/session.")
        if r["need_micros"]:
            L.append(f"To earn ${DAY_GOAL:.0f} in the average session: **x{r['need_micros']:.0f} "
                     f"micros**, whose single stop is **{100*r['stop_share']:.0f}%** of the "
                     f"${BUFFER:.0f} buffer"
                     + ("" if r["stop_share"] <= 1 else " — one losing trade ends the account") + ".")
        else:
            L.append("It cannot earn $500 in a session at any size: the average session is zero or "
                     "negative.")
        f = r.get("fit") or {}
        if f:
            L.append(f"Traded at that required size over {f['windows']} rolling {a.horizon}-session "
                     f"windows: pass {f['pass']:.1f}%, blow {f['breach']:.1f}%, "
                     f"reached target {f['reached']:.1f}%, **net {f['net']:+.1f}**.")
        a2 = r.get("at2") or {}
        if a2:
            L.append(f"At the honest x2: pass {a2['pass']:.1f}%, blow {a2['breach']:.1f}%, "
                     f"net {a2['net']:+.1f}.")
        L.append("")

    block("Highest win rate in the whole sweep", top_win,
          "Ignoring money entirely, this is as high as the win rate goes.")
    block("Highest win rate that still makes money", win_pos,
          "The dial turned as far as it goes without the dollars turning negative.")
    block("Highest win rate at or above 70% that still makes money", win_70,
          "The ask, taken literally: 70%+ and positive expectancy.")
    block("...and the best of those that the $1,000 buffer can actually carry", win_70_fit,
          "Same, restricted to settings whose required size does not risk the whole buffer on one stop.")

    Path(ROOT / a.out).write_text("\n".join(L) + "\n")
    (DESK / "winrate-hunt.json").write_text(json.dumps(
        [{k: v for k, v in r.items() if k != "day_pnl"} for r in rows], indent=1) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
