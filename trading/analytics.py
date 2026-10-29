#!/usr/bin/env python3
"""
Logs and analytics — the part that tells you which bot to stop listening to.

A trading system without this is a pile of opinions with a ledger attached. Every
close writes a row; this file turns the rows into answers to four questions:

  1. **Which rule earns its keep?** per-rule and per-market trades, win, expectancy.
  2. **Which agent is actually right?** directional accuracy from the recorded
     committee votes, with the skeptic's veto scored too.
  3. **How do trades actually end?** stop, target or clock — and at what hour.
  4. **Is the confidence number meaningful?** board calls carry a confidence; once
     an outcome exists for the same market, the pair becomes a calibration point.

The honest failure mode here is a table with three samples in it. Everything below
twenty samples prints its sample size and says so, because a 100% win rate on four
trades is a coincidence with good formatting.

    python3 trading/analytics.py            # write analytics.json + analytics.md
    python3 trading/analytics.py --print    # also print the tables
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

DESK = Path(__file__).resolve().parent / "desk"
OUT_JSON = DESK / "analytics.json"
OUT_MD = DESK / "analytics.md"

MIN_SAMPLE = 20


def rows(name: str) -> list[dict]:
    path = DESK / name
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "win": 0.0, "avg": 0.0, "total": 0.0}
    wins = sum(1 for v in values if v > 0)
    return {"n": len(values), "win": round(100 * wins / len(values), 1),
            "avg": round(statistics.mean(values), 3), "total": round(sum(values), 2)}


def by_key(ledger: list[dict], key: str) -> dict[str, dict]:
    groups: dict[str, list[float]] = {}
    for r in ledger:
        if r.get("tradeable") is False:
            continue
        groups.setdefault(str(r.get(key, "?")), []).append(float(r.get("net_r", 0)))
    return {k: _stats(v) for k, v in sorted(groups.items())}


def agent_accuracy(decisions: list[dict]) -> dict[str, dict]:
    """Score every agent that took a side. A veto counts as a 'no' vote."""
    tally: dict[str, list[int]] = {}
    for d in decisions:
        if "outcome_r" not in d:
            continue
        good = float(d["outcome_r"]) > 0
        for v in d.get("votes", []):
            vote = v.get("vote")
            if vote not in ("take", "against", "veto", "clear"):
                continue
            predicted_yes = vote in ("take", "clear")
            slot = tally.setdefault(str(v.get("agent", "?")), [0, 0])
            slot[0] += 1
            slot[1] += int(predicted_yes == good)
    return {a: {"n": n, "right_pct": round(100 * c / n) if n else 0,
                "conclusive": n >= MIN_SAMPLE}
            for a, (n, c) in sorted(tally.items())}


def calibration(calls: list[dict], ledger: list[dict]) -> dict:
    """Join a recorded call to the trade it became, then bucket by confidence."""
    settled = sorted({(r.get("symbol"), r.get("date")): float(r.get("net_r", 0))
                      for r in ledger if r.get("tradeable") is not False}.items(),
                     key=lambda kv: str(kv[0][1]))
    pairs = []
    used = set()
    for c in calls:
        if c.get("call") not in ("BUY", "SELL"):
            continue
        for (symbol, date), r in settled:
            if (symbol, date) in used or symbol != c.get("symbol"):
                continue
            if str(c.get("at", ""))[:10] <= str(date):
                pairs.append((float(c.get("confidence", 50)), r))
                used.add((symbol, date))
                break
    if len(pairs) < 10:
        return {"n": len(pairs),
                "note": (f"{len(pairs)} call/outcome pair(s) — calibration needs ten. "
                         "Calls are logged every hour; this fills in as trades settle."),
                "buckets": []}
    buckets = []
    for lo, hi in ((0, 40), (40, 55), (55, 70), (70, 101)):
        chunk = [r for c, r in pairs if lo <= c < hi]
        if chunk:
            buckets.append({"confidence": f"{lo}-{hi - 1}", "n": len(chunk),
                            "win_pct": round(100 * sum(1 for r in chunk if r > 0) / len(chunk)),
                            "avg_r": round(statistics.mean(chunk), 2)})
    brier = statistics.mean(((c / 100) - (1 if r > 0 else 0)) ** 2 for c, r in pairs)
    return {"n": len(pairs), "brier": round(brier, 3), "buckets": buckets,
            "note": ("Brier score: 0.25 is a coin flip, lower is better. If the win "
                     "rate does not rise with confidence, the confidence number is "
                     "decoration.")}


def hours(ledger: list[dict]) -> dict[str, dict]:
    groups: dict[str, list[float]] = {"cash hours": [], "overnight": [], "unknown": []}
    for r in ledger:
        stamp = r.get("exited_at")
        hour = None
        if stamp and len(str(stamp)) >= 13:
            try:
                hour = int(str(stamp)[11:13])
            except ValueError:
                hour = None
        if hour is None:
            groups["unknown"].append(float(r.get("net_r", 0)))
        else:
            groups["cash hours" if 13 <= hour < 20 else "overnight"].append(
                float(r.get("net_r", 0)))
    return {k: _stats(v) for k, v in groups.items() if v}


def build() -> dict:
    ledger = rows("ledger.jsonl")
    shadow = rows("shadow.jsonl")
    decisions = rows("decisions.jsonl") + rows("shadow_decisions.jsonl")
    calls = rows("calls.jsonl")
    orders = rows("orders.jsonl")

    traded = [r for r in ledger if r.get("tradeable") is not False]
    return {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "counts": {"forward": len(ledger), "shadow": len(shadow),
                   "decisions": len(decisions), "calls": len(calls),
                   "order_transitions": len(orders)},
        "overall": _stats([float(r.get("net_r", 0)) for r in traded]),
        "by_rule": by_key(traded, "rule"),
        "by_market": by_key(traded, "symbol"),
        "by_exit": by_key(traded, "exit_reason"),
        "by_hour": hours(traded),
        "agents": agent_accuracy(decisions),
        "calibration": calibration(calls, traded),
        "sample_note": (f"nothing below {MIN_SAMPLE} samples is a conclusion — the "
                        "sample size is printed next to every row"),
    }


def to_markdown(a: dict) -> str:
    out = [f"# Analytics — {a['at']}", "", a["sample_note"], "",
           f"Forward signals: {a['counts']['forward']} · shadow: {a['counts']['shadow']} · "
           f"decisions: {a['counts']['decisions']} · calls: {a['counts']['calls']}", ""]

    def table(title: str, data: dict) -> None:
        out.extend([f"## {title}", ""])
        if not data:
            out.extend(["No data yet.", ""])
            return
        out.extend(["| | n | win | avg R | total R |", "|---|---|---|---|---|"])
        for key, s in data.items():
            out.append(f"| {key} | {s['n']} | {s['win']:.0f}% | {s['avg']:+.2f} | "
                       f"{s['total']:+.2f} |")
        out.append("")

    table("By rule", a["by_rule"])
    table("By market", a["by_market"])
    table("How trades ended", a["by_exit"])
    table("By exit hour", a["by_hour"])

    out.extend(["## Agent accuracy", ""])
    if not a["agents"]:
        out.extend(["No settled decisions yet.", ""])
    else:
        out.extend(["| agent | calls | right | conclusive |", "|---|---|---|---|"])
        for name, s in a["agents"].items():
            out.append(f"| {name} | {s['n']} | {s['right_pct']}% | "
                       f"{'yes' if s['conclusive'] else 'not yet'} |")
        out.append("")

    cal = a["calibration"]
    out.extend(["## Confidence calibration", "", str(cal.get("note", "")), ""])
    for b in cal.get("buckets", []):
        out.append(f"- confidence {b['confidence']}: {b['n']} trades, "
                   f"{b['win_pct']}% win, {b['avg_r']:+.2f}R")
    out.append("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", dest="show", action="store_true")
    args = ap.parse_args()
    a = build()
    DESK.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(a, indent=1))
    OUT_MD.write_text(to_markdown(a))
    print(f"  analytics written to {OUT_MD.name} and {OUT_JSON.name} "
          f"({a['counts']['forward']} forward, {a['counts']['decisions']} decisions)")
    if args.show:
        print(OUT_MD.read_text())


if __name__ == "__main__":
    main()
