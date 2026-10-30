#!/usr/bin/env python3
"""
Forward paper trader — the best rule the experiments actually found.

The rule
--------
GC and CL, 15-minute bars, breakout: close beyond the prior 20-bar range with RSI on
the right side of 50 and TRAMA sloping the same way, entered only 13:00-20:00 UTC
(the US cash session), stopped at 1 ATR, targeted at 3 ATR, time stop 48 bars, one
position per market, at most two across the book.

Why those two markets and not all five: in the out-of-sample half, that rule with the
session filter made gold $+37 a session and crude $+16, while ES was -$3 and NQ -$30.
It is the only combination in the whole sweep that survived its own test with a
positive number, and even then the median config across four markets was +$7.

Why catch-up instead of a 15-minute cron
----------------------------------------
Every run replays only the closed bars it has not seen yet, in order, incrementing
each open position's bar counter exactly once. So a run every 15 minutes, every hour,
or once a week produces the *same* trade record — the schedule changes freshness, not
honesty. That is what makes this a paper record rather than a backtest: a bar that has
been settled and passed is not traded into, and nothing is picked after the fact.

Which bars count as "closed"
---------------------------
The cron fires on the quarter hour, the exact moment the newest 15-minute candle closes,
when the feed is still writing it — the same half-formed-bar trap the daily book hit. So
a bar is only tradable once it has been closed for 30 minutes (`SETTLE_SEC`), judged from
its own timestamp rather than the runner's clock. The cost is always working two bars
behind. That is free here.

The one bar that can be revisited
---------------------------------
The newest recorded bar is compared against the feed on the next run. If its prices moved,
the desk restores the state from just before that bar and replays it through the same code
that recorded it, so a trade the revised bar no longer supports is deleted and one it now
supports appears. That is the only revision this file can catch: anything older is frozen,
and a bar that vanishes from the feed is left alone rather than guessed at. Corrections are
shown on the page, before and after, instead of being quietly swapped.

    python3 trading/paper_aggressive.py --replay 10   # last 10 sessions, state untouched
    python3 trading/paper_aggressive.py               # one forward step, saves the ledger
"""

from __future__ import annotations

import argparse
import copy
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aggressive import build, signal  # noqa: E402
from lab import COMMISSION  # noqa: E402
from scalp import MARKETS, day, load  # noqa: E402

HERE = Path(__file__).resolve().parent
DESK = HERE / "desk"
STATE = DESK / "paper-state.json"
FORWARD_MD = DESK / "paper-forward.md"
REPLAY_MD = DESK / "paper-replay.md"
RULE_SRC = DESK / "aggressive.json"

BUFFER = 1000.0                 # the end-of-day drawdown the account dies at
US_HOURS = list(range(13, 21))  # 13:00-20:00 UTC
MAX_OPEN = 2

# A bar is only trusted once it has been closed for this long. The cron fires on the
# quarter hour, which is exactly when the newest bar has just closed and the feed is
# still writing it — trusting that bar immediately is how a half-formed candle becomes
# a recorded trade. Being 30 minutes late costs nothing; the record is not a live order.
SETTLE_SEC = 30 * 60
TF_SEC = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}
KEEP_FIXES = 10                 # how many corrections stay on the page

DEFAULT = {"fast": 9, "slow": 21, "trend": 100, "rsi_len": 14, "tlen": 99,
           "nbars": 20, "lo": 40, "hi": 60, "stop": 1.0, "target": 3.0,
           "hold": 48, "cool": 6, "hours": US_HOURS}

# the two markets the sweep picked, pinned so a later re-sweep cannot silently
# change what is being paper traded
PINNED = {"GC=F": {"tf": "15m", "strat": "breakout"},
          "CL=F": {"tf": "15m", "strat": "breakout"}}


def rules() -> dict:
    """Rule per market: pinned market list, parameters taken from the last sweep."""
    src = {}
    if RULE_SRC.exists():
        try:
            src = json.loads(RULE_SRC.read_text())
        except Exception:  # noqa: BLE001
            src = {}
    chosen = src.get("chosen", []) if isinstance(src, dict) else []

    out = {}
    for sym, base in PINNED.items():
        row = next((r for r in chosen
                    if r.get("symbol") == sym and r.get("tf") == base["tf"]), None)
        params = dict(DEFAULT)
        if row:
            params.update({k: v for k, v in row["params"].items() if k in DEFAULT})
        params["hours"] = US_HOURS
        out[sym] = {"tf": base["tf"],
                    "strat": row["strat"] if row else base["strat"],
                    "params": params}
    return out


def blank_state() -> dict:
    return {"created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "last": {}, "open": {}, "ledger": [], "equity": 0.0,
            "max_open": MAX_OPEN, "halted": False, "undo": {}, "fixes": []}


def fingerprint(b) -> list[float]:
    """The four prices a trade is decided on, rounded so a feed's float noise is not a revision."""
    return [round(b.o, 4), round(b.h, 4), round(b.l, 4), round(b.c, 4)]


def iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def complete_len(bars: list, tf: str, now_ts: float | None = None) -> int:
    """How many bars are finished *and* past the settle window.

    Bars are judged by their own timestamp, never by the runner's clock, so a delayed or
    early run reads the same history. A bar stamped in the future is not a closed bar and
    stops the count — that is the phantom-order guard.
    """
    if not bars:
        return 0
    now_ts = time.time() if now_ts is None else now_ts
    span, cutoff = TF_SEC[tf], now_ts - SETTLE_SEC
    n = 0
    for b in bars:
        if b.t > now_ts or b.t + span > cutoff:
            break
        n += 1
    return n


def remember(state: dict, sym: str, bars: list, i: int) -> None:
    """Keep the state as it was *before* bar i, so a later revision can undo that bar."""
    snap = {k: copy.deepcopy(v) for k, v in state.items() if k not in ("undo", "fixes")}
    state.setdefault("undo", {})[sym] = {
        "ts": bars[i].t, "prev": bars[i - 1].t if i else 0,
        "bar": fingerprint(bars[i]), "state": snap}


def recheck(sym: str, rule: dict, bars: list, state: dict, upto: int) -> list[dict]:
    """Did the feed revise the bar this desk acted on last? If so, rewind and replay it.

    Only the newest recorded bar is re-examined, and only once — on the run after the one
    that recorded it. A revision that arrives later than that is not caught.
    """
    u = (state.get("undo") or {}).get(sym)
    if not u:
        return []
    bar = next((b for b in bars if b.t == u["ts"]), None)
    if bar is None:
        return []                       # gone from the feed: nothing to compare, leave it alone
    now_fp = fingerprint(bar)
    if now_fp == u["bar"]:
        return []

    before = [t for t in state["ledger"] if t["market"] == sym and t["ts"] >= u["ts"]]
    before_open = copy.deepcopy(state["open"].get(sym))
    was_halted = state.get("halted", False)

    state.update(copy.deepcopy(u["state"]))   # back to just before that bar
    state["last"][sym] = u["prev"]
    state["undo"] = {k: v for k, v in (state.get("undo") or {}).items() if k != sym}
    state["halted"] = was_halted or state.get("halted", False)

    step(sym, rule, bars, state, upto)         # same code path that recorded it, so the two cannot drift

    after = [t for t in state["ledger"] if t["market"] == sym and t["ts"] >= u["ts"]]
    fix = {"market": sym, "bar": u["ts"], "when": iso(u["ts"]),
           "was": u["bar"], "now": now_fp, "before": before, "after": after,
           "before_open": before_open, "after_open": copy.deepcopy(state["open"].get(sym))}
    state.setdefault("fixes", []).append(fix)
    state["fixes"] = state["fixes"][-KEEP_FIXES:]
    return [fix]


def step(sym: str, rule: dict, bars: list, state: dict, upto: int) -> list[dict]:
    """Advance one market through every settled bar it has not seen. Returns new trades."""
    p = rule["params"]
    _, pv, tick = MARKETS[sym]
    cost = 2 * (COMMISSION + tick * pv)
    S = build(bars, p)

    last = state["last"].get(sym, 0)
    start = next((i for i, b in enumerate(bars) if b.t > last), None)
    if start is None or upto < 3:
        return []

    fresh: list[dict] = []
    for i in range(max(start, 2), upto):
        b = bars[i]
        if i == upto - 1:
            # the newest bar about to be trusted — keep the state without it
            remember(state, sym, bars, i)
        pos = state["open"].get(sym)

        if pos:
            pos["held"] += 1
            side = pos["side"]
            at_stop = b.l <= pos["stop"] if side > 0 else b.h >= pos["stop"]
            at_tgt = b.h >= pos["target"] if side > 0 else b.l <= pos["target"]
            hit = None
            if at_stop:                       # pessimistic: stop wins an ambiguous bar
                hit = ("stop", pos["stop"])
            elif at_tgt:
                hit = ("target", pos["target"])
            elif pos["held"] >= p["hold"]:
                hit = ("time", b.c)
            if hit:
                net = (hit[1] - pos["entry"]) * side * pv - cost
                trade = {"ts": b.t, "when": datetime.fromtimestamp(b.t, tz=timezone.utc)
                         .strftime("%Y-%m-%d %H:%M"), "market": sym,
                         "side": "long" if side > 0 else "short",
                         "entry": round(pos["entry"], 3), "exit": round(hit[1], 3),
                         "why": hit[0], "held": pos["held"], "usd": round(net, 2),
                         "risk": round(abs(pos["entry"] - pos["stop"]) * pv, 2)}
                state["ledger"].append(trade)
                state["equity"] = round(state["equity"] + net, 2)
                state["open"].pop(sym, None)
                fresh.append(trade)
                if state["equity"] <= -BUFFER:
                    state["halted"] = True
                continue

        if (sym not in state["open"] and len(state["open"]) < state["max_open"]
                and not state["halted"]):
            side = signal(rule["strat"], S, i, p)
            a = S["a"][i - 1] if i else None
            if side and a:
                entry = b.o
                state["open"][sym] = {
                    "side": side, "entry": entry,
                    "opened": datetime.fromtimestamp(b.t, tz=timezone.utc)
                    .strftime("%Y-%m-%d %H:%M"),
                    "stop": entry - side * a * p["stop"],
                    "target": entry + side * a * p["target"], "held": 0}

    if upto >= 3 and bars[upto - 1].t > state["last"].get(sym, 0):
        state["last"][sym] = bars[upto - 1].t
    return fresh


def scale_table(ledger: list[dict]) -> list[str]:
    if not ledger:
        return ["No completed paper trades yet — the first entry has not closed."]
    usd = [t["usd"] for t in ledger]
    risk = statistics.median(t["risk"] for t in ledger)
    days = len({day(t["ts"]) for t in ledger})
    per_day = sum(usd) / max(days, 1)
    lines = ["| contracts | $/day at the measured rate | one stop, all contracts | buffer needed |",
             "|---|---|---|---|"]
    for n in (1, 2, 5, 10):
        lines.append(f"| {n} | ${per_day * n:+,.0f} | ${risk * n:,.0f} "
                     f"| ${risk * n * 3:,.0f} |")
    if per_day > 0:
        lines += ["", f"To make $200 a day at this rate you would need **{200 / per_day:.0f} "
                      f"contracts**, about ${risk * 200 / per_day:,.0f} of risk per stop — "
                      f"{risk * 200 / per_day / BUFFER:.1f}x the entire $1,000 buffer."]
        lines += [f"To make $500 a day: **{500 / per_day:.0f} contracts**."]
    else:
        lines += ["", "At this rate no amount of size turns it into $200 a day — it loses "
                      "money, so more contracts lose faster."]
    return lines


def px_row(fp: list[float]) -> str:
    return " / ".join(f"{x:,.2f}" for x in fp)


def pos_txt(pos: dict | None) -> str:
    if not pos:
        return "flat"
    return (f"{('long' if pos['side'] > 0 else 'short')} @ {pos['entry']:,.2f}, "
            f"stop {pos['stop']:,.2f}, target {pos['target']:,.2f}")


def corrections_block(state: dict) -> list[str]:
    """The revisions the desk had to untangle, or nothing at all."""
    fixes = state.get("fixes") or []
    if not fixes:
        return []
    out = ["## Corrections", "",
           "The feed revised a bar *after* the desk had already acted on it, so the desk went "
           "back to just before that bar and replayed it from the bar as it now stands. The "
           "record below uses the corrected number; the old one stays on this page instead of "
           "being quietly swapped.", ""]
    for f in reversed(fixes):
        out += [f"**{f['when']} UTC · {f['market']}** — bar was {px_row(f['was'])}, "
                f"now {px_row(f['now'])} (open/high/low/close)", ""]
        if f["before"] or f["after"]:
            out += ["| | side | entry | exit | why | held | $ |",
                    "|---|---|---|---|---|---|---|"]
            for label, trades in (("before", f["before"]), ("after", f["after"])):
                for t in trades:
                    out.append(f"| {label} | {t['side']} | {t['entry']:,.2f} | {t['exit']:,.2f} "
                               f"| {t['why']} | {t['held']} | ${t['usd']:+,.2f} |")
        elif f["before_open"] != f["after_open"]:
            out.append(f"Position: before {pos_txt(f['before_open'])}, "
                       f"after {pos_txt(f['after_open'])}.")
        else:
            out.append("No trade either way — the bar moved, the position did not.")
        out.append("")
    return out


def write_report(state: dict, rules: dict, bars_by: dict, path: Path, title: str) -> None:
    led = state["ledger"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    todays = [t for t in led if day(t["ts"]) == today]
    longs = [t for t in led if t["side"] == "long"]
    lines = [f"# {title}", "",
             f"Updated {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')} · "
             f"started {state['created']} · equity ${state['equity']:+,.2f} "
             f"({len(led)} closed trades)", ""]

    lines += corrections_block(state)
    lines += ["## Right now", ""]
    if state.get("halted"):
        lines.append("**Halted**: equity reached the $1,000 buffer. No new entries.")
    if state["open"]:
        lines += ["| market | side | opened | entry | stop | target | bars held |",
                  "|---|---|---|---|---|---|---|"]
        for sym, pos in state["open"].items():
            lines.append(f"| {sym} | {'long' if pos['side'] > 0 else 'short'} | "
                         f"{pos['opened']} | {pos['entry']:,.2f} | {pos['stop']:,.2f} | "
                         f"{pos['target']:,.2f} | {pos['held']} |")
    else:
        lines.append("Flat — nothing open, waiting for the next qualifying breakout.")

    for sym, rule in rules.items():
        bars = bars_by[sym]
        p = rule["params"]
        S = build(bars, p)
        i = len(bars) - 1
        r, tr, a = S["r"][i], S["tr"][i], S["a"][i]
        last_sig = 0
        for back in range(1, 60):
            if signal(rule["strat"], S, i - back + 1, p):
                last_sig = back
                break
        lines += ["", f"**{sym}** {rule['tf']} {rule['strat']}: close {bars[i].c:,.2f}, "
                      f"RSI {r:.0f}, TRAMA {tr:,.2f}, ATR {a:,.2f}"
                      + (f", last signal {last_sig} bars ago" if last_sig else
                         ", no signal in the last 60 bars")]

    lines += ["", "## Today (UTC)", ""]
    if todays:
        lines += ["| time | market | side | entry | exit | why | $ |",
                  "|---|---|---|---|---|---|---|"]
        for t in todays:
            lines.append(f"| {t['when']} | {t['market']} | {t['side']} | {t['entry']:,.2f} "
                         f"| {t['exit']:,.2f} | {t['why']} | ${t['usd']:+,.2f} |")
        lines += ["", f"Day total **${sum(t['usd'] for t in todays):+,.2f}** "
                      f"across {len(todays)} trades."]
    else:
        lines.append("No closed trades today. One trade every few hours is the design, "
                     "not a fault.")

    if led:
        usd = [t["usd"] for t in led]
        wins = sum(1 for u in usd if u > 0)
        eq = peak = dd = 0.0
        for u in usd:
            eq += u
            peak = max(peak, eq)
            dd = min(dd, eq - peak)
        lines += ["", "## The record so far", "",
                  f"- {len(led)} trades, {wins} winners ({100 * wins / len(led):.0f}%), "
                  f"net **${sum(usd):+,.2f}**",
                  f"- ${statistics.mean(usd):+,.2f} per trade, median risk "
                  f"${statistics.median(t['risk'] for t in led):,.0f}",
                  f"- worst drawdown ${dd:,.0f}, {len({day(t['ts']) for t in led})} sessions",
                  f"- longs {len(longs)} (${sum(t['usd'] for t in longs):+,.0f}), "
                  f"shorts {len(led) - len(longs)} "
                  f"(${sum(t['usd'] for t in led if t['side'] == 'short'):+,.0f})", "",
                  "| when | market | side | entry | exit | why | held | $ |",
                  "|---|---|---|---|---|---|---|---|"]
        for t in led[-25:]:
            lines.append(f"| {t['when']} | {t['market']} | {t['side']} | {t['entry']:,.2f} "
                         f"| {t['exit']:,.2f} | {t['why']} | {t['held']} | "
                         f"${t['usd']:+,.2f} |")

    lines += ["", "## What size would this take?", ""] + scale_table(led)
    lines += ["", "The rate above is measured, not projected. It moves every time the "
                  "record moves.", ""]
    path.write_text("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", type=int, default=0,
                    help="simulate the last N sessions without touching the saved state")
    ap.add_argument("--commit", action="store_true", help="accepted for the workflow")
    args = ap.parse_args()

    rule = rules()
    bars_by = {sym: load(sym, r["tf"]) for sym, r in rule.items()}
    for sym, b in bars_by.items():
        if len(b) < 120:
            raise SystemExit(f"{sym}: only {len(b)} bars, cannot evaluate")

    # Only bars that have closed *and* settled are tradable. Everything below works from
    # this count, so no run can act on a candle the feed is still writing.
    upto = {sym: complete_len(bars, rule[sym]["tf"]) for sym, bars in bars_by.items()}
    for sym, n in upto.items():
        if n < 3:
            raise SystemExit(f"{sym}: only {n} settled {rule[sym]['tf']} bars, cannot evaluate")

    if args.replay:
        state = blank_state()
        for sym, bars in bars_by.items():
            sessions = sorted({day(x.t) for x in bars})
            keep = set(sessions[-args.replay:])
            first = next(i for i, x in enumerate(bars) if day(x.t) in keep)
            state["last"][sym] = bars[first - 1].t if first else 0
        for sym in rule:
            step(sym, rule[sym], bars_by[sym], state, upto[sym])
        write_report(state, rule, bars_by, REPLAY_MD,
                     f"Paper replay — last {args.replay} sessions")
        led = state["ledger"]
        print(f"  replay of the last {args.replay} sessions: {len(led)} trades, "
              f"net ${state['equity']:+,.2f}")
        if led:
            print(f"  ${statistics.mean(t['usd'] for t in led):+,.2f}/trade, "
                  f"median risk ${statistics.median(t['risk'] for t in led):,.0f}, "
                  f"{len({day(t['ts']) for t in led})} sessions traded")
        print(f"  written to {REPLAY_MD}")
        return

    state = json.loads(STATE.read_text()) if STATE.exists() else blank_state()
    if not state["last"]:
        # first ever run: start from the newest settled bar, so nothing historical is
        # ever recorded as forward
        for sym, bars in bars_by.items():
            state["last"][sym] = bars[upto[sym] - 1].t
        print("  state created — forward record starts with the next settled bar")
    else:
        for sym in rule:
            state.setdefault("last", {}).setdefault(sym, 0)
        # re-read the newest bar this desk acted on before trusting it again
        for sym in rule:
            for f in recheck(sym, rule[sym], bars_by[sym], state, upto[sym]):
                moved = f"{len(f['before'])} trade(s) → {len(f['after'])}"
                print(f"  corrected {sym} {f['when']}: bar revised ({moved})")

    before = len(state["ledger"])
    for sym in rule:
        step(sym, rule[sym], bars_by[sym], state, upto[sym])

    for t in state["ledger"][before:]:
        print(f"  {t['when']} {t['market']} {t['side']} {t['entry']:,.2f} -> "
              f"{t['exit']:,.2f} ({t['why']}) ${t['usd']:+,.2f}")

    STATE.write_text(json.dumps(state, indent=2))
    write_report(state, rule, bars_by, FORWARD_MD, "Paper forward record")
    print(f"  {len(state['ledger'])} closed trades, equity ${state['equity']:+,.2f}, "
          f"{len(state['open'])} open")
    print(f"  written to {FORWARD_MD}")


if __name__ == "__main__":
    main()
