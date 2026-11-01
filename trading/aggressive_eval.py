#!/usr/bin/env python3
"""Score the whole space the way the account actually keeps score: pass versus blow.

The objective has changed. Expectancy ranks rules that make money slowly; this ranks
rules by how often an attempt ends in a funded account instead of a dead one, and it is
willing to lose some accounts along the way, as requested.

For every configuration and every size, this slides a window of H sessions across the
2023+ record, starts the account at $25,000 each time, and walks it day by day:

  * the floor follows the closing high-water mark and locks at $25,100 above $26,100;
  * the 40% consistency rule must hold on the day the target is reached;
  * whichever comes first, +$1,250 (a pass) or balance under the floor (a blow), decides
    that attempt.

The score is **net = pass% - breach%**: accounts won minus accounts lost. A rule with
net > 0 wins more evaluations than it burns, which is the only arithmetic answer to
"as long as we're earning way more accounts than losing."

A configuration is only counted at a size where one stop costs less than the buffer —
otherwise the first loss is the last trade, and the pass rate is fiction.

    python3 aggressive_eval.py --horizon 20
    python3 aggressive_eval.py --horizon 4 --top 25
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

import edge_causal as E
import sweep3 as S

ROOT = Path(__file__).resolve().parent
DESK = ROOT / "desk"
START, TARGET, BUFFER = E.START_BAL, E.TARGET, E.MAX_LOSS
LOCK_AT, LOCK_TRIG, CONS = E.LOCK_AT, E.LOCK_TRIGGER, E.CONSISTENCY
ERA = "2023-01-01"
SIZES = (1, 2, 3)
MIN_TRADES = 40
STOP_SHARE_CAP = 0.90          # one stop may not exceed 90% of the buffer


def evaluate(day_pnl: np.ndarray, size: int, horizon: int) -> dict | None:
    """Pass/blow rates over every H-session window, first event wins."""
    n = len(day_pnl)
    if n <= horizon:
        return None
    mat = np.lib.stride_tricks.sliding_window_view(day_pnl, horizon) * size
    bal = START + np.cumsum(mat, axis=1)
    peak = np.maximum.accumulate(bal, axis=1)
    floor = np.where(peak >= LOCK_TRIG, np.maximum(peak - BUFFER, LOCK_AT), peak - BUFFER)
    breach = bal < floor
    profit = bal - START
    largest = np.maximum.accumulate(mat, axis=1)
    hit = (profit >= TARGET) & (largest <= CONS * np.maximum(profit, 1e-9))

    b_any = breach.any(axis=1)
    p_any = hit.any(axis=1)
    b_idx = np.argmax(breach, axis=1)
    p_idx = np.argmax(hit, axis=1)
    passed = p_any & (~b_any | (p_idx <= b_idx))
    breached = b_any & (~p_any | (b_idx < p_idx))
    reached = hit.any(axis=1)          # hit +$1,250 at some point, consistency aside
    w = len(passed)
    return {"pass": 100 * passed.sum() / w, "breach": 100 * breached.sum() / w,
            "reached": 100 * reached.sum() / w, "windows": w,
            "net": 100 * (passed.sum() - breached.sum()) / w}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=20)
    ap.add_argument("--top", type=int, default=18)
    ap.add_argument("--symbols", default="ES=F,NQ=F")
    ap.add_argument("--out", default="desk/aggressive-eval.md")
    ap.add_argument("--min-stop", type=float, default=0.0,
                    help="ignore stops tighter than this; 0.25 ATR flatters close-based exits")
    a = ap.parse_args()

    rows = []
    for sym in [s.strip() for s in a.symbols.split(",") if s.strip()]:
        path = ROOT / "data" / S.CSV.get(sym, "")
        if not path.exists():
            continue
        D = E.load_csv(str(path))
        o, h, l, c = (np.array(D[k]) for k in "ohlc")
        atr = np.array(D["atr"])
        d = np.array(D["d"])
        mult, tick = E.SPECS[sym]["mult"], E.SPECS[sym]["tick"]
        e20, e50, e200 = S.ema(c, 20), S.ema(c, 50), S.ema(c, 200)
        r = S.rsi2(c)
        pc = np.r_[np.nan, c[:-1]]
        dow = np.array([__import__("datetime").date.fromisoformat(x).weekday() for x in d])
        trend_up = c > e200
        os_sessions = d >= ERA
        session_index = {x: i for i, x in enumerate(d[os_sessions])}
        last_atr = next(x for x in reversed(atr) if x > 0)
        print(f"  {sym}: {len(c)} bars")

        for name, lb, fired, entry, kind, side in S.variants(D, o, h, l, c, atr,
                                                             e20, e50, e200, r):
            for gap in S.GAPS:
                gmask = np.ones(len(c), bool)
                if gap == "with":
                    gmask = (o > pc) if side > 0 else (o < pc)
                elif gap == "against":
                    gmask = (o < pc) if side > 0 else (o > pc)
                for tname, use_trend in (("trend", False), ("counter", True)):
                    tmask = ~trend_up if use_trend else np.ones(len(c), bool)
                    for dname, wd in S.DOWS:
                        base = fired & gmask[21:] & tmask[21:]
                        if wd is not None:
                            base &= dow[21:] == wd
                        idx = np.where(base)[0] + 21
                        if len(idx) < MIN_TRADES:
                            continue
                        dates = d[idx]
                        if (dates >= ERA).sum() < MIN_TRADES:
                            continue
                        for stopk in S.STOPS:
                            if stopk < a.min_stop:
                                continue
                            risk = stopk * last_atr * mult
                            for ename, m in S.EXITS.items():
                                p = S.pnl(o, h, l, c, atr, idx, entry[idx - 21], kind, side,
                                          stopk, m, mult, tick)
                                day_pnl = np.zeros(int(os_sessions.sum()))
                                for dt, val in zip(dates, p):
                                    j = session_index.get(dt)
                                    if j is not None:
                                        day_pnl[j] += val
                                for size in SIZES:
                                    if risk * size > STOP_SHARE_CAP * BUFFER:
                                        continue
                                    ev = evaluate(day_pnl, size, a.horizon)
                                    if not ev:
                                        continue
                                    rows.append(dict(sym=sym, rule=f"{name}:{lb}", gap=gap,
                                                     trend=tname, dow=dname, stop=stopk,
                                                     exit=ename, size=size, risk=risk * size,
                                                     **ev))

    if not rows:
        print("nothing evaluated")
        return
    rows.sort(key=lambda r: (-r["net"], -r["pass"]))
    best = rows[0]

    L = [f"# Aggressive sizing: which attempts win accounts and which burn them", "",
         f"Every configuration from the wide sweep, scored on **evaluation outcome** over "
         f"rolling {a.horizon}-session windows from {ERA} onward, at 1, 2 and 3 micros. "
         f"Floor follows the closing high-water mark; the {CONS:.0%} consistency rule must "
         f"hold when the target is hit; first event — +${TARGET:,.0f} or breach — decides "
         f"the attempt. A size is only counted if one stop costs under "
         f"{STOP_SHARE_CAP:.0%} of the buffer.", "",
         f"**{len(rows):,} rule/size combinations evaluated.**", "",
         "| sym | rule | gap/trend/day | bracket | size | stop $ | pass | reached target | "
         "blow | **net** |", "|---|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in rows[:a.top]:
        L.append(f"| {r['sym']} | {r['rule']} | {r['gap']}/{r['trend']}/{r['dow']} | "
                 f"{r['stop']} ATR {r['exit']} | x{r['size']} | ${r['risk']:,.0f} | "
                 f"{r['pass']:.1f}% | {r['reached']:.1f}% | {r['breach']:.1f}% | "
                 f"**{r['net']:+.1f}%** |")

    pos = [r for r in rows if r["net"] > 0]
    L += ["", "## The headline", "",
          f"- best net score: **{best['net']:+.1f} points** — {best['sym']} {best['rule']} "
          f"{best['gap']}/{best['trend']}/{best['dow']} {best['stop']} ATR {best['exit']} "
          f"at x{best['size']} (pass {best['pass']:.1f}%, blow {best['breach']:.1f}%)",
          f"- combinations with net > 0 (win more accounts than they burn): "
          f"**{len(pos):,} of {len(rows):,}**",
          f"- the 'reached target' column is the tell: where it is far above 'pass', the "
          f"40% consistency rule — not the dollars — is refusing the pass.", ""]
    if pos:
        by_size = {}
        for r in pos:
            by_size.setdefault(r["size"], []).append(r["net"])
        L.append("| size | combinations with net > 0 | best net at that size |")
        L.append("|---:|---:|---:|")
        for size in sorted(by_size):
            L.append(f"| x{size} | {len(by_size[size]):,} | {max(by_size[size]):+.1f}% |")
        L.append("")
    L += ["_Net is accounts won minus accounts lost per attempt. A positive net is the only "
          "version of 'we win more than we lose' that survives arithmetic; a negative one "
          "means every additional account bought with size is a donation._", ""]

    DESK.mkdir(exist_ok=True)
    (ROOT / a.out).write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
