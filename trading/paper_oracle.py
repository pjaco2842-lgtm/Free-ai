#!/usr/bin/env python3
"""
Forward paper record for whatever the 26,000-test book chose.

The rules are day trades: a signal is known at the close, the order sits at a derived
level during the next session, the stop is intraday, the exit is the close. So this
runner does not need to watch the tape — it needs completed daily bars, and it writes
one record per completed session. It is idempotent in the same way the intraday
runner is: it only ever processes bars with a date it has not already processed, so a
run every hour, every day or once a week produces the same ledger.

It also prints the levels for the session in progress, which is the only part that is
live: if price trades through a level, that is the trade the record will contain after
the close.

    python3 trading/paper_oracle.py                 # forward step, saves the ledger
    python3 trading/paper_oracle.py --replay 20     # last 20 sessions, state untouched
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lab26k import BOOK, day_trade, prep, spec_legs  # noqa: E402
from scalp import MARKETS  # noqa: E402

DESK = Path(__file__).resolve().parent / "desk"
STATE = DESK / "oracle-state.json"
FORWARD = DESK / "oracle-forward.md"
REPLAY_MD = DESK / "oracle-replay.md"
BUFFER = 1000.0
TARGET = 1250.0           # evaluation target: +$1,250 before the buffer is gone
CLOSE_UTC = 21.5          # the futures session closes ~21:00 UTC; treat 21:30 as complete
KEYS = ("family", "n", "stop", "exit", "gap", "trend", "dow", "dir")


def label(spec: dict) -> str:
    n = "" if spec["n"] is None else f"-{spec['n']}"
    return f"{spec['family']}{n} {spec['stop']}A {spec['exit']} {spec['dir']}"


def spec_of(row: dict) -> dict:
    return {k: row[k] for k in KEYS}


def complete_len(D: dict, now: datetime) -> int:
    """Number of bars that are finished. Today's bar is excluded until the close."""
    if not D["dates"]:
        return 0
    frac = now.hour + now.minute / 60
    if D["dates"][-1] == now.strftime("%Y-%m-%d") and frac < CLOSE_UTC:
        return len(D["dates"]) - 1
    return len(D["dates"])


def blank() -> dict:
    return {"created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "last": {}, "ledger": [], "equity": 0.0, "halted": False}


def step(sym: str, D: dict, specs: list[dict], state: dict, upto: int) -> list[dict]:
    pv, tick = MARKETS[sym][1], MARKETS[sym][2]
    start = state["last"].get(sym)
    first = 2
    if start:
        first = max(2, next((i for i, d in enumerate(D["dates"]) if d > start), upto))
    fresh: list[dict] = []
    for spec in specs:
        legs = spec_legs(D, spec)
        for i in range(first, upto):
            if state["halted"]:
                break
            t = day_trade(D, i, spec, legs, pv, tick)
            if not t:
                continue
            trade = {"date": D["dates"][i], "market": sym, "rule": label(spec),
                     "side": "long" if t["side"] > 0 else "short",
                     "entry": round(t["entry"], 2), "exit": round(t["exit"], 2),
                     "why": t["why"], "risk": round(t["risk"], 2),
                     "usd": round(t["usd"], 2)}
            state["ledger"].append(trade)
            state["equity"] = round(state["equity"] + t["usd"], 2)
            fresh.append(trade)
            if state["equity"] <= -BUFFER:
                state["halted"] = True
    if upto > 1:
        state["last"][sym] = D["dates"][upto - 1]
    return fresh


PAD_KEYS = ("o", "h", "l", "c", "atr", "atr_prev", "sma20", "sma50", "rng", "body")


def pad(D: dict) -> dict:
    """Add one placeholder session so tomorrow's levels exist before tomorrow's bar does.

    Levels are built from the bars *before* the trade, so a placeholder cannot leak into
    them: the rolling extremes are recomputed from the real last n bars explicitly.
    """
    P = dict(D)
    for k in PAD_KEYS:
        P[k] = np.append(D[k], D[k][-1])
    P["dow"] = np.append(D["dow"], D["dow"][-1])
    P["years"] = np.append(D["years"], D["years"][-1])
    P["hiN"] = {n: np.append(v, np.max(D["h"][-n:])) for n, v in D["hiN"].items()}
    P["loN"] = {n: np.append(v, np.min(D["l"][-n:])) for n, v in D["loN"].items()}
    nxt = datetime.strptime(D["dates"][-1], "%Y-%m-%d") + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    P["dates"] = D["dates"] + [nxt.strftime("%Y-%m-%d")]
    return P


def watch(D: dict, specs: list[dict], upto: int) -> list[dict]:
    """The orders standing for the session in progress, or for the next one."""
    if upto >= len(D["dates"]):
        D = pad(D)
        upto = len(D["dates"]) - 1
    if upto < 1:
        return []
    pv = MARKETS[D["symbol"]][1]
    atr = D["atr"][upto - 1]
    close = D["c"][upto - 1]
    out = []
    for spec in specs:
        legs = spec_legs(D, spec)
        sides = ((1, -1) if spec["dir"] == "both"
                 else ((1,) if spec["dir"] == "long" else (-1,)))
        for side in sides:
            leg = legs[0] if side > 0 else legs[1]
            row = {"date": D["dates"][upto], "market": D["symbol"], "rule": label(spec),
                   "side": "long" if side > 0 else "short"}
            if leg["mode"] == "open":
                row.update({"level": None, "dist": None,
                            "risk": round(spec["stop"] * atr * pv, 2),
                            "note": "at the open, if the gap rule holds"})
            else:
                lvl = float(leg["level"][upto])
                if lvl != lvl:                      # NaN
                    continue
                row.update({"level": round(lvl, 2), "dist": round(lvl - close, 2),
                            "risk": round(spec["stop"] * atr * pv, 2),
                            "note": "buy/sell stop at the level"})
            out.append(row)
    return out


def sizing(ledger: list[dict]) -> list[str]:
    if not ledger:
        return ["No completed paper trades yet."]
    usd = [t["usd"] for t in ledger]
    per_trade = statistics.mean(usd)
    risk = statistics.median(t["risk"] for t in ledger)
    days = len({t["date"] for t in ledger})
    return [f"- {len(ledger)} trades over {days} sessions, ${sum(usd):+,.2f} total, "
            f"${per_trade:+,.2f}/trade, median risk ${risk:,.0f}/contract",
            f"- one contract at this rate: ${per_trade * len(ledger) / max(days, 1):+,.0f}/session",
            f"- $200 a day would need {200 / max(per_trade * len(ledger) / max(days, 1), 1e-9):.0f} "
            f"contracts = ${risk * 200 / max(per_trade * len(ledger) / max(days, 1), 1e-9):,.0f} "
            f"of risk per stop, against a ${BUFFER:,.0f} buffer"
            if per_trade * len(ledger) / max(days, 1) > 0 else
            "- at a negative rate no size turns this into $200 a day"]


def write(state: dict, rows: list[dict], ledger_today: list[dict], path: Path, title: str,
          unvalidated: bool) -> None:
    now = datetime.now(timezone.utc)
    led = state["ledger"]
    lines = [f"# {title}", "",
             f"Updated {now.strftime('%Y-%m-%dT%H:%MZ')} · started {state['created']} · "
             f"equity **${state['equity']:+,.2f}** across {len(led)} closed trades", ""]
    if unvalidated:
        lines += ["> These rules scored best in the 26,000-test sweep but did not clear every "
                  "gate. Paper only — treat the record as an experiment.", ""]
    if state.get("halted"):
        lines += ["**Halted**: equity reached the $1,000 buffer.", ""]

    lines += ["## Orders standing for the next close", ""]
    if rows:
        lines += ["| session | market | rule | side | level | distance from last close | risk/contract |",
                  "|---|---|---|---|---|---|---|"]
        for r in rows:
            lvl = "—" if r["level"] is None else f"{r['level']:,.2f}"
            dist = "—" if r["dist"] is None else f"{r['dist']:+,.2f}"
            lines.append(f"| {r['date']} | {r['market']} | {r['rule']} | {r['side']} | {lvl} "
                         f"| {dist} | ${r['risk']:,.0f} |")
        worst = sum(r["risk"] for r in rows)
        lines += ["", "A level is a resting buy/sell stop: if the session trades through it, "
                      "the trade is taken and the record shows it after the close.",
                  "", f"**Worst case next session**: if every standing order fills and every "
                  f"one stops out, that is **${worst:,.0f}** against the ${BUFFER:,.0f} "
                  f"buffer. Not hidden."]
    else:
        lines.append("No levels to show — the book is empty or the next session has not started.")

    lines += ["", "## Today (UTC)", ""]
    if ledger_today:
        lines += ["| date | market | rule | side | entry | exit | why | $ |",
                  "|---|---|---|---|---|---|---|---|"]
        for t in ledger_today:
            lines.append(f"| {t['date']} | {t['market']} | {t['rule']} | {t['side']} | "
                         f"{t['entry']:,.2f} | {t['exit']:,.2f} | {t['why']} | ${t['usd']:+,.2f} |")
    else:
        lines.append("No trade closed today. These rules take at most one per market per "
                     "session, so a blank day is the design.")

    if led:
        usd = [t["usd"] for t in led]
        wins = sum(1 for u in usd if u > 0)
        eq = peak = dd = 0.0
        for u in usd:
            eq += u
            peak = max(peak, eq)
            dd = min(dd, eq - peak)
        lines += ["", "## The record", "",
                  f"- {len(led)} trades, {wins} winners ({100 * wins / len(led):.0f}%), "
                  f"net **${sum(usd):+,.2f}**",
                  f"- worst drawdown ${dd:,.0f} against a ${BUFFER:,.0f} buffer", ""]

        # per rule, so a weak rule can be dropped on evidence instead of by feel
        lines += ["**By rule**", "", "| rule | trades | win | net $ | worst DD |",
                  "|---|---|---|---|---|"]
        rules_seen: dict[str, list[dict]] = {}
        for t in led:
            rules_seen.setdefault(t["rule"], []).append(t)
        for rule, ts in sorted(rules_seen.items(),
                               key=lambda kv: -sum(x["usd"] for x in kv[1])):
            u = [x["usd"] for x in ts]
            e = p = d = 0.0
            for x in u:
                e += x
                p = max(p, e)
                d = min(d, e - p)
            lines.append(f"| {rule} | {len(ts)} | "
                         f"{100 * sum(1 for x in u if x > 0) / len(u):.0f}% "
                         f"| ${sum(u):+,.0f} | ${d:,.0f} |")

        # the evaluation, in the terms the account actually uses
        by_day: dict[str, float] = {}
        for t in led:
            by_day[t["date"]] = by_day.get(t["date"], 0.0) + t["usd"]
        net = sum(by_day.values())
        best = max(by_day.values())
        share = 100 * best / net if net > 0 else None
        lines += ["", "## Evaluation tracker", "",
                  f"- net **${net:+,.2f}** of the **${TARGET:,.0f}** target "
                  f"({100 * net / TARGET:+.0f}%)"]
        if BUFFER + net > 0:
            lines.append(f"- **${BUFFER + net:+,.2f}** of room left before the "
                         f"${BUFFER:,.0f} end-of-day buffer is gone")
        else:
            lines.append("- **the buffer is gone** — this attempt failed")
        lines.append(f"- {len(by_day)} sessions traded, best day ${best:+,.2f}, "
                     f"worst day ${min(by_day.values()):+,.2f}")
        if share is not None:
            lines.append(f"- consistency: best day is **{share:.0f}%** of profit "
                         f"(rule: ≤40%) → {'pass' if share <= 40 else '**fail**'}")
        lines.append("")
        lines += ["| date | market | rule | side | entry | exit | why | $ |",
                  "|---|---|---|---|---|---|---|---|"]
        for t in led[-25:]:
            lines.append(f"| {t['date']} | {t['market']} | {t['rule']} | {t['side']} | "
                         f"{t['entry']:,.2f} | {t['exit']:,.2f} | {t['why']} | ${t['usd']:+,.2f} |")

    lines += ["", "## What size would $200 a day take?", ""] + sizing(led) + [""]
    path.write_text("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", type=int, default=0)
    ap.add_argument("--book", default=str(BOOK), help="which book to trade")
    ap.add_argument("--state", default=str(STATE), help="ledger file for that book")
    ap.add_argument("--out", default=str(FORWARD), help="report file for that book")
    args = ap.parse_args()
    book_path, state_path, out_path = Path(args.book), Path(args.state), Path(args.out)
    if args.replay and Path(args.out) == FORWARD:
        out_path = REPLAY_MD          # a replay must never overwrite the forward record

    if not book_path.exists():
        raise SystemExit(f"no {book_path.name} — run trading/lab26k.py first")
    book = json.loads(book_path.read_text())
    if not book:
        raise SystemExit("the book is empty")

    by_sym: dict[str, list[dict]] = {}
    for row in book:
        by_sym.setdefault(row["symbol"], []).append(spec_of(row))
    unvalidated = any(r.get("unvalidated") for r in book)

    now = datetime.now(timezone.utc)
    data = {sym: prep(sym) for sym in by_sym}

    if args.replay:
        state = blank()
        for sym, D in data.items():
            sessions = sorted(set(D["dates"]))
            keep = set(sessions[-args.replay:])
            first = next((i for i, d in enumerate(D["dates"]) if d in keep), len(D["dates"]))
            state["last"][sym] = D["dates"][first - 1] if first else ""
        for sym, D in data.items():
            step(sym, D, by_sym[sym], state, len(D["dates"]))
        rows = [r for sym, D in data.items() for r in watch(D, by_sym[sym], len(D["dates"]) - 1)]
        write(state, rows[:0], state["ledger"], out_path,
              f"Replay — the book over the last {args.replay} sessions", unvalidated)
        print(f"  replay: {len(state['ledger'])} trades, ${state['equity']:+,.2f} → {out_path}")
        return

    state = json.loads(state_path.read_text()) if state_path.exists() else blank()
    fresh: list[dict] = []
    for sym, D in data.items():
        upto = complete_len(D, now)
        if not state["last"].get(sym):
            # never record history as forward: start after the last completed bar
            state["last"][sym] = D["dates"][upto - 1] if upto else ""
            print(f"  {sym}: record starts with the next completed session")
            continue
        fresh += step(sym, D, by_sym[sym], state, upto)
    for t in fresh:
        print(f"  {t['date']} {t['market']} {t['rule']} {t['side']} "
              f"{t['entry']:,.2f}→{t['exit']:,.2f} ({t['why']}) ${t['usd']:+,.2f}")

    rows = [r for sym, D in data.items()
            for r in watch(D, by_sym[sym], complete_len(D, now))]
    state_path.write_text(json.dumps(state, indent=2))
    write(state, rows, fresh, out_path, "The 26,000-test paper book", unvalidated)
    print(f"  {len(state['ledger'])} closed trades, equity ${state['equity']:+,.2f}, "
          f"{len(rows)} orders standing")
    print(f"  written to {FORWARD}")


if __name__ == "__main__":
    main()
