#!/usr/bin/env python3
"""The causal paper desk: one rule, one micro, its own ledger.

This is the runner the live book trades, kept separate from the paused legacy
runner so nothing that was retracted is overwritten. It does exactly three things:

  1. settles every completed session after the ledger's last date, using the
     causal fill rules in edge_causal.py (a buy limit below the market cannot be
     scored on a target that traded before the dip);
  2. prints the order for the next session with the exact level, stop, target,
     dollar risk and share of the $1,000 buffer, plus the gap condition that has
     to hold at the open;
  3. tracks the evaluation honestly: end-of-day trailing floor locking at
     $25,100, the 40% consistency share, and target progress.

It refuses to invent a level. If bars cannot be fetched and no --csv is given,
it says so and writes nothing.

    python3 paper_causal.py                 # settle what is finished, print the order
    python3 paper_causal.py --order         # order sheet only, no settlement
    python3 paper_causal.py --csv bars.csv  # date,open,high,low,close
    python3 paper_causal.py --selftest      # fixtures, no files touched
    python3 paper_causal.py --demo          # synthetic bars, writes to /tmp only

Paper only. No broker, no keys, no orders anywhere.
"""
from __future__ import annotations

import argparse
import json
import statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import edge_causal as E

ROOT = Path(__file__).resolve().parent
DESK = ROOT / "desk"
BOOK = DESK / "live-book.json"
STATE = DESK / "live-ledger.json"
OUT = DESK / "live-desk.md"

START, TARGET, MAX_LOSS = E.START_BAL, E.TARGET, E.MAX_LOSS
LOCK_AT, LOCK_TRIG, CONS = E.LOCK_AT, E.LOCK_TRIGGER, E.CONSISTENCY


def load_book(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def next_session(last: str) -> str:
    d = datetime.strptime(last, "%Y-%m-%d").date() + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.isoformat()


def fresh_state(leg: dict) -> dict:
    return {"created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "book": leg["id"], "last": None, "ledger": [], "equity": 0.0,
            "peak_eod": START, "largest_day": 0.0, "passed": False, "breached": False}


# --------------------------------------------------------------------- the order

def order(D: dict, leg: dict) -> dict:
    """The standing order for the session after the last completed bar."""
    i = D["n"] - 1
    pv = E.SPECS[leg["symbol"]]["mult"]
    tick = E.SPECS[leg["symbol"]]["tick"]
    atr = D["atr"][i]
    level = min(D["l"][i - leg["n"] + 1:i + 1])
    close = D["c"][i]
    risk_pts = leg["stop"] * atr
    m = E.EXITS[leg["exit"]]
    px_risk = risk_pts * pv * leg["micros"]
    return {
        "for_session": next_session(D["d"][-1]),
        "from_bar": D["d"][-1],
        "order": f"BUY LIMIT {leg['micros']} {leg.get('contract', 'MES')} @ {level:.2f}",
        "level": level,
        "gap_condition": (f"post only if the open is above the last close {close:.2f}"
                          if leg["gap"] == "with" else "no gap condition"),
        "last_close": close,
        "distance_pct": 100.0 * (level - close) / close,
        "atr": atr,
        "stop": level - risk_pts,
        "target": level + m * risk_pts,
        "risk_usd": px_risk,
        "risk_share": 100.0 * px_risk / MAX_LOSS,
        "buffer_after_stop": MAX_LOSS - px_risk,
        "tick": tick,
    }


def order_lines(o: dict, leg: dict) -> list[str]:
    return [
        f"**{o['order']}** — for the session of {o['for_session']} "
        f"(levels from the completed bar {o['from_bar']}).", "",
        "| field | value |", "|---|---|",
        f"| entry (buy limit) | **{o['level']:.2f}** |",
        f"| condition | {o['gap_condition']} |",
        f"| distance from last close | {o['last_close']:.2f} → {o['distance_pct']:+.2f}% |",
        f"| stop | **{o['stop']:.2f}** ({leg['stop']} × ATR, ATR {o['atr']:.2f}) |",
        f"| target | **{o['target']:.2f}** ({E.EXITS[leg['exit']]}R) |",
        f"| risk if stopped | **${o['risk_usd']:.0f}** = {o['risk_share']:.0f}% of the "
        f"${MAX_LOSS:.0f} buffer |",
        f"| buffer left after one stop | ${o['buffer_after_stop']:.0f} |", "",
        "If the market gaps below the level, the limit fills at the open (better price); "
        "one tick of entry and exit slippage and $1.24 per side are charged on settlement.",
    ]


def open_order(D: dict, leg: dict) -> dict:
    """A leg that enters at the open: the level is unknown, so the rule is printed in points."""
    i = D["n"] - 1
    pv = E.SPECS[leg["symbol"]]["mult"]
    atr = D["atr"][i]
    risk_pts = leg["stop"] * atr
    m = E.EXITS[leg["exit"]]
    px_risk = risk_pts * pv * leg["micros"]
    return {"for_session": next_session(D["d"][-1]), "from_bar": D["d"][-1],
            "last_close": D["c"][i], "atr": atr, "stop_pts": risk_pts,
            "target_pts": m * risk_pts, "risk_usd": px_risk,
            "risk_share": 100.0 * px_risk / MAX_LOSS,
            "buffer_after_stop": MAX_LOSS - px_risk, "tick": E.SPECS[leg["symbol"]]["tick"],
            "contract": leg.get("contract", "MES"), "micros": leg["micros"]}


def open_order_lines(o: dict, leg: dict) -> list[str]:
    c, s, t = o["last_close"], o["stop_pts"], o["target_pts"]
    m, n = o["micros"], o["contract"]
    return [
        f"**MARKET AT THE OPEN, {m} {n}, in the direction of the gap** — for the session of "
        f"{o['for_session']} (rule built from the completed bar {o['from_bar']}).", "",
        "| field | value |", "|---|---|",
        f"| open above {c:.2f} | **BUY {m} {n} at market** |",
        f"| open below {c:.2f} | **SELL {m} {n} at market** |",
        f"| stop | long: entry − **{s:.2f}** pts · short: entry + **{s:.2f}** pts "
        f"({leg['stop']} × ATR {o['atr']:.2f}) |",
        f"| target | long: entry + **{t:.2f}** pts · short: entry − **{t:.2f}** pts "
        f"({E.EXITS[leg['exit']]}R) |",
        f"| risk if stopped | **${o['risk_usd']:.0f}** = {o['risk_share']:.0f}% of the "
        f"${MAX_LOSS:.0f} buffer |",
        f"| buffer left after one stop | ${o['buffer_after_stop']:.0f} |", "",
        "This leg fires on every session whose open differs from the last close, so it always "
        "trades. Its measured expectation is negative — it is here to guarantee forward data, "
        "not because it is expected to earn.",
    ]


# ------------------------------------------------------------------ settlement

def settle(D: dict, leg: dict, state: dict, today: str) -> list[dict]:
    """Append every completed session after state['last'] that the rule traded."""
    pv = E.SPECS[leg["symbol"]]["mult"]
    tick = E.SPECS[leg["symbol"]]["tick"]
    stop = leg.get("daily_stop_usd")
    stood: set[str] = set()
    start = 16                        # ATR(14) warm-up; trade_pnl refuses ATR <= 0
    if state.get("last"):
        after = [i for i, d in enumerate(D["d"]) if d > state["last"]]
        if not after:
            return []
        start = max(start, after[0])
    fresh = []
    for i in range(start, D["n"]):
        if D["d"][i] >= today:          # never settle a session that is still open
            break
        if D["d"][i] in stood:        # the day's stop was reached; stand down
            continue
        if leg.get("entry") == "open":
            sig = E.open_signal(D, i)
            if not sig:
                continue
            entry, kind, side = sig
        else:
            sig = E.signal(D, i, leg["family"], leg["n"], leg["gap"])
            if not sig:
                continue
            entry, kind = sig
            side = 1
        one = E.trade_pnl(D, i, entry, kind, leg["stop"], E.EXITS[leg["exit"]],
                          pv, tick, leg["resolution"], side=side)
        if one is None:
            continue
        atr = D["atr"][i - 1]
        fresh.append({
            "date": D["d"][i],
            "order": (f"{'buy' if side > 0 else 'sell'} market @ {entry:.2f}"
                      if leg.get("entry") == "open"
                      else f"buy limit {leg['micros']} @ {entry:.2f}"),
            "entry": round(entry, 2), "micros": leg["micros"],
            "side": "long" if side > 0 else "short",
            "stop": round(entry - side * leg["stop"] * atr, 2),
            "target": round(entry + side * E.EXITS[leg["exit"]] * leg["stop"] * atr, 2),
            "risk": round(leg["stop"] * atr * pv * leg["micros"], 2),
            "usd": round(one * leg["micros"], 2),
            "result": "win" if one > 0 else "loss",
            "resolution": leg["resolution"],
        })
        if stop and sum(x["usd"] for x in state["ledger"] + fresh
                        if x["date"] == D["d"][i]) <= -stop:
            stood.add(D["d"][i])
    if D["d"][-1] < today:
        state["last"] = D["d"][-1]
    elif fresh:
        state["last"] = fresh[-1]["date"]
    for t in fresh:
        state["ledger"].append(t)
        state["equity"] = round(state["equity"] + t["usd"], 2)
        day = sum(x["usd"] for x in state["ledger"] if x["date"] == t["date"])
        state["largest_day"] = round(max(state["largest_day"], day), 2)
    bal = START + state["equity"]
    state["peak_eod"] = round(max(state["peak_eod"], bal), 2)
    floor = max(state["peak_eod"] - MAX_LOSS, LOCK_AT) if state["peak_eod"] >= LOCK_TRIG \
        else state["peak_eod"] - MAX_LOSS
    profit = bal - START
    state["breached"] = bal < floor
    state["passed"] = bool(profit >= TARGET and state["largest_day"] <= CONS * profit)
    return fresh


def account_lines(state: dict) -> list[str]:
    bal = START + state["equity"]
    floor = max(state["peak_eod"] - MAX_LOSS, LOCK_AT) if state["peak_eod"] >= LOCK_TRIG \
        else state["peak_eod"] - MAX_LOSS
    profit = bal - START
    share = 100.0 * state["largest_day"] / profit if profit > 0 else 0.0
    status = "breached" if state["breached"] else ("passed" if state["passed"] else "running")
    return [
        f"- balance **${bal:,.2f}** ({profit:+,.2f} of the ${TARGET:,.0f} target, "
        f"{100*profit/TARGET:.0f}%)",
        f"- end-of-day floor ${floor:,.2f} — room ${bal-floor:,.0f}",
        f"- largest day ${state['largest_day']:,.0f} = {share:.0f}% of profit "
        f"(limit {100*CONS:.0f}%)",
        f"- status: **{status}**, {len(state['ledger'])} settled trades",
    ]


# ---------------------------------------------------------------------- report

def pace_lines(leg: dict, state: dict) -> list[str]:
    """Your rubric, applied to what has actually settled."""
    targets = leg.get("daily_targets") or []
    stop = leg.get("daily_stop_usd")
    days = sorted({t["date"] for t in state["ledger"]})
    if not days:
        want = ", ".join(f"day {i+1} ${v:,}" for i, v in enumerate(targets))
        out = [f"Nothing settled yet. Ladder: {want or 'unset'}."]
        if stop:
            out.append(f"Daily stand-down at -${stop:,.0f}: one stop ends the session.")
        return out
    L = ["| session | target | actual | cumulative |", "|---|---:|---:|---:|"]
    cum = 0.0
    for i, d in enumerate(days):
        tot = round(sum(t["usd"] for t in state["ledger"] if t["date"] == d), 2)
        cum += tot
        tgt = f"${targets[i]:,}" if i < len(targets) else "—"
        L.append(f"| {d} | {tgt} | ${tot:+,.2f} | ${cum:+,.2f} |")
    best = max(sum(t["usd"] for t in state["ledger"] if t["date"] == d) for d in days)
    mean = round(sum(t["usd"] for t in state["ledger"]) / len(days), 2)
    verdict = ("keep it, no changes" if best >= 500 else
               "keep it, small tweaks" if mean >= 200 else "rework it")
    L += ["", f"- best session ${best:+,.2f}, average ${mean:+,.2f}/session",
          f"- your rubric: **{verdict}** (>= $500 keep, >= $200 a day keep and tweak, "
          "below that rework)"]
    if stop:
        hit = [d for d in days
               if sum(t["usd"] for t in state["ledger"] if t["date"] == d) <= -stop]
        L.append(f"- stand-down at -${stop:,.0f}/session: "
                 + (f"hit on {', '.join(hit)}; no further entry that day" if hit else "not hit"))
    return L


def report(leg: dict, state: dict, o: dict | None, rows: list[str]) -> str:
    L = ["# The causal paper desk", "",
         f"Book `{leg['id']}` — {leg['micros']} micro, {leg['symbol']}, "
         + ("market at the open with the gap, either side" if leg.get("entry") == "open"
            else f"{leg['family']}-{leg['n']}, gap:{leg['gap']}, long only")
         + f", {leg['stop']} ATR stop, {leg['exit']} target.", "",
         "> **Paper only.** The evidence behind this book is unvalidated: `RESEARCH-LOG.md` (o) "
         "showed the old fill model could count a target that traded before the dip. This "
         "runner uses the causal resolution instead, so the first 100 settled trades here "
         "are the test, not a formality.", "",
         "## Next session", ""]
    if not o:
        L += ["No order: not enough completed bars to build a level."]
    elif leg.get("entry") == "open":
        L += open_order_lines(o, leg)
    else:
        L += order_lines(o, leg)
    L += ["", "## Account", ""] + account_lines(state) + [""]
    L += ["## Pace against your rubric", ""] + pace_lines(leg, state) + [""]
    if state["ledger"]:
        L += ["## Ledger", "",
              "| date | entry | stop | target | risk | result | $ |", "|---|---:|---:|---:|---:|---|---:|"]
        for t in state["ledger"]:
            L.append(f"| {t['date']} | {t['entry']:.2f} | {t['stop']:.2f} | {t['target']:.2f} | "
                     f"${t['risk']:.0f} | {t['result']} | ${t['usd']:+.2f} |")
        usd = [t["usd"] for t in state["ledger"]]
        wins = sum(1 for x in usd if x > 0)
        L += ["", f"{len(usd)} trades, {100*wins/len(usd):.0f}% win, "
                  f"${statistics.fmean(usd):+.2f}/trade. Break-even on this book is "
                  f"{100*E_breakeven(leg):.1f}% — below that, more trades lose money."]
    else:
        L += ["## Ledger", "", "No settled trades yet."]
    return "\n".join(L + [""] + rows)


def E_breakeven(leg: dict) -> float:
    """Break-even win rate for this leg at today's ATR-free cost ratio (approximate)."""
    m = E.EXITS[leg["exit"]]
    return 1.0 / (1.0 + m)


# ------------------------------------------------------------------------ demo

def demo() -> None:
    """Synthetic bars: proves the order sheet, settlement and pace work without data."""
    rows, px = [], 5000.0
    for k in range(60):
        d = (date(2026, 9, 1) + timedelta(days=k)).isoformat()
        o = px
        if k % 12 == 11:                     # gap up, then a dip to the prior low
            o = px + 3.0
            if k % 24 == 11:
                c, h, l = o - 15.0, o + 2.0, o - 11.0   # dipped and closed weak
            else:
                c, h, l = o + 9.0, o + 11.0, o - 11.0   # dipped and closed strong
        else:
            c, h, l = o + 2.0, o + 3.0, o - 1.0
        rows.append([d, o, h, l, c])
        px = c
    D = E.build(rows)
    leg = load_book(BOOK)[0] if BOOK.exists() else None
    leg = dict(leg or {"id": "demo", "symbol": "ES=F", "family": "limit_low", "n": 1,
                       "stop": 1.0, "exit": "tp05", "gap": "any", "micros": 1,
                       "resolution": "proven", "daily_targets": [500, 500, 250],
                       "daily_stop_usd": 708})
    o = order(D, leg)
    st = fresh_state(leg)
    st["last"] = None
    settle(D, leg, st, today="2999-01-01")
    print(report(leg, st, o, ["", "_Synthetic demo bars — not a market record._"]))


# --------------------------------------------------------------------- selftest

def selftest() -> None:
    rows = []
    for k in range(20):                       # rising bars: no limit is ever touched
        px = 100.0 + 0.5 * k
        rows.append([(date(2026, 8, 1) + timedelta(days=k)).isoformat(),
                     px, px + 1.0, px + 0.4, px + 0.7])
    rows.append(["2026-08-21", 110.0, 120.0, 95.0, 96.0])   # dips to the prior low
    D = E.build(rows)
    leg = {"id": "t", "symbol": "ES=F", "family": "limit_low", "n": 1, "stop": 1.0,
           "exit": "tp05", "gap": "any", "micros": 1, "resolution": "proven"}
    st = fresh_state(leg)
    settle(D, leg, st, today="2999-01-01")
    assert len(st["ledger"]) == 1, st["ledger"]
    # the target traded before the dip on that bar, so a causal fill exits at the close
    assert st["ledger"][0]["result"] == "loss", st["ledger"][0]
    o = order(D, leg)
    assert o["for_session"] > D["d"][-1]
    assert o["risk_usd"] > 0 and o["stop"] < o["level"] < o["target"]
    assert abs(o["target"] - (o["level"] + 0.5 * (o["level"] - o["stop"]))) < 1e-6
    print("selftest ok: one causal fill, order levels ordered, 0.5R target exact")


def run_leg(leg: dict, args, multi: bool) -> None:
    """Settle, print and journal one book leg. Each leg keeps its own ledger."""
    # Local, not args.csv: assigning into args made the second leg reuse the first
    # leg's bars, so GC and CL were priced off ES levels with CL's multiplier.
    csv = args.csv or str(ROOT / "data" / f"{leg['symbol'].replace('=F', '')}_F_1d.csv")
    if not Path(csv).exists():
        print(f"  {leg['id']}: no bars at {Path(csv).name} — nothing invented, "
              "nothing written. Run fetch_bars.py.")
        return
    if not args.csv:
        print(f"  bars: {Path(csv).relative_to(ROOT)} (run fetch_bars.py to refresh)")
    D = E.load_csv(csv)
    if D["n"] < 22:
        print(f"  {leg['id']}: only {D['n']} bars — ATR(14) and a prior low need 22.")
        return

    slug = leg["id"].replace("=", "-")
    sp = Path(args.state) if args.state != str(STATE) else DESK / (
        f"live-ledger-{slug}.json" if multi else STATE.name)
    out = DESK / (f"live-desk-{slug}.md" if multi else OUT.name)
    state = json.loads(sp.read_text()) if sp.exists() else fresh_state(leg)
    if not sp.exists() and args.since:
        # Journal only from this date: a fresh ledger over ten years of replay is the
        # backtest again, not a live record.
        state["last"] = args.since
    today = datetime.now(timezone.utc).date().isoformat()
    if args.settle_today:
        # The guard below refuses the current bar because it may still be forming. After the
        # 22:00 UTC futures close it is final, and waiting a day would hide tonight's session.
        today = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
    fresh = [] if args.order else settle(D, leg, state, today)
    o = open_order(D, leg) if leg.get("entry") == "open" else order(D, leg)
    if multi:
        print(f"\n===== {leg['id']} ({leg['micros']} micro)\n")
    print(report(leg, state, o, []))
    if not args.order:
        sp.write_text(json.dumps(state, indent=2) + "\n")
        out.write_text(report(leg, state, o, []))
        print(f"\n  {leg['id']}: {len(fresh)} settled, wrote {sp.name} and {out.name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default=str(BOOK))
    ap.add_argument("--state", default=str(STATE))
    ap.add_argument("--csv")
    ap.add_argument("--leg", help="book id, or a unique part of it")
    ap.add_argument("--all", action="store_true", help="every leg, one ledger each")
    ap.add_argument("--since", help="only journal sessions after this date")
    ap.add_argument("--order", action="store_true")
    ap.add_argument("--settle-today", action="store_true",
                    help="settle the current session's bar too; only after the 22:00 UTC close")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    if args.demo:
        demo()
        return

    legs = load_book(Path(args.book))
    if args.leg:
        legs = [l for l in legs if args.leg in l["id"]]
        if not legs:
            print(f"no leg matches {args.leg!r}; the book holds "
                  + ", ".join(l["id"] for l in load_book(Path(args.book))))
            raise SystemExit(2)
    if not args.all:
        legs = legs[:1]
    for leg in legs:
        run_leg(leg, args, multi=len(legs) > 1)


if __name__ == "__main__":
    main()
