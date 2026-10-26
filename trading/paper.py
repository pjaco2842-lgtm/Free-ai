#!/usr/bin/env python3
"""
Paper-trade the AI Signal Bot on a futures contract. No broker, no keys, no money.

What it does
------------
Every time a candle closes it asks the same rules as trading/ai-signal-bot.pine:

    * is price in a discount (long) or premium (short) part of the recent range?
    * did the Hull-butterfly oscillator or the stochastic cross?
    * is RSI on the right side?
Then it sizes the trade from your account and risk %, opens a simulated position,
and closes it when the stop or the target is touched. Everything is written to
disk after each bar, so stopping the script loses nothing.

Commands
--------
    python3 trading/paper.py --replay 250      # rebuild the last 250 bars as if live
    python3 trading/paper.py --once            # process the newest closed bar
    python3 trading/paper.py --loop             # keep running, act once per bar
    python3 trading/paper.py --status          # equity, open position, recent trades
    python3 trading/paper.py --reset           # wipe the ledger and start again

Files (in trading/paper/)
--------------------------
    state.json     positions, equity, last processed bar
    trades.jsonl   one line per closed trade
    status.md      readable summary, rewritten every time a trade closes

Honest notes
------------
* Fills are simulated: entry at the next bar's open plus slippage, exits at the
  stop/target price plus slippage, commission charged per contract per side.
* When a bar touches both stop and target, the stop is assumed to hit first.
  That is the pessimistic assumption, on purpose.
* NQZ2026 is the December 2026 E-mini Nasdaq-100 contract. Yahoo's NQ=F is the
  front month, which IS December 2026 until the roll, so it is the right proxy;
  check it again after mid-December.
* A full NQ contract is $20 per point. With a 30-point stop that is $600 of risk
  per contract, so a small account cannot trade it at sane risk. Use MNQ ($2 per
  point) until the account is large.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scanner import DEFAULTS, load, series, signals  # noqa: E402

HERE = Path(__file__).resolve().parent
PAPER = HERE / "paper"
STATE_FILE = PAPER / "state.json"
LEDGER = PAPER / "trades.jsonl"
STATUS = PAPER / "status.md"

INSTRUMENTS = {
    # multiplier = dollars per point, tick = smallest price step
    "nq": {"name": "NQ (E-mini Nasdaq-100)", "multiplier": 20.0, "tick": 0.25},
    "mnq": {"name": "MNQ (Micro E-mini Nasdaq-100)", "multiplier": 2.0, "tick": 0.25},
}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fmt(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def fresh_state(args) -> dict:
    inst = INSTRUMENTS[args.instrument]
    return {
        "created": now(),
        "symbol": args.symbol,
        "contract": args.contract,
        "source": args.source,
        "tf": args.tf,
        "instrument": args.instrument,
        "multiplier": inst["multiplier"],
        "tick": inst["tick"],
        "account_start": args.account,
        "equity": args.account,
        "peak_equity": args.account,
        "max_drawdown": 0.0,
        "risk_pct": args.risk_pct,
        "max_contracts": args.max_contracts,
        "sl_atr": args.sl_atr,
        "tp_r": args.tp_r,
        "commission_per_contract": args.commission,
        "slippage_ticks": args.slippage_ticks,
        "last_idx": -1,
        "position": None,
        "pending": None,
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "total_r": 0.0,
        "skipped": [],
    }


def load_state(args) -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return fresh_state(args)


def save_state(state: dict) -> None:
    PAPER.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2))
    os.replace(tmp, STATE_FILE)


def log_trade(trade: dict) -> None:
    PAPER.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(trade) + "\n")


def size_position(state: dict, stop_distance: float) -> int:
    risk_dollars = state["equity"] * state["risk_pct"] / 100.0
    per_contract = stop_distance * state["multiplier"]
    if per_contract <= 0:
        return 0
    by_risk = int(risk_dollars // per_contract)
    cap = int(state.get("max_contracts") or 0)
    if cap > 0:
        return min(by_risk, cap)
    return by_risk


def open_position(state, bars, i, side, stop_distance) -> None:
    qty = size_position(state, stop_distance)
    px = bars[i].o
    slip = state["slippage_ticks"] * state["tick"]
    if qty < 1:
        reason = (f"skip {fmt(bars[i].t)}: risk {stop_distance:.2f} pts x "
                  f"${state['multiplier']:.0f} = ${stop_distance * state['multiplier']:.0f} "
                  f"per contract, over budget")
        state["skipped"].append(reason)
        state["skipped"] = state["skipped"][-20:]
        print(reason)
        return
    entry = px + slip if side == "long" else px - slip
    stop = entry - stop_distance if side == "long" else entry + stop_distance
    target = (entry + stop_distance * state["tp_r"] if side == "long"
              else entry - stop_distance * state["tp_r"])
    state["position"] = {
        "side": side, "qty": qty, "entry": round(entry, 2),
        "stop": round(stop, 2), "target": round(target, 2),
        "stop_distance": round(stop_distance, 2),
        "opened_bar": i, "opened_at": int(bars[i].t), "opened_iso": now(),
    }
    print(f"OPEN  {side.upper():5} {qty} @ {entry:.2f}  stop {stop:.2f}  target {target:.2f}"
          f"  ({fmt(bars[i].t)})")


def close_position(state, bars, i, price, reason) -> None:
    pos = state["position"]
    slip = state["slippage_ticks"] * state["tick"]
    exit_px = price - slip if pos["side"] == "long" else price + slip
    points = (exit_px - pos["entry"]) if pos["side"] == "long" else (pos["entry"] - exit_px)
    gross = points * state["multiplier"] * pos["qty"]
    commission = state["commission_per_contract"] * pos["qty"] * 2
    pnl = gross - commission
    r = pnl / (pos["stop_distance"] * state["multiplier"] * pos["qty"]) if pos["qty"] else 0.0

    state["equity"] += pnl
    state["peak_equity"] = max(state["peak_equity"], state["equity"])
    state["max_drawdown"] = max(state["max_drawdown"], state["peak_equity"] - state["equity"])
    state["trades"] += 1
    state["wins" if pnl > 0 else "losses"] += 1
    state["total_r"] += r

    trade = {
        "contract": state["contract"], "side": pos["side"], "qty": pos["qty"],
        "entry": pos["entry"], "exit": round(exit_px, 2), "points": round(points, 2),
        "pnl": round(pnl, 2), "r": round(r, 2), "reason": reason,
        "opened_at": pos["opened_at"], "closed_at": int(bars[i].t),
        "opened_iso": pos["opened_iso"], "closed_iso": now(),
        "equity_after": round(state["equity"], 2),
    }
    log_trade(trade)
    print(f"CLOSE {pos['side'].upper():5} {pos['qty']} @ {exit_px:.2f}  {reason:6}"
          f"  {points:+.2f} pts  ${pnl:+.2f}  ({r:+.2f}R)  equity ${state['equity']:,.2f}")
    state["position"] = None


def advance(state, bars, s, longs, shorts, upto, max_hold: int) -> None:
    """Walk bars from the last processed index to `upto`, managing one position."""
    start = state["last_idx"] + 1
    for i in range(max(start, 1), upto + 1):
        pos = state["position"]

        if pos:
            # A position is only exposed to bars AFTER the one it was opened on.
            if i > pos["opened_bar"]:
                if pos["side"] == "long":
                    hit_stop, hit_target = bars[i].l <= pos["stop"], bars[i].h >= pos["target"]
                else:
                    hit_stop, hit_target = bars[i].h >= pos["stop"], bars[i].l <= pos["target"]
                if hit_stop:
                    close_position(state, bars, i, pos["stop"], "stop")
                    pos = None
                elif hit_target:
                    close_position(state, bars, i, pos["target"], "target")
                    pos = None
                elif i - pos["opened_bar"] >= max_hold:
                    close_position(state, bars, i, bars[i].c, "expiry")
                    pos = None

        if not state["position"] and state["pending"] and i >= state["pending"]["bar"]:
            open_position(state, bars, i, state["pending"]["side"], state["pending"]["stop"])
            state["pending"] = None

        if not state["position"] and not state["pending"]:
            atr = s["atr"][i]
            if atr and (longs[i] or shorts[i]):
                state["pending"] = {
                    "side": "long" if longs[i] else "short",
                    "bar": i + 1,
                    "stop": atr * state["sl_atr"],
                }
                print(f"SIGNAL {'LONG' if longs[i] else 'SHORT':5} at {fmt(bars[i].t)}"
                      f"  close {bars[i].c:.2f}  atr {atr:.2f}")

        state["last_idx"] = i


def write_status(state) -> None:
    PAPER.mkdir(parents=True, exist_ok=True)
    recent = []
    if LEDGER.exists():
        lines = LEDGER.read_text().strip().splitlines()[-10:]
        recent = [json.loads(line) for line in lines]
    pos = state["position"]
    win_rate = (state["wins"] / state["trades"] * 100) if state["trades"] else 0.0
    body = [
        f"# Paper trading — {state['contract']}",
        "",
        f"_updated {now()} · data: {state['source']} {state['symbol']} {state['tf']} · "
        f"{INSTRUMENTS[state['instrument']]['name']}_",
        "",
        f"- **Equity**: ${state['equity']:,.2f} (start ${state['account_start']:,.2f})",
        f"- **Trades**: {state['trades']} · wins {state['wins']} · losses {state['losses']} · "
        f"win rate {win_rate:.0f}%",
        f"- **Total R**: {state['total_r']:+.2f} · max drawdown ${state['max_drawdown']:,.2f}",
        f"- **Open position**: " + (
            f"{pos['side']} {pos['qty']} @ {pos['entry']} · stop {pos['stop']} · target {pos['target']}"
            if pos else "none"),
        "",
    ]
    if recent:
        body += ["## Last trades", "", "| closed | side | qty | entry | exit | points | $ |", "|---|---|---|---|---|---|---|"]
        for t in recent:
            body.append(f"| {fmt(t['closed_at'])} | {t['side']} | {t['qty']} | {t['entry']:.2f} | "
                        f"{t['exit']:.2f} | {t['points']:+.2f} | {t['pnl']:+.2f} |")
        body.append("")
    if state["skipped"]:
        body += ["## Skipped signals", ""] + [f"- {s}" for s in state["skipped"]] + [""]
    STATUS.write_text("\n".join(body))


def run(args, state) -> None:
    bars = load(args.source, args.symbol, args.tf, args.bars)
    if len(bars) < 120:
        raise SystemExit(f"not enough history ({len(bars)} bars) for {args.symbol} {args.tf}")

    p = {**DEFAULTS, "struct": args.struct, "band": args.band,
         "sl_atr": args.sl_atr, "tp_r": args.tp_r}
    s = series(bars, p)
    longs, shorts = signals(s, p)

    last_closed = len(bars) - 2          # the final bar is still forming
    if args.replay:
        start = max(1, last_closed - args.replay)
        state["last_idx"] = start - 1
        print(f"replaying bars {start}..{last_closed} ({fmt(bars[start].t)} → {fmt(bars[last_closed].t)})")
        advance(state, bars, s, longs, shorts, last_closed, args.max_hold)
    else:
        if state["last_idx"] >= last_closed:
            print(f"no new closed bar since {fmt(bars[state['last_idx']].t)} — nothing to do")
            save_state(state)
            return
        advance(state, bars, s, longs, shorts, last_closed, args.max_hold)

    # Mark-to-market so equity is honest while a position is open.
    equity = state["equity"]
    if state["position"]:
        pos = state["position"]
        last = bars[last_closed].c
        points = (last - pos["entry"]) if pos["side"] == "long" else (pos["entry"] - last)
        equity += points * state["multiplier"] * pos["qty"]

    save_state(state)
    write_status(state)
    win_rate = (state["wins"] / state["trades"] * 100) if state["trades"] else 0.0
    print(f"\n{state['contract']}: equity ${equity:,.2f} ({equity - state['account_start']:+,.2f}) · "
          f"{state['trades']} trades · {win_rate:.0f}% wins · {state['total_r']:+.2f}R total")
    if state["position"]:
        pos = state["position"]
        print(f"open: {pos['side']} {pos['qty']} @ {pos['entry']} · stop {pos['stop']} · target {pos['target']}")
    print(f"status file: {STATUS}")


def cmd_status(state) -> None:
    print(STATUS.read_text() if STATUS.exists() else "no trades yet — run --replay or --once first")


def main() -> None:
    ap = argparse.ArgumentParser(description="Paper-trade the AI Signal Bot on futures. No real orders.")
    ap.add_argument("--symbol", default="NQ=F", help="Yahoo symbol (NQ=F is the front month)")
    ap.add_argument("--contract", default="NQZ2026", help="label used in reports")
    ap.add_argument("--source", default="yahoo", choices=["yahoo"])
    ap.add_argument("--tf", default="5m", choices=["1m", "5m", "15m", "1h"])
    ap.add_argument("--bars", type=int, default=400)
    ap.add_argument("--instrument", default="mnq", choices=sorted(INSTRUMENTS))
    ap.add_argument("--account", type=float, default=25000.0)
    ap.add_argument("--risk-pct", type=float, default=2.0)
    ap.add_argument("--max-contracts", type=int, default=2,
                    help="hard cap on contracts per trade (0 = no cap)")
    ap.add_argument("--sl-atr", type=float, default=1.0)
    ap.add_argument("--tp-r", type=float, default=2.0)
    ap.add_argument("--struct", type=int, default=DEFAULTS["struct"])
    ap.add_argument("--band", type=float, default=DEFAULTS["band"])
    ap.add_argument("--commission", type=float, default=1.50, help="$ per contract per round turn")
    ap.add_argument("--slippage-ticks", type=int, default=1)
    ap.add_argument("--max-hold", type=int, default=48, help="close after this many bars")
    ap.add_argument("--replay", type=int, default=0, help="replay the last N closed bars")
    ap.add_argument("--once", action="store_true", help="process the newest closed bar and exit")
    ap.add_argument("--loop", action="store_true", help="keep running, act once per closed bar")
    ap.add_argument("--interval", type=int, default=60, help="seconds between checks in --loop")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()

    if args.reset:
        for f in (STATE_FILE, LEDGER, STATUS):
            f.unlink(missing_ok=True)
        print("paper state cleared")
        if not (args.once or args.loop or args.replay):
            return

    if args.status:
        cmd_status(load_state(args))
        return

    state = load_state(args)
    if (state["account_start"] != args.account or state["instrument"] != args.instrument
            or state.get("max_contracts") != args.max_contracts):
        print("note: account size, instrument or contract cap changed — run --reset to start over with it")

    if args.loop:
        print(f"looping every {args.interval}s on {args.symbol} {args.tf} — Ctrl+C stops (state is on disk)")
        while True:
            try:
                state = load_state(args)
                run(args, state)
            except Exception as err:  # noqa: BLE001 - keep the loop alive through network hiccups
                print(f"! {type(err).__name__}: {err}")
            time.sleep(args.interval)
    else:
        run(args, state)


if __name__ == "__main__":
    main()
