#!/usr/bin/env python3
"""
Does a wider stop buy a higher win rate on a $25,000 account?

The question, in the desk's own terms: at 25K the evaluation pays +$1,250 and kills at
-$1,000, and one micro of NQ at a 1.0 ATR stop already risks about $1,060 — the whole
allowance in a single trade. So "2.5 ATR has a higher win rate" is true and may still be
useless, because a higher win rate bought with a bigger loss is not a higher chance of
passing. This file measures the thing that decides: how often a real account, walked
forward from *every* starting trade, reaches +$1,250 before the floor.

What is swept (per market)
--------------------------
    rules    nr_break-2 (narrow range → prior-day breakout)
             nday_break-1 (plain prior-day breakout)
             nday_fade-5  (five-day fade)
             prevclose_break ("Oracle": prior close, both directions)
    stops    0.5, 0.75, 1.0, 1.5, 2.0, 2.5 x yesterday's ATR
    exits    close, tp1 (1R), tp2 (2R)
    markets  ES (MES, $5/pt) and NQ (MNQ, $2/pt), one micro

Every line is then scored on the account, not on the equity curve: pass%, the share of
passes that also satisfy the 40% consistency rule, breach%, and sessions to target. Books
of two and three rules are built from the lines that survive, with overlapping rules
excluded so a "book" is not the same position counted twice.

    python3 trading/atr_grid.py
    python3 trading/atr_grid.py --since 2023-01-01 --pool 6
"""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lab26k import MARKETS, prep  # noqa: E402
from pick_book import (CONSISTENCY, FLOOR, LOCKED, START, TARGET_EQ, combine,  # noqa: E402
                       recent, record, risk_now, rolling, spec_for, trades_for)

HERE = Path(__file__).resolve().parent
OUT = HERE / "desk" / "atr-grid.md"
RAW = HERE / "desk" / "atr-grid.json"

BUFFER = START - FLOOR
FAMILIES = [("nr_break", 2), ("nday_break", 1), ("nday_fade", 5), ("prevclose_break", None)]
STOPS = [0.5, 0.75, 1.0, 1.5, 2.0, 2.5]
EXITS = ["close", "tp1", "tp2"]
SYMS = ["ES=F", "NQ=F"]


def days_of(trades: list[dict]) -> set[str]:
    return {t["date"] for t in trades}


def overlap(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a or b else 1.0


def label(sym: str, fam: str, n, stop: float, exit_: str) -> str:
    return f"{sym[:2]} {fam.replace('_', '-')}{'' if n is None else '-' + str(n)} {stop:g}A {exit_}"


def line(sym: str, fam: str, n, stop: float, exit_: str, data: dict, since: str) -> dict:
    D = data[sym]
    spec = spec_for(sym, fam, n, stop, exit_)
    tr = trades_for(D, spec)
    tr_recent = recent(tr, since)
    rec_all = record(tr)
    rec_now = record(tr_recent)
    acc = rolling(tr_recent)
    return {"name": label(sym, fam, n, stop, exit_), "symbol": sym, "family": fam, "n": n,
            "stop": stop, "exit": exit_, "spec": spec,
            "all": rec_all, "now": rec_now, "account": acc,
            "risk_now": risk_now(tr_recent), "days": days_of(tr_recent), "trades": tr_recent}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2023-01-01")
    ap.add_argument("--pool", type=int, default=6, help="lines per market fed into the books")
    args = ap.parse_args()

    print("=" * 116)
    print(f"  ATR GRID ON A ${START:,.0f} EVALUATION · +${TARGET_EQ - START:,.0f} target · "
          f"${BUFFER:,.0f} buffer · consistency ≤ {CONSISTENCY:.0f}% · one micro")
    print("=" * 116)

    data = {s: prep(s) for s in SYMS}
    lines: list[dict] = []
    for sym in SYMS:
        for fam, n in FAMILIES:
            for stop in STOPS:
                for ex in EXITS:
                    L = line(sym, fam, n, stop, ex, data, args.since)
                    if L["now"]["n"] < 30:
                        continue
                    lines.append(L)
    print(f"  {len(lines)} lines tested · trade record from {args.since} · "
          f"NQ med ATR {np.nanmedian(data['NQ=F']['atr_prev'][-120:]):.0f} pts, "
          f"ES {np.nanmedian(data['ES=F']['atr_prev'][-120:]):.2f} pts")

    # ---- the stop question, one leg at a time
    print("\n  Every line, ranked by how often the account passes (one micro, 2023 onward)")
    print(f"  {'line':28}{'trades':>7}{'win':>6}{'$/trade':>9}{'net $':>9}{'risk':>7}"
          f"{'fits?':>7}{'pass%':>7}{'cons%':>7}{'breach%':>9}{'days→':>7}")
    lines.sort(key=lambda L: (-L["account"]["consistency_pct"], -L["now"]["per"]))
    for L in lines:
        a, r = L["account"], L["now"]
        fits = "yes" if L["risk_now"] <= BUFFER / 2 else ("tight" if L["risk_now"] <= BUFFER else "no")
        md = "—" if a["med_days_to_pass"] is None else f"{a['med_days_to_pass']:.0f}"
        print(f"  {L['name']:28}{r['n']:7d}{r['win']:5.0f}%{r['per']:>9,.0f}{r['net']:>9,.0f}"
              f"{L['risk_now']:>7,.0f}{fits:>7}{a['pass_pct']:6.0f}%{a['consistency_pct']:6.0f}%"
              f"{a['breach_pct']:8.0f}%{md:>7}")

    # ---- does the stop distance actually buy a higher win rate?
    print("\n  The stop axis, averaged over every rule/exit/market (2023 onward)")
    print(f"  {'stop':>6}{'risk $':>9}{'win%':>7}{'$/trade':>9}{'stops/trade':>12}{'pass%':>7}{'breach%':>9}")
    stop_rows = []
    for stop in STOPS:
        grp = [L for L in lines if L["stop"] == stop]
        if not grp:
            continue
        risk = statistics.median(L["risk_now"] for L in grp)
        win = statistics.median(L["now"]["win"] for L in grp)
        per = statistics.mean(L["now"]["per"] for L in grp)
        stops = 100 * sum(L["now"]["stops"] for L in grp) / max(sum(L["now"]["n"] for L in grp), 1)
        ps = statistics.mean(L["account"]["pass_pct"] for L in grp)
        br = statistics.mean(L["account"]["breach_pct"] for L in grp)
        stop_rows.append({"stop": stop, "risk": risk, "win": win, "per": per,
                          "stops_pct": stops, "pass_pct": ps, "breach_pct": br})
        print(f"  {stop:>5.2f}A{risk:>9,.0f}{win:>6.0f}%{per:>9,.0f}{stops:>11.0f}%"
              f"{ps:>6.0f}%{br:>8.0f}%")

    # ---- books: two and three rules, one micro each
    pool: list[dict] = []
    for sym in SYMS:
        cand = [L for L in lines if L["symbol"] == sym and L["risk_now"] <= BUFFER]
        cand.sort(key=lambda L: (-L["account"]["consistency_pct"], -L["now"]["per"]))
        kept: list[dict] = []
        for L in cand:
            if any(overlap(L["days"], K["days"]) > 0.6 for K in kept):
                continue
            kept.append(L)
            if len(kept) >= args.pool:
                break
        pool += kept
    print("\n  book pool (one line per trade shape, risk inside the buffer):")
    for L in pool:
        print(f"    {L['name']:28} {L['account']['consistency_pct']:3.0f}% pass-with-consistency, "
              f"risk ${L['risk_now']:,.0f}, {L['now']['win']:.0f}% win")

    books: list[dict] = []
    for k in (2, 3):
        for combo in itertools.combinations(pool, k):
            syms = {L["symbol"] for L in combo}
            if len(syms) > 1 and k == 3:
                continue                      # keep 3-rule books to a single market
            if any(overlap(a["days"], b["days"]) > 0.5
                   for a, b in itertools.combinations(combo, 2)):
                continue
            tr = combine([L["trades"] for L in combo])
            rec, acc = record(tr), rolling(tr)
            rn = risk_now(tr)
            books.append({"name": " + ".join(L["name"].split(" ", 1)[1] if len(L["symbol"]) else L["name"]
                                             for L in combo),
                          "legs": [L["name"] for L in combo], "symbol": "+".join(sorted(syms)),
                          "k": k, "now": rec, "account": acc, "risk_now": rn})
    books.sort(key=lambda b: (-b["account"]["consistency_pct"], -b["now"]["per"]))
    print(f"\n  {len(books)} books built from those lines, ranked by pass rate with consistency")
    print(f"  {'book':62}{'k':>2}{'trades':>7}{'win':>6}{'$/trade':>9}{'risk':>7}"
          f"{'pass%':>7}{'cons%':>7}{'breach%':>9}{'days→':>7}")
    for b in books[:18]:
        a, r = b["account"], b["now"]
        md = "—" if a["med_days_to_pass"] is None else f"{a['med_days_to_pass']:.0f}"
        print(f"  {b['name'][:62]:62}{b['k']:2d}{r['n']:7d}{r['win']:5.0f}%{r['per']:>9,.0f}"
              f"{b['risk_now']:>7,.0f}{a['pass_pct']:6.0f}%{a['consistency_pct']:6.0f}%"
              f"{a['breach_pct']:8.0f}%{md:>7}")

    # ---- the two books this desk actually trades, at every stop, so the comparison is fair
    named = []
    for sym in SYMS:
        for stop in (1.0, 1.5, 2.0, 2.5):
            for fam, n, ex in (("prevclose_break", None, "tp2"), ("nr_break", 2, "tp2")):
                L = next((x for x in lines if x["symbol"] == sym and x["family"] == fam
                          and x["n"] == n and x["stop"] == stop and x["exit"] == ex), None)
                if L:
                    named.append(L)
    print("\n  The named single rules, same stop grid (2023 onward)")
    for L in named:
        a, r = L["account"], L["now"]
        print(f"  {L['name']:28}{r['n']:6d} trades {r['win']:4.0f}% win ${r['per']:+6,.0f}/trade "
              f"risk ${L['risk_now']:6,.0f}  pass {a['pass_pct']:4.0f}%  "
              f"with consistency {a['consistency_pct']:4.0f}%  breach {a['breach_pct']:3.0f}%")

    best = books[0] if books else None
    best_single = max(lines, key=lambda L: (
        L["account"]["consistency_pct"], -L["account"]["breach_pct"], L["now"]["per"]))
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    # ---- write it down
    md = [
        "# The ATR grid on a 25K",
        "",
        f"Generated {stamp} · ${START:,.0f} start · ${FLOOR:,.0f} opening floor, trailing the "
        f"highest close and locking at ${LOCKED:,.0f} · +${TARGET_EQ - START:,.0f} target · "
        f"consistency ≤ {CONSISTENCY:.0f}% · one micro contract · trade record "
        f"{args.since} onward",
        "",
        "The question was whether a wider stop buys a higher win rate, and whether that buys a",
        "higher chance of passing. The first half is mechanically true — a 2.5 ATR stop is hit",
        "far less often than a 0.75 ATR stop, so the win rate rises — and the second half is",
        "where it breaks: on a 25K the buffer is $1,000, and one micro of NQ at 1.0 ATR risks",
        "about $1,060 today, so a wider stop does not buy a higher chance of passing, it buys a",
        "larger share of the account lost when the rule is wrong.",
        "",
        "## The stop axis",
        "",
        "| stop | median risk | win% | $/trade | trades stopped | pass% | breach% |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in stop_rows:
        md.append(f"| {s['stop']:g}A | ${s['risk']:,.0f} | {s['win']:.0f}% | ${s['per']:+,.0f} | "
                  f"{s['stops_pct']:.0f}% | {s['pass_pct']:.0f}% | {s['breach_pct']:.0f}% |")

    md += ["", "## Every line", "",
           "`fits?` is the line's median session risk against the $1,000 buffer: `yes` at half of",
           "it or less, `tight` inside it, `no` beyond it. `pass%` reaches +$1,250 from every",
           "starting trade; `cons%` is the share that also keeps the best day under 40% of the",
           "profit.", "",
           "| line | trades | win | $/trade | net | risk | fits? | pass% | cons% | breach% | days → pass |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for L in lines:
        a, r = L["account"], L["now"]
        fits = "yes" if L["risk_now"] <= BUFFER / 2 else ("tight" if L["risk_now"] <= BUFFER else "no")
        md.append(f"| {L['name']} | {r['n']} | {r['win']:.0f}% | ${r['per']:+,.0f} | "
                  f"${r['net']:+,.0f} | ${L['risk_now']:,.0f} | {fits} | {a['pass_pct']:.0f}% | "
                  f"{a['consistency_pct']:.0f}% | {a['breach_pct']:.0f}% | "
                  + ("—" if a["med_days_to_pass"] is None else f"{a['med_days_to_pass']:.0f}") + " |")

    md += ["", "## Books of two and three rules", "",
           "Built only from lines whose own session risk fits the buffer, with overlapping trade",
           "shapes excluded — two rules that trade the same days are one position sized twice.", "",
           "| book | legs | trades | win | $/trade | risk | pass% | cons% | breach% | days → pass |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for b in books[:24]:
        a, r = b["account"], b["now"]
        md.append(f"| {b['name'][:70]} | {b['k']} | {r['n']} | {r['win']:.0f}% | "
                  f"${r['per']:+,.0f} | ${b['risk_now']:,.0f} | {a['pass_pct']:.0f}% | "
                  f"{a['consistency_pct']:.0f}% | {a['breach_pct']:.0f}% | "
                  + ("—" if a["med_days_to_pass"] is None else f"{a['med_days_to_pass']:.0f}") + " |")

    md += ["", "## What this says", ""]
    if best:
        md += [f"**Best book for a 25K: {best['name']}** — {best['account']['consistency_pct']:.0f}% "
               f"of starting trades pass with the consistency rule intact, "
               f"{best['account']['breach_pct']:.0f}% breach, ${best['risk_now']:,.0f} of session "
               f"risk, and a median of {best['account']['med_days_to_pass'] or 0:.0f} sessions to "
               f"the target.", ""]
    md += [f"**Best single line: {best_single['name']}** — "
           f"{best_single['account']['consistency_pct']:.0f}% pass with consistency, "
           f"{best_single['now']['win']:.0f}% win, ${best_single['now']['per']:+,.0f} a trade, "
           f"${best_single['risk_now']:,.0f} of risk.", "",
           "The honest reading of the grid is that the stop distance is not a free dial. Every",
           "step wider trades stop-outs for size: the win rate climbs and the average loss climbs",
           "with it, so the pass rate does not climb at all — it is set by how many buffers one",
           "loss costs, and that is a fact about the contract, not the rule.", ""]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(md))
    RAW.write_text(json.dumps({"generated": stamp, "since": args.since, "buffer": BUFFER,
                              "stop_axis": stop_rows,
                              "lines": [{k: v for k, v in L.items()
                                         if k not in ("days", "trades", "spec")} for L in lines],
                              "books": books[:40]}, indent=2, default=str))

    print(f"\n  written to {OUT} and {RAW}")
    if best:
        print(f"  best book: {best['name']}  "
              f"({best['account']['consistency_pct']:.0f}% pass with consistency, "
              f"risk ${best['risk_now']:,.0f})")
    print(f"  best single: {best_single['name']}  "
          f"({best_single['account']['consistency_pct']:.0f}% pass with consistency, "
          f"{best_single['now']['win']:.0f}% win)")


if __name__ == "__main__":
    main()
