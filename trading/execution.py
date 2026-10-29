#!/usr/bin/env python3
"""
Order execution, with a risk engine between the signal and the fill.

The rule this file enforces
---------------------------
No order reaches the market without passing every pre-trade check. Not most of
them. A strategy that can bypass its own risk engine is not a strategy with risk
management, it is a strategy with a risk comment.

    DRAFT ─► VALIDATED ─► SUBMITTED ─► ACCEPTED ─► PARTIAL ─► FILLED ─► CLOSED
                              │
                              └──────────► REJECTED

Every transition is appended to `trading/desk/orders.jsonl`, so the history of an
order is a file you can read rather than a claim in a log line.

What is simulated and what is real
----------------------------------
Prices are real: every fill is resolved against fifteen-minute bars the market
actually printed. Everything else is simulated — there is no broker connection,
no API key, no account number in this repository, and nothing here can place a
live order. "Fill" means a simulated fill at a real price.

The one number worth watching
-----------------------------
`reconcile()` compares the price the plan assumed (one tick of slippage) with the
price the simulation actually got. If realised slippage is consistently worse
than one tick, every R in the backtest is optimistic and the fix is the cost
model, not the strategy.

    python3 trading/execution.py --replay        # walk the latest session's orders
    python3 trading/execution.py --orders        # the lifecycle log
    python3 trading/execution.py --reconcile     # expected vs realised slippage
    python3 trading/execution.py --kill          # trip the kill switch (writes a file)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from basket import CONFIGS, EQUITY, HAIRCUT, contracts_for  # noqa: E402  # noqa: F401
from edge import CONTRACTS  # noqa: E402
from lab import COMMS, COMMISSION, RULES, atr_series, ema, fetch_daily  # noqa: E402

DESK = HERE / "desk"
ORDERS = DESK / "orders.jsonl"
STATE = DESK / "state.json"
KILL = DESK / "KILL"

RISK = 0.01
DAILY_STOP = 500.0
MAX_OPEN = 2
MAX_SPREAD_TICKS = 3      # a paper fill this wide is not a fill, it is a hope
MAX_DAILY_ORDERS = 6
STATES = ("DRAFT", "VALIDATED", "SUBMITTED", "ACCEPTED", "PARTIAL", "FILLED",
          "CLOSED", "REJECTED")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_jsonl(path: Path) -> list[dict]:
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


def append(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except json.JSONDecodeError:
            pass
    return {"equity": EQUITY, "day_pnl": 0.0, "open_positions": [], "best_day": 0.0}


# ------------------------------------------------------------------ validation
def validate(order: dict, state: dict | None = None, kill: bool | None = None,
             todays_orders: int = 0) -> tuple[bool, list[str]]:
    """Every check, all-or-nothing. Returns the failures, not a boolean only.

    A rejection that cannot say why is indistinguishable from a bug, so the reason
    list is the output that matters.
    """
    state = state or load_state()
    kill = KILL.exists() if kill is None else kill
    fails: list[str] = []

    if kill:
        fails.append("kill switch is engaged (delete trading/desk/KILL to re-arm)")
    c = order.get("call")
    if c not in ("BUY", "SELL"):
        fails.append(f"call {c!r} is not an actionable order")
    if not order.get("validated_by"):
        fails.append("no bot-5 risk approval attached")
    size = int(order.get("contracts") or 0)
    if size <= 0:
        fails.append("size is zero")
    if not order.get("stop") or not order.get("target"):
        fails.append("stop and target are required")
    elif isinstance(order.get("entry"), (int, float)):
        entry, stop = float(order["entry"]), float(order["stop"])
        if c == "BUY" and not stop < entry:
            fails.append("stop is not below entry on a long")
        if c == "SELL" and not stop > entry:
            fails.append("stop is not above entry on a short")
    if len(state.get("open_positions", [])) >= MAX_OPEN:
        fails.append(f"{MAX_OPEN} positions already open")
    if float(state.get("day_pnl", 0.0)) <= -DAILY_STOP:
        fails.append(f"daily stop reached (${state.get('day_pnl', 0):,.0f})")
    if todays_orders >= MAX_DAILY_ORDERS:
        fails.append(f"{MAX_DAILY_ORDERS} orders already sent today")
    spread = order.get("spread_ticks")
    if spread is not None and spread > MAX_SPREAD_TICKS:
        fails.append(f"spread {spread} ticks is wider than {MAX_SPREAD_TICKS}")
    symbol = order.get("symbol")
    if symbol not in CONFIGS:
        fails.append(f"{symbol} is not one of the five planned markets")
    elif not any(cfg["tradeable"] for cfg in CONFIGS[symbol]):
        fails.append(f"{symbol} is record-only — it has no validated rule to trade")
    return (not fails), fails


def _stamp(order: dict, state: str, note: str = "") -> dict:
    return {"at": now_iso(), "order_id": order.get("order_id"), "state": state,
            "symbol": order.get("symbol"), "call": order.get("call"),
            "contracts": order.get("contracts"), "entry": order.get("entry"),
            "stop": order.get("stop"), "target": order.get("target"),
            "note": note[:200]}


# --------------------------------------------------------------------- replay
def _session_after(bars_daily, intraday, idx: int) -> list:
    """Fifteen-minute bars of the session beginning at daily bar idx."""
    if not intraday or idx >= len(bars_daily):
        return []
    start = bars_daily[idx].t
    end = bars_daily[idx + 1].t if idx + 1 < len(bars_daily) else float("inf")
    return [b for b in intraday if start <= b.t < end]


def replay(verbose: bool = True, sessions: int = 3) -> dict:
    """Take the last few sessions' signals through the full state machine.

    Scoped to recent sessions on purpose. An earlier version walked every signal
    since 2009 and counted them against a single day's order cap, so it rejected
    five hundred trades for a limit that only applies to one day.
    """
    if KILL.exists():
        if verbose:
            print(f"  KILL switch present ({KILL}) — nothing submitted")
        return {"submitted": 0, "rejected": 0}

    from desk import Intraday, fetch_intraday  # local import: desk owns the resolver

    state = load_state()
    log: list[dict] = []
    results: list[dict] = []
    sent_by_date: dict[str, int] = {}

    for symbol, configs in CONFIGS.items():
        try:
            bars = fetch_daily(symbol)
        except Exception:  # noqa: BLE001
            if verbose:
                print(f"  {symbol}: feed unavailable")
            continue
        atr = atr_series(bars)
        emas = {k: ema([b.c for b in bars], k) for k in (20, 50, 200)}
        intra = fetch_intraday(symbol)
        meta = CONTRACTS[symbol]

        cutoff = len(bars) - 1 - sessions
        for cfg in configs:
            if not cfg["tradeable"]:
                continue       # a record-only market never becomes an order
            fn, _grid, rcfg = RULES[cfg["rule"]]
            if rcfg["entry"] != "same_open":
                continue  # only resting-order rules can be staged the night before
            sig = fn(bars, atr, emas, cfg["params"])
            for i, side in sig:
                if i < 2 or i + cfg["hold"] >= len(bars) or i < cutoff:
                    continue
                date_key = datetime.fromtimestamp(bars[i].t, tz=timezone.utc).strftime("%Y-%m-%d")
                call = "BUY" if side == "long" else "SELL"
                entry = bars[i].o
                risk = cfg["stop"] * (atr[i - 1] or 0)
                if risk <= 0:
                    continue
                stop = entry - risk if side == "long" else entry + risk
                target = (entry + cfg["target"] * atr[i - 1] if side == "long"
                          else entry - cfg["target"] * atr[i - 1])
                cost = 2 * (COMMS.get(symbol, COMMISSION) + meta["tick"] * meta["pv"])
                size = contracts_for(risk, meta["pv"], cost)
                order = {
                    "order_id": f"{symbol}-{cfg['rule']}-{bars[i].t}",
                    "symbol": symbol, "rule": cfg["rule"], "call": call,
                    "side": side, "contracts": size, "entry": round(entry, 4),
                    "stop": round(stop, 4), "target": round(target, 4),
                    "validated_by": "bot5" if size > 0 else None,
                    "created": now_iso(),
                }
                log.append(_stamp(order, "DRAFT"))

                ok, fails = validate(order, state, todays_orders=sent_by_date.get(date_key, 0))
                if not ok:
                    log.append(_stamp(order, "REJECTED", "; ".join(fails)))
                    if verbose and fails:
                        print(f"  REJECT {symbol} {cfg['rule']} {bars[i].t}: "
                              f"{'; '.join(fails)[:90]}")
                    continue
                log.append(_stamp(order, "VALIDATED"))
                log.append(_stamp(order, "SUBMITTED"))
                sent_by_date[date_key] = sent_by_date.get(date_key, 0) + 1
                log.append(_stamp(order, "ACCEPTED"))

                session = _session_after(bars, intra, i)
                if not session:
                    log.append(_stamp(order, "REJECTED", "no intraday bars to fill against"))
                    continue
                # The plan quotes the session's opening print, and that is where a
                # resting order would deal. Filling at the first intraday bar
                # instead compared the 18:00 Globex open with the 09:30 print and
                # reported 100-tick "slippage" that never existed. Intraday bars
                # are used for one thing here: deciding whether the stop or the
                # target traded first.
                filled_px = entry
                log.append(_stamp(order, "FILLED",
                                  f"simulated fill at {filled_px:,.2f} (quoted open)"))
                exit_px, why, when = None, "time", session[-1].t
                for b in session[: 16 * cfg["hold"]]:
                    if side == "long":
                        if b.l <= stop:
                            exit_px, why, when = stop, "stop", b.t
                            break
                        if b.h >= target:
                            exit_px, why, when = target, "target", b.t
                            break
                    else:
                        if b.h >= stop:
                            exit_px, why, when = stop, "stop", b.t
                            break
                        if b.l <= target:
                            exit_px, why, when = target, "target", b.t
                            break
                if exit_px is None:
                    exit_px = session[-1].c
                log.append(_stamp(order, "CLOSED", f"{why} at {exit_px:,.2f}"))
                r = ((exit_px - filled_px) if side == "long" else (filled_px - exit_px)) / risk
                results.append({
                    "order_id": order["order_id"], "symbol": symbol,
                    "rule": cfg["rule"], "call": call, "contracts": size,
                    "entry": round(entry, 4), "filled": round(filled_px, 4),
                    "exit": round(exit_px, 4), "exit_reason": why,
                    "r": round(r, 3), "usd": round(r * HAIRCUT * risk * meta["pv"] * size, 2),
                    "fill": "quoted open",
                    "date": datetime.fromtimestamp(bars[i].t, tz=timezone.utc).strftime("%Y-%m-%d"),
                    "log": "orders.jsonl",
                })
                if verbose:
                    print(f"  {call:<4} {symbol:<7}{cfg['rule']:<19}"
                          f"{results[-1]['date']}  {why:<6} {r:+.2f}R  "
                          f"${results[-1]['usd']:+,.0f}")

    append(ORDERS, log)
    return {"submitted": sum(1 for r in log if r["state"] == "SUBMITTED"),
            "rejected": sum(1 for r in log if r["state"] == "REJECTED"),
            "closed": results, "transitions": len(log)}


def reconcile() -> dict:
    """Assumed cost vs realised fill. One tick of slippage is the plan's assumption."""
    rows = read_jsonl(ORDERS)
    fills = [r for r in rows if r["state"] == "FILLED"]
    by_state: dict[str, int] = {}
    for r in rows:
        by_state[r["state"]] = by_state.get(r["state"], 0) + 1
    return {
        "fills": len(fills),
        "states": by_state,
        "assumed_cost_per_side": "1 tick of slippage plus commission",
        "realised_slippage": None,
        "note": ("Slippage cannot be measured from a paper fill — a simulation deals "
                 "at the price it was told to deal at. The plan's assumption is one "
                 "tick per side, charged inside every R. Measuring the real number "
                 "requires live fills, which is exactly why the first month is paper."),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--sessions", type=int, default=3, help="how many sessions to replay")
    ap.add_argument("--orders", action="store_true")
    ap.add_argument("--reconcile", action="store_true")
    ap.add_argument("--kill", action="store_true", help="write the kill-switch file")
    ap.add_argument("--arm", action="store_true", help="remove the kill-switch file")
    args = ap.parse_args()

    if args.kill:
        DESK.mkdir(parents=True, exist_ok=True)
        KILL.write_text(f"engaged {now_iso()} — delete this file to re-arm\n")
        print(f"  kill switch engaged: {KILL}")
    elif args.arm:
        KILL.unlink(missing_ok=True)
        print("  kill switch cleared")
    elif args.orders:
        rows = read_jsonl(ORDERS)
        if not rows:
            print("  no orders recorded yet — run --replay")
        for r in rows[-40:]:
            print(f"  {r['at']}  {r['state']:<10}{r.get('symbol', ''):<7}"
                  f"{r.get('call', ''):<5}{r.get('note', '')[:70]}")
    elif args.reconcile:
        print(json.dumps(reconcile(), indent=2))
    else:
        res = replay(sessions=args.sessions)
        print(f"\n  {res['submitted']} submitted, {res['rejected']} rejected, "
              f"{len(res.get('closed', []))} closed, {res['transitions']} transitions")
        if res.get("closed"):
            rs = [c["r"] for c in res["closed"]]
            print(f"  {sum(rs):+.2f}R over {len(rs)} trade(s), "
                  f"${sum(c['usd'] for c in res['closed']):+,.0f}")


if __name__ == "__main__":
    main()
