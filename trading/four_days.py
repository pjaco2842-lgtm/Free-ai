#!/usr/bin/env python3
"""Can this account pass inside four sessions? Measured, not hoped for.

The ask is 3-4 days. That is four sessions (16, 17, 18, 19 November), so the question is
narrow enough to answer exactly: take every historical four-session window, run the rule
through it day by day, and count how often the balance reaches +$1,250 before it falls
under the trailing floor.

What the window enforces, the same way `paper_causal.settle` does:
  * the floor follows the closing high-water mark and locks at $25,100 above $26,100;
  * the 40% consistency rule must hold at the moment the target is reached;
  * the book's own daily stop can stand the session down.

Also printed: the target that is reachable with 50%, 25%, 10% and 5% probability in four
sessions. That number is the honest answer to "how close can we get", because it says what
the account can actually do in the time available rather than what we wish it would.

    python3 four_days.py
"""
from __future__ import annotations

import argparse
import statistics
from pathlib import Path

import edge_causal as E

ROOT = Path(__file__).resolve().parent
DESK = ROOT / "desk"
START, TARGET, MAX_LOSS = E.START_BAL, E.TARGET, E.MAX_LOSS
LOCK_AT, LOCK_TRIG, CONS = E.LOCK_AT, E.LOCK_TRIGGER, E.CONSISTENCY
DAYS = 4
ERA = "2023-01-01"
# edge_causal's own EXITS stops at tp2; the sweep used wider targets, so map them here
EXIT_MULT = {"close": None, "tp05": 0.5, "tp1": 1.0, "tp15": 1.5, "tp2": 2.0,
             "tp25": 2.5, "tp3": 3.0, "tp4": 4.0}

LEGS = [
    ("ES prior-low 0.5 ATR tp2 (the book)", "ES_F_1d.csv", "ES=F",
     dict(fam="limit_low", n=1, stop=0.5, exit="tp2")),
    ("NQ prior-low 0.25 ATR tp4 (sweep's best)", "NQ_F_1d.csv", "NQ=F",
     dict(fam="limit_low", n=1, stop=0.25, exit="tp4")),
    ("NQ prior-low 0.5 ATR tp2 (sanity)", "NQ_F_1d.csv", "NQ=F",
     dict(fam="limit_low", n=1, stop=0.5, exit="tp2")),
]


def series(path: Path, sym: str, leg: dict) -> tuple[list[float], list[str]]:
    D = E.load_csv(str(path))
    spec = E.SPECS[sym]
    exitmode = EXIT_MULT[leg["exit"]]
    trades = []
    for i in range(21, D["n"]):
        sig = E.signal(D, i, leg["fam"], leg["n"], "any")
        if not sig:
            continue
        entry, kind = sig
        pnl = E.trade_pnl(D, i, entry, kind, leg["stop"], exitmode,
                          spec["mult"], spec["tick"], "proven")
        if pnl is not None:
            trades.append((D["d"][i], pnl))
    per_day: dict[str, float] = {}
    for d, pnl in trades:
        per_day[d] = per_day.get(d, 0.0) + pnl
    days = [d for d in D["d"] if d >= ERA]
    return [per_day.get(d, 0.0) for d in days], days


def window(pnls: list[float], size: int) -> tuple[str, float]:
    """Walk one four-session window. Returns (outcome, dollars moved)."""
    bal, peak, largest = START, START, 0.0
    for pnl in pnls:
        day = pnl * size
        bal += day
        largest = max(largest, day)
        peak = max(peak, bal)
        floor = max(peak - MAX_LOSS, LOCK_AT) if peak >= LOCK_TRIG else peak - MAX_LOSS
        if bal < floor:
            return "breach", bal - START
        profit = bal - START
        if profit >= TARGET and largest <= CONS * profit:
            return "pass", profit
    return "neither", bal - START


def quantile(xs: list[float], q: float) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, int(q * (len(s) - 1)))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=DAYS)
    a = ap.parse_args()

    L = [f"# Can we pass in {a.days} sessions?", "",
         f"Every historical {a.days}-session window from {ERA} onward, walked day by day "
         f"with the trailing floor and the {CONS:.0%} consistency rule enforced. "
         f"Target +${TARGET:,.0f}. One contract set per row; `x2` means two micros on the "
         f"same signal.", "",
         "| rule | size | windows | pass | breach | neither | median | p95 | best |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]

    summary = {}
    for name, csv_name, sym, leg in LEGS:
        path = ROOT / "data" / csv_name
        if not path.exists():
            print(f"  {csv_name} missing")
            continue
        pnls, days = series(path, sym, leg)
        for size in (1, 2):
            outs, moves = [], []
            for i in range(len(pnls) - a.days + 1):
                res, moved = window(pnls[i:i + a.days], size)
                outs.append(res)
                moves.append(moved)
            n = len(outs)
            p_pass = 100 * outs.count("pass") / n
            p_br = 100 * outs.count("breach") / n
            summary[(name, size)] = {
                "pass": p_pass, "breach": p_br,
                "moves": moves, "n": n,
                "p50": quantile(moves, 0.50), "p95": quantile(moves, 0.95),
                "best": max(moves),
                "target50": quantile(moves, 0.50),
            }
            L.append(f"| {name} | x{size} | {n} | **{p_pass:.2f}%** | {p_br:.1f}% | "
                     f"{100 - p_pass - p_br:.1f}% | ${quantile(moves, 0.50):+,.0f} | "
                     f"${quantile(moves, 0.95):+,.0f} | ${max(moves):+,.0f} |")

    L += ["", "## What four sessions can actually deliver", "",
          "The dollars a window reaches at each probability, so the gap between the target "
          "and the account is visible rather than argued about:", "",
          "| rule | size | 50% of windows reach | 25% | 10% | 5% | best ever |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for (name, size), s in summary.items():
        L.append(f"| {name} | x{size} | ${quantile(s['moves'], 0.50):+,.0f} | "
                 f"${quantile(s['moves'], 0.75):+,.0f} | "
                 f"${quantile(s['moves'], 0.90):+,.0f} | "
                 f"${quantile(s['moves'], 0.95):+,.0f} | ${s['best']:+,.0f} |")

    best = max(summary.items(), key=lambda kv: kv[1]["pass"]) if summary else None
    L += ["", "## Reading it", ""]
    if best:
        (name, size), s = best
        L += [f"Best pass rate found: **{name} at x{size} — {s['pass']:.2f}% of "
              f"four-session windows**, against {s['breach']:.1f}% breaching the floor.",
              "",
              f"Median window moves ${s['p50']:+,.0f}; the 95th percentile moves "
              f"${s['p95']:+,.0f}; the best window in {s['n']} ever recorded moved "
              f"${s['best']:+,.0f}. The target is ${TARGET:,.0f}.",
              ""]
    L += ["Per session the target demands **$312.50 a session** for four sessions. The book "
          "earns about $15 a session at one micro and $30 at two. That is the whole gap: it is "
          "not a missing indicator, it is a factor of ten in dollars per session, and the two "
          "ways to close it are more size (which spends the buffer) or more time (which is the "
          "four days we do not have).", ""]

    DESK.mkdir(exist_ok=True)
    (DESK / "four-days.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
