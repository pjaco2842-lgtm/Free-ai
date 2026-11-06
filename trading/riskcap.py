#!/usr/bin/env python3
"""Does capping the dollar stop improve the desk? Measured, not assumed.

The book takes every signal with a 0.5 ATR stop, so the money at risk scales with
volatility. In a quiet stretch one micro risks ~$175; in the week of 2-5 November the
same rule risked $277-$416, and three legs together could risk $996 against a $1,000
daily buffer. One bad session then ends the evaluation instead of denting it.

The obvious fix is to skip a trade when its stop is wider than a fixed dollar cap. That
changes which trades are taken, so it has to be measured rather than asserted: this
script applies each cap to the full history of every leg's rule and reports what the cap
costs in trades and edge against what it saves in drawdown. A cap is only worth adopting
if it holds up across contracts and cap levels, not at one hand-picked number.

    python3 riskcap.py            # per-leg and combined tables
    python3 riskcap.py --selftest # cap arithmetic only, no data

Paper only. Nothing here writes a ledger.
"""
from __future__ import annotations

import argparse
import statistics
from pathlib import Path

import edge_causal as E

ROOT = Path(__file__).resolve().parent
CAPS = (None, 150, 200, 250, 300, 350, 400)
ERA = "2023-01-01"

# id, symbol, family args, stop (ATR), exit, resolution, micros — the live book's rules
LEGS = [
    ("es-pdlow1", "ES=F", {"family": "limit_low", "n": 1, "gap": "any"}, 0.5, "tp2", "proven", 1),
    ("cl-pdlow1", "CL=F", {"family": "limit_low", "n": 1, "gap": "any"}, 0.5, "tp2", "proven", 1),
    ("gc-pdlow1", "GC=F", {"family": "limit_low", "n": 1, "gap": "any"}, 0.5, "tp2", "proven", 1),
    ("cl-open-gap", "CL=F", {"entry": "open"}, 0.5, "tp3", "open", 1),
]


def trades_for(sym: str, fam: dict, stopk: float, exitname: str,
               resolution: str) -> tuple[list[dict], dict]:
    """Every trade the rule would take, with the dollars its stop put at risk."""
    D = E.load_csv(str(ROOT / "data" / f"{sym.replace('=F', '')}_F_1d.csv"))
    pv, tick = E.SPECS[sym]["mult"], E.SPECS[sym]["tick"]
    out = []
    for i in range(22, D["n"]):                 # ATR(14) + a prior bar need 22
        if fam.get("entry") == "open":
            sig = E.open_signal(D, i)
            if not sig:
                continue
            entry, kind, side = sig
        else:
            sig = E.signal(D, i, fam["family"], fam["n"], fam["gap"])
            if not sig:
                continue
            entry, kind = sig
            side = 1
        usd = E.trade_pnl(D, i, entry, kind, stopk, E.EXITS[exitname],
                          pv, tick, resolution, side=side)
        if usd is None:
            continue
        out.append({"d": D["d"][i], "usd": usd,
                    "risk": stopk * D["atr"][i - 1] * pv})
    return out, D


def summarize(tr: list[dict]) -> dict:
    if not tr:
        return {"n": 0, "win": 0.0, "mean": 0.0, "net": 0.0, "dd": 0.0,
                "worst": 0.0, "risk": 0.0}
    v = [t["usd"] for t in tr]
    eq = peak = dd = 0.0
    for x in v:
        eq += x
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    return {"n": len(v), "win": 100.0 * sum(1 for x in v if x > 0) / len(v),
            "mean": statistics.fmean(v), "net": sum(v), "dd": dd,
            "worst": min(v), "risk": statistics.median([t["risk"] for t in tr])}


def capped(tr: list[dict], cap: float | None) -> list[dict]:
    return tr if cap is None else [t for t in tr if t["risk"] <= cap]


def combined(tables: dict[str, list[dict]], cap: float | None) -> dict[str, float]:
    day: dict[str, float] = {}
    for tr in tables.values():
        for t in capped(tr, cap):
            day[t["d"]] = day.get(t["d"], 0.0) + t["usd"]
    return day


def walk(day: dict[str, float], dates: list[str], horizon: int = 240) -> dict:
    """Account walk over every starting session: pass and breach shares."""
    starts = [i for i, d in enumerate(dates) if d >= ERA]
    p = [day.get(d, 0.0) for d in dates]
    passed = breached = 0
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
            if profit >= E.TARGET and largest <= E.CONSISTENCY * profit:
                passed += 1
                break
    n = len(starts)
    return {"pass": 100.0 * passed / n, "breach": 100.0 * breached / n, "starts": n}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        assert capped([{"risk": 100.0}, {"risk": 250.0}], 200) == [{"risk": 100.0}]
        assert capped([{"risk": 900.0}], None)[0]["risk"] == 900.0
        print("selftest ok: a cap keeps stops at or under it, None keeps everything")
        return

    tables: dict[str, list[dict]] = {}
    dates = None
    for lid, sym, fam, stopk, exitname, res, _ in LEGS:
        tr, D = trades_for(sym, fam, stopk, exitname, res)
        tables[lid] = tr
        dates = dates or D["d"]

    HEAD = ("| leg | cap | trades | taken | win | $/trade | net | max DD | worst trade "
            "| median risk |")
    SEP = "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    print("## Per leg — what a dollar-stop cap does to the full record\n")
    print(HEAD)
    print(SEP)
    for lid, tr in tables.items():
        base = len(tr)
        near = [t for t in tr if t["d"] >= ERA]
        for cap in CAPS:
            s = summarize(capped(near, cap))
            print(f"| {lid} | {'none' if cap is None else f'${cap}'} | {base} | {s['n']} | "
                  f"{s['win']:.0f}% | ${s['mean']:+.2f} | ${s['net']:+,.0f} | "
                  f"${s['dd']:+,.0f} | ${s['worst']:+.0f} | ${s['risk']:.0f} |")
        print(SEP)

    print("\n## The four legs as one book (since 2023)\n")
    print("| cap | net | worst day | max DD | pass% | breach% | sessions risking >$800 |")
    print("|---:|---:|---:|---:|---:|---:|---:|")
    for cap in CAPS:
        day = combined(tables, cap)
        rec = {d: v for d, v in day.items() if d >= ERA}
        if not rec:
            continue
        v = list(rec.values())
        eq = peak = dd = 0.0
        for x in v:
            eq += x
            peak = max(peak, eq)
            dd = min(dd, eq - peak)
        w = walk(day, dates)
        risk_day: dict[str, float] = {}
        for tr in tables.values():
            for t in capped(tr, cap):
                if t["d"] >= ERA:
                    risk_day[t["d"]] = risk_day.get(t["d"], 0.0) + t["risk"]
        over = sum(1 for x in risk_day.values() if x > 800)
        print(f"| {'none' if cap is None else f'${cap}'} | ${sum(v):+,.0f} | "
              f"${min(v):+.0f} | ${dd:+,.0f} | {w['pass']:.1f}% | {w['breach']:.1f}% | "
              f"{over} of {len(risk_day)} |")
    print("\n_reads: 'taken' is trades surviving the cap over 2023+; the account walk "
          "steps every starting session for 240 sessions with the $1,000 floor._")


if __name__ == "__main__":
    main()
