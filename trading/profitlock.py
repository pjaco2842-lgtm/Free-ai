#!/usr/bin/env python3
"""Does a good day deserve a smaller desk? Two policies, measured, not assumed.

The idea from the owner: after a session like +$634, trade less and be safer rather than
pressing a good hand. That is not obviously an improvement -- fewer entries is also a
slower walk to the target -- so it gets the same treatment as every other idea here.

Policy 1, a session profit lock. Once the book's realised profit in a session reaches $L,
no further leg enters that session. The open-gap leg trades at the open and the limit legs
wait for a dip, so the lock is applied in that order; each leg takes at most one trade a
session, which is exactly what the live runner does.

Policy 2, a cooldown. After a session that made $T, the whole book stands down for the
next K sessions.

Both are applied on top of the $300 dollar-stop cap already in force (riskcap.py), and
scored the way the account scores them: the end-of-day trailing floor, the $25,100 lock and
the 50% consistency rule the account actually carries.

    python3 profitlock.py            # lock table, cooldown table, after-a-big-day study
    python3 profitlock.py --selftest # sequencing arithmetic only, no data

Paper only. Nothing here writes a ledger.
"""
from __future__ import annotations

import argparse
import statistics

import edge_causal as E
from riskcap import LEGS, capped, trades_for

CAP = 300.0                       # the dollar-stop cap adopted in RESEARCH-LOG (xix)
ERA = "2023-01-01"
# approximate intraday order: market at the open first, then the resting limit orders
ORDER = ["cl-open-gap", "es-pdlow1", "cl-pdlow1", "gc-pdlow1"]
LOCKS = (None, 400.0, 500.0, 625.0, 800.0)
COOLDOWNS = (0, 1, 2)
TRIGGERS = (500.0, 600.0)


def per_leg(tables: dict[str, list[dict]]) -> dict[str, dict[str, float]]:
    return {lid: {t["d"]: t["usd"] for t in capped(tables.get(lid, []), CAP)}
            for lid in ORDER}


def series(per: dict[str, dict[str, float]], dates: list[str],
           lock: float | None = None, cooldown: int = 0,
           trigger: float = 600.0) -> dict[str, float]:
    """date -> book profit under the policy."""
    day: dict[str, float] = {}
    for i, d in enumerate(dates):
        if cooldown:
            prev = dates[max(0, i - cooldown):i]
            if any(day.get(p, 0.0) >= trigger for p in prev):
                continue
        s = 0.0
        for lid in ORDER:
            v = per[lid].get(d)
            if v is None:
                continue
            if lock is not None and s >= lock:
                continue                     # the day is already banked: no new risk
            s += v
        if s:
            day[d] = s
    return day


def walk(day: dict[str, float], dates: list[str], horizon: int = 240) -> dict:
    """Pass, target-reached, breach and median sessions, from every 2023+ start."""
    starts = [i for i, d in enumerate(dates) if d >= ERA]
    p = [day.get(d, 0.0) for d in dates]
    passed, reached, breached, sess = 0, 0, 0, []
    for s in starts:
        bal = peak = E.START_BAL
        largest = 0.0
        for j in range(s, min(len(p), s + horizon)):
            bal += p[j]
            largest = max(largest, p[j])
            peak = max(peak, bal)
            floor = (max(peak - E.MAX_LOSS, E.LOCK_AT) if peak >= E.LOCK_TRIGGER
                     else peak - E.MAX_LOSS)
            if bal < floor:
                breached += 1
                break
            profit = bal - E.START_BAL
            if profit >= E.TARGET:
                reached += 1
                if largest <= E.CONSISTENCY * profit:
                    passed += 1
                    sess.append(j - s + 1)
                break
    n = len(starts) or 1
    return {"starts": len(starts), "pass": 100.0 * passed / n,
            "reached": 100.0 * reached / n, "breach": 100.0 * breached / n,
            "median": statistics.median(sess) if sess else None}


def shape(day: dict[str, float]) -> dict:
    v = [x for d, x in day.items() if d >= ERA]
    eq = peak = dd = 0.0
    for x in v:
        eq += x
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    return {"net": sum(v), "best": max(v) if v else 0.0, "worst": min(v) if v else 0.0,
            "dd": dd, "days": len(v)}


def aftershock(day: dict[str, float], dates: list[str], trigger: float) -> dict:
    """What the next sessions look like after the book banks `trigger` in one session."""
    idx = {d: i for i, d in enumerate(dates)}
    nxt, nxt3 = [], []
    for d, v in day.items():
        if v >= trigger and d >= ERA and d in idx:
            i = idx[d]
            if i + 1 < len(dates):
                nxt.append(day.get(dates[i + 1], 0.0))
            nxt3.append(sum(day.get(x, 0.0) for x in dates[i + 1:i + 4]))
    allv = [day.get(d, 0.0) for d in dates if d >= ERA]
    return {"hits": len(nxt), "next": statistics.fmean(nxt) if nxt else 0.0,
            "next3": statistics.fmean(nxt3) if nxt3 else 0.0,
            "all": statistics.fmean(allv) if allv else 0.0,
            "neg3": 100.0 * sum(1 for x in nxt3 if x < 0) / len(nxt3) if nxt3 else 0.0}


def selftest() -> None:
    dates = ["2026-01-02", "2026-01-05", "2026-01-06"]
    per = {"cl-open-gap": {dates[0]: 700.0}, "es-pdlow1": {dates[0]: 200.0},
           "cl-pdlow1": {dates[0]: -100.0}, "gc-pdlow1": {dates[1]: 50.0}}
    assert series(per, dates)[dates[0]] == 800.0            # no lock: every leg books
    assert series(per, dates, lock=625.0)[dates[0]] == 700.0  # gap leg banks, rest stand down
    assert series(per, dates, lock=800.0)[dates[0]] == 900.0  # lock reached only at the end
    # after a $600+ session the next session is stood down for one day
    cool = series(per, dates, cooldown=1, trigger=600.0)
    assert dates[1] not in cool, cool
    assert series(per, dates, cooldown=0)[dates[1]] == 50.0
    print("selftest ok: the lock stops later legs only, a cooldown stands the next session down")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return

    tables: dict[str, list[dict]] = {}
    dates = None
    for lid, sym, fam, stopk, exitname, res, _ in LEGS:
        tr, D = trades_for(sym, fam, stopk, exitname, res)
        tables[lid] = tr
        dates = dates or D["d"]
    per = per_leg(tables)

    print("## A session profit lock — no new entry once the day has banked $L\n")
    print("| lock | days | net | best day | worst day | max DD | pass% | reached% "
          "| breach% | median sessions |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for lock in LOCKS:
        day = series(per, dates, lock=lock)
        s, w = shape(day), walk(day, dates)
        med = "-" if w["median"] is None else f"{w['median']:.0f}"
        print(f"| {'none' if lock is None else f'${lock:.0f}'} | {s['days']} | "
              f"${s['net']:+,.0f} | ${s['best']:+,.0f} | ${s['worst']:+.0f} | "
              f"${s['dd']:+,.0f} | {w['pass']:.1f}% | {w['reached']:.1f}% | "
              f"{w['breach']:.1f}% | {med} |")

    print("\n## A cooldown — the whole book stands down for K sessions after a $T day\n")
    print("| trigger | cooldown | days | net | best day | pass% | reached% | breach% "
          "| median sessions |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for trig in TRIGGERS:
        for k in COOLDOWNS:
            day = series(per, dates, cooldown=k, trigger=trig)
            s, w = shape(day), walk(day, dates)
            med = "-" if w["median"] is None else f"{w['median']:.0f}"
            print(f"| ${trig:.0f} | {k} | {s['days']} | ${s['net']:+,.0f} | "
                  f"${s['best']:+,.0f} | {w['pass']:.1f}% | {w['reached']:.1f}% | "
                  f"{w['breach']:.1f}% | {med} |")

    print("\n## After the book banks a big session — is the next one any good?\n")
    base = series(per, dates)
    allm = aftershock(base, dates, 10**9)
    print(f"Every 2023+ session: mean ${allm['all']:+.2f}/session, "
          f"{allm['neg3']:.0f}% of three-session windows negative.\n")
    print("| session made at least | sessions | next session mean | next 3 mean "
          "| vs all sessions | next 3 negative |")
    print("|---:|---:|---:|---:|---:|---:|")
    for trig in (400.0, 500.0, 600.0, 800.0):
        r = aftershock(base, dates, trig)
        edge = r["next"] - r["all"]
        print(f"| ${trig:.0f} | {r['hits']} | ${r['next']:+.2f} | ${r['next3']:+.2f} | "
              f"{edge:+.2f} | {r['neg3']:.0f}% |")
    print("\n_reads: the lock and the cooldown are applied on top of the $300 stop cap; "
          "the account walk steps every starting session for 240 sessions._")


if __name__ == "__main__":
    main()
