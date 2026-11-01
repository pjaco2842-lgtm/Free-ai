#!/usr/bin/env python3
"""How long until the account is funded? A race, not an average.

"When do we get funded" is not target divided by expectancy. The account can die
first: $1,000 of trailing room, and the floor follows the closing high-water mark.
So this simulates the actual race — +$1,250 before balance under the floor — on the
only numbers that exist: the live book's own settled trades.

Method, stated so it can be argued with:

  * the trade list is `edge_causal.run_config` for the book exactly as it stands
    (`desk/live-book.json`: prior-session-low limit, any gap, 0.5 ATR stop, 2R
    target, proven resolution, one micro);
  * each session's dollar result is the sum of that day's trades, zero when the
    rule does not fire — a flat day is a real day, not a skipped one;
  * sessions are resampled in blocks of five so good and bad weeks stay together
    instead of being averaged away by independence;
  * passing requires profit >= $1,250 AND the 40% consistency rule, exactly as
    `paper_causal.settle` enforces it; breach requires balance < floor.

This is a model of the record, not a promise about the future. Its honest output
is a distribution, and the distribution is the answer.

    python3 time_to_funded.py                  # 20,000 paths, 1 and 2 micros
    python3 time_to_funded.py --paths 100000   # tighter tails
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from datetime import date, timedelta
from pathlib import Path

import edge_causal as E

ROOT = Path(__file__).resolve().parent
CSV = ROOT / "data" / "ES_F_1d.csv"

START, TARGET, MAX_LOSS = E.START_BAL, E.TARGET, E.MAX_LOSS
LOCK_AT, LOCK_TRIG, CONS = E.LOCK_AT, E.LOCK_TRIGGER, E.CONSISTENCY
FIRST_SESSION = date(2026, 11, 16)      # Monday, the first session of the evaluation
BLOCK = 5
MULT = E.SPECS["ES=F"]["mult"]
TICK = E.SPECS["ES=F"]["tick"]
LEG = dict(fam="limit_low", n=1, stop=0.5, exit="tp2", gap="any", engine="proven")


def sessions(leg: dict | None = None,
             only: set[str] | None = None) -> tuple[list[float], list[str], int]:
    """One dollar result per session, including the sessions with no trade."""
    leg = leg or LEG
    D = E.load_csv(str(CSV))
    if leg["fam"] in ("nday_break", "nr_break"):
        # the breakout families live in wide_stops.py because edge_causal's own
        # "nr_break" has no narrow-range filter and has no prior-day breakout at all
        import wide_stops as W
        trades = []
        for i in range(21, D["n"]):
            sig = W.signal(D, i, leg["fam"], leg["n"])
            if not sig:
                continue
            entry, kind = sig
            pnl = E.trade_pnl(D, i, entry, kind, leg["stop"], E.EXITS[leg["exit"]],
                              MULT, TICK, "proven")
            if pnl is not None:
                trades.append((D["d"][i], pnl))
    else:
        trades = E.run_config(D, leg["fam"], leg["n"], leg["stop"], leg["exit"],
                              leg["gap"], leg["engine"], MULT, TICK)
    if only is not None:                 # a gate: the rule stands down on other days
        trades = [(d, p) for d, p in trades if d in only]
    per_day: dict[str, float] = {}
    for day, pnl in trades:
        per_day[day] = per_day.get(day, 0.0) + pnl
    calendar = [d for d in D["d"] if d >= "2023-01-01"]
    return [per_day.get(d, 0.0) for d in calendar], calendar, len(trades)


def calendar_date(k: int) -> str:
    """Session k after 16 Nov 2026, counting weekdays. Holidays are ignored."""
    d = FIRST_SESSION
    left = k
    while left > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            left -= 1
    return d.isoformat()


def one_path(blocks: list[list[float]], size: int, rng: random.Random,
             max_sessions: int) -> tuple[str, int]:
    bal, peak, largest = START, START, 0.0
    day = 0
    while day < max_sessions:
        block = blocks[rng.randrange(len(blocks))]
        for pnl in block:
            day += 1
            bal += pnl * size
            largest = max(largest, pnl * size)
            peak = max(peak, bal)
            floor = max(peak - MAX_LOSS, LOCK_AT) if peak >= LOCK_TRIG else peak - MAX_LOSS
            if bal < floor:
                return "breach", day
            profit = bal - START
            if profit >= TARGET and largest <= CONS * profit:
                return "pass", day
            if day >= max_sessions:
                return "running", day
    return "running", max_sessions


def run(size: int, paths: int, max_sessions: int, leg: dict | None = None,
        seed: int = 16, only: set[str] | None = None,
        series: list[float] | None = None) -> dict:
    """`series` lets any sweep hand over its own per-session dollars directly."""
    leg = leg or LEG
    if series is None:
        pnls, _calendar, _n = sessions(leg, only)
    else:
        pnls = series
    blocks = [pnls[i:i + BLOCK] for i in range(len(pnls) - BLOCK + 1)]
    rng = random.Random(seed + size)
    out = []
    for _ in range(paths):
        out.append(one_path(blocks, size, rng, max_sessions))
    passes = [d for kind, d in out if kind == "pass"]
    breach = sum(1 for kind, _ in out if kind == "breach")
    return {
        "size": size, "paths": paths, "max_sessions": max_sessions, "leg": leg,
        "pass_sessions": passes, "breached": breach,
        "p_pass": len(passes) / paths, "p_breach": breach / paths,
        "ev_session": statistics.fmean(pnls) * size,
        "fire_rate": sum(1 for p in pnls if p) / len(pnls),
        "sessions_available": len(pnls),
    }


def by(tag: str, horizon: int, r: dict) -> str:
    hit = sum(1 for d in r["pass_sessions"] if d <= horizon) / r["paths"]
    return f"  by session {horizon:>3} ({calendar_date(horizon)}):  {100*hit:5.1f}%"


def report(r: dict) -> list[str]:
    s = r["size"]
    leg = r.get("leg") or {}
    rule = leg.get("name") or (f"{leg.get('fam')}-{leg.get('n')} "
                                f"{leg.get('stop')} ATR {leg.get('exit')}")
    L = [f"{'=' * 78}", f"  {s} micro{'s' if s > 1 else ''} — {r['paths']:,} paths, "
         f"{r['sessions_available']} sessions of history, {r['max_sessions']} max",
         f"  rule: {rule}",
         "=" * 78]
    L.append(f"  EV: ${r['ev_session']:+.2f}/session · rule fires {100*r['fire_rate']:.1f}% "
             "of sessions")
    L.append(f"  funded at some point:  {100*r['p_pass']:5.1f}%")
    L.append(f"  breached the floor:    {100*r['p_breach']:5.1f}%")
    L.append(f"  still running after {r['max_sessions']}: "
             f"{100*(1-r['p_pass']-r['p_breach']):5.1f}%")
    L.append("")
    L += [by("", h, r) for h in (20, 40, 60, 120, 250, 500)]
    if r["pass_sessions"]:
        p = sorted(r["pass_sessions"])
        L += ["", f"  sessions to funding, among those that made it:",
              f"    25th {p[len(p)//4]}, median {p[len(p)//2]}, 75th {p[3*len(p)//4]}, "
              f"95th {p[int(0.95*(len(p)-1))]}"]
        L.append(f"    median date: {calendar_date(p[len(p)//2])}")
    else:
        L += ["", "  no path reached the target inside the horizon"]
    return L


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", type=int, default=20_000)
    ap.add_argument("--max-sessions", type=int, default=750)
    ap.add_argument("--json")
    ap.add_argument("--fam", default=LEG["fam"])
    ap.add_argument("--n", type=int, default=LEG["n"])
    ap.add_argument("--stop", type=float, default=LEG["stop"])
    ap.add_argument("--exit", default=LEG["exit"])
    ap.add_argument("--only-dates", help="JSON list of sessions the rule is allowed to trade")
    ap.add_argument("--pnl-json", help="a sweep's own per-session dollars (one micro)")
    a = ap.parse_args()
    leg = dict(LEG, fam=a.fam, n=a.n, stop=a.stop, exit=a.exit)
    only = set(json.loads(Path(a.only_dates).read_text())) if a.only_dates else None
    series, label = None, None
    if a.pnl_json:
        blob = json.loads(Path(a.pnl_json).read_text())
        series = blob["pnl"]
        label = blob.get("config") or {}
        label = (f"{label.get('sym')} {label.get('rule')} "
                 f"{label.get('gap')}/{label.get('trend')}/{label.get('dow')} "
                 f"{label.get('stop')} ATR {label.get('exit')}" if label else None)
        print(f"  series: {len(series)} sessions from {a.pnl_json} — {label}")
        leg = dict(leg, name=label) if label else leg
    results = [run(size, a.paths, a.max_sessions, leg, only=only, series=series)
               for size in (1, 2)]
    for r in results:
        print("\n".join(report(r)))
    if a.json:
        Path(a.json).write_text(__import__("json").dumps(results, indent=2))
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
