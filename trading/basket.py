#!/usr/bin/env python3
"""
Paper-trade the five December contracts, the settings that survived the blind test.

Why these settings and not the prettiest ones
---------------------------------------------
trading/edge.py scored ~9,300 stop/target/hold combinations on both halves of
history. Picking the top row is how backtests lie, so it also chose settings
using ONE half and scored the other. Only these came through:

    ES  inside_day       0.5 ATR stop / 1.0 ATR target / 5 bars   58% win, +0.62R
    ES  fade_trend_day   0.5 / 3.0 / 10                           +14.0R early, +9.3R late
    CL  fade_trend_day   0.5 / 3.0 / 2                            +9.1R early, +4.0R late
    NKD continue_trend_day 0.5 / 3.0 / 5   <- picked identically in BOTH
                                              directions, but too big to size

NQ and GC are recorded but not traded: their best setting chosen on the early
half lost money on the late half. They stay in the ledger so we can see for
ourselves rather than argue about it.

Every rule below is an "enter at the open" rule, which means it is a resting
stop order you can place the night before. That is what makes it paper-tradeable
on a phone without watching screens.

    python3 trading/basket.py --scan      # log finished sessions, show what is open
    python3 trading/basket.py --pending    # just tomorrow's orders, nothing is written
    python3 trading/basket.py --report     # the ledger so far
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from edge import CONTRACTS, bracket  # noqa: E402
from lab import COMMS, COMMISSION, RULES, atr_series, ema, fetch_daily  # noqa: E402
from scanner import Bar  # noqa: E402

HERE = Path(__file__).resolve().parent
BOOK = HERE / "basket"
LEDGER = BOOK / "ledger.jsonl"
SINCE = BOOK / "since.txt"

EQUITY = 25000.0
RISK = 0.01          # 1% of equity planned per trade = $250
HAIRCUT = 0.75       # record 75% of the backtest R, the same pessimism as edge.py

# symbol: (rule, params, stop_atr, target_atr, hold, tradeable)
CONFIGS = {
    "ES=F": [
        {"rule": "inside_day", "params": {}, "stop": 0.5, "target": 1.0, "hold": 5, "tradeable": True},
        {"rule": "fade_trend_day", "params": {"trend": 1.2}, "stop": 0.5, "target": 3.0, "hold": 10, "tradeable": True},
    ],
    "CL=F": [
        {"rule": "fade_trend_day", "params": {"trend": 1.5}, "stop": 0.5, "target": 3.0, "hold": 2, "tradeable": True},
    ],
    "NKD=F": [
        {"rule": "continue_trend_day", "params": {"trend": 1.5}, "stop": 0.5, "target": 3.0, "hold": 5, "tradeable": False},
    ],
    "NQ=F": [
        {"rule": "close_extreme", "params": {"edge": 0.9, "slow": 200}, "stop": 0.5, "target": 3.0, "hold": 10, "tradeable": False},
    ],
    "GC=F": [
        {"rule": "nr_break", "params": {"lookback": 7}, "stop": 0.5, "target": 3.0, "hold": 10, "tradeable": False},
    ],
}


def read_ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    return [json.loads(line) for line in LEDGER.read_text().splitlines() if line.strip()]


def contracts_for(risk_pts: float, pv: float, cost: float, equity: float = EQUITY,
                  risk_frac: float = RISK) -> int:
    budget = equity * risk_frac
    unit = risk_pts * pv + cost
    return int(budget // unit) if unit > 0 else 0


def context(symbol: str):
    bars = fetch_daily(symbol)
    atr = atr_series(bars)
    closes = [b.c for b in bars]
    emas = {k: ema(closes, k) for k in (20, 50, 200)}
    return bars, atr, emas


def trades_for(symbol: str, cfg: dict, bars, atr, emas):
    fn, _grid, rcfg = RULES[cfg["rule"]]
    meta = CONTRACTS[symbol]
    comm = COMMS.get(symbol, COMMISSION)
    sig = fn(bars, atr, emas, cfg["params"])
    return bracket(bars, atr, sig, cfg["stop"], cfg["target"], cfg["hold"],
                   meta["pv"], meta["tick"], rcfg["entry"], comm)


def pending_orders(symbol: str, cfg: dict, bars, atr, emas) -> list[dict]:
    """Ask the rule what it would do if the next session opened above / below.

    Every rule here decides on the open, so the decision is a resting stop order
    at the previous bar's extreme. We probe both directions rather than guess
    which side the rule would take.
    """
    fn, _grid, rcfg = RULES[cfg["rule"]]
    if rcfg["entry"] != "same_open" or not bars:
        return []
    meta = CONTRACTS[symbol]
    last = bars[-1]
    eps = max(meta["tick"], 1e-9)
    emas_last = {k: (v[-1] if v else None) for k, v in emas.items()}
    out = []
    for direction, px in (("long", last.h + eps), ("short", last.l - eps)):
        probe = Bar(last.t + 86400, px, px, px, px, 0.0)
        b2 = bars + [probe]
        a2 = atr + [atr[-1] if atr else None]
        e2 = {k: v + [emas_last[k]] for k, v in emas.items()}
        sig = fn(b2, a2, e2, cfg["params"])
        if any(i == len(bars) for i, _side in sig):
            a = atr[-1]
            out.append({
                "side": direction,
                "trigger": px,
                "stop_pts": cfg["stop"] * a,
                "target_pts": cfg["target"] * a,
                "expiry": "next session only",
            })
    return out


def scan(write: bool) -> None:
    BOOK.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not SINCE.exists():
        SINCE.write_text(today + "\n")
    since = SINCE.read_text().strip() or today
    seen = {(r["symbol"], r["rule"], r["date"]) for r in read_ledger()}

    print("=" * 100)
    print(f"  BASKET — forward paper ledger · counting only sessions from {since} onward")
    print(f"  sizing ${EQUITY:,.0f} · {100 * RISK:.0f}% risk per trade · {100 * HAIRCUT:.0f}% of backtest R recorded")
    print("=" * 100)

    new_rows = []
    for symbol, configs in CONFIGS.items():
        try:
            bars, atr, emas = context(symbol)
        except Exception as err:  # noqa: BLE001
            print(f"\n{symbol}: data unavailable ({err})")
            continue
        meta = CONTRACTS[symbol]
        print(f"\n  {symbol}  {meta['name']}  as {meta['trade_as']}  ${meta['pv']:,.0f}/pt"
              f"  last close {bars[-1].c:,.2f}")
        for cfg in configs:
            trades = trades_for(symbol, cfg, bars, atr, emas)
            tag = "" if cfg["tradeable"] else "  [record only]"
            live = [t for t in trades if not t["finished"]]
            fresh = [t for t in trades
                     if t["finished"] and t["date"] >= since and (symbol, cfg["rule"], t["date"]) not in seen]
            print(f"    {cfg['rule']:<19}{cfg['stop']}/{cfg['target']}/{cfg['hold']:<3}{tag}")
            for t in fresh:
                n = contracts_for(t["risk_pts"], t["pv"], t["round_trip_cost_usd"])
                usd = t["net"] * HAIRCUT * t["risk_pts"] * t["pv"] * n
                row = {"symbol": symbol, "rule": cfg["rule"], "params": cfg["params"],
                       "date": t["date"], "side": t["side"], "entry": round(t["entry"], 4),
                       "stop": round(t["stop"], 4), "target": round(t["target"], 4),
                       "exit": round(t["exit"], 4), "reason": t["reason"],
                       "r": round(t["r"], 3), "net_r": round(t["net"], 3),
                       "contracts": n, "usd": round(usd, 2),
                       "tradeable": cfg["tradeable"],
                       "logged": datetime.now(timezone.utc).isoformat()}
                new_rows.append(row)
                mark = "WIN " if t["net"] > 0 else "LOSS"
                print(f"      {mark} {t['date']} {t['side']:<5} {t['reason']:<6}"
                      f" {t['r']:+.2f}R  {n} contract(s)  ${usd:+,.0f}")
            for t in live:
                n = contracts_for(t["risk_pts"], t["pv"], t["round_trip_cost_usd"])
                print(f"      OPEN  {t['date']} {t['side']:<5} entry {t['entry']:,.2f}"
                      f"  stop {t['stop']:,.2f}  target {t['target']:,.2f}"
                      f"  held {t['bars_held']}/{cfg['hold']} bars  {n} contract(s)")
            for order in pending_orders(symbol, cfg, bars, atr, emas):
                cost = 2 * (COMMS.get(symbol, COMMISSION) + meta["tick"] * meta["pv"])
                n = contracts_for(order["stop_pts"], meta["pv"], cost)
                fits = f"{n} contract(s)" if n > 0 else "does not fit 1% risk"
                print(f"      ORDER {order['side'].upper():<5} stop order at {order['trigger']:,.2f}"
                      f"  ·  risk {order['stop_pts']:,.2f} pts  ·  target {order['target_pts']:,.2f} pts"
                      f"  ·  {fits}  ·  {order['expiry']}")
            if not fresh and not live:
                print("      (nothing new)")

    if new_rows and write:
        with LEDGER.open("a") as fh:
            for row in new_rows:
                fh.write(json.dumps(row) + "\n")
        print(f"\n  appended {len(new_rows)} closed trade(s) to {LEDGER}")
    elif new_rows:
        print(f"\n  {len(new_rows)} trade(s) would be appended (dry run)")
    else:
        print("\n  no new closed trades")


def report() -> None:
    rows = read_ledger()
    print("=" * 100)
    print("  BASKET LEDGER")
    print("=" * 100)
    if not rows:
        print("  empty — run --scan after a session closes")
        return
    traded = [r for r in rows if r.get("tradeable")]
    print(f"  {len(rows)} logged signals, {len(traded)} on tradeable markets")
    for group, label in ((rows, "all logged"), (traded, "tradeable only")):
        if not group:
            continue
        rs = [r["net_r"] for r in group]
        wins = sum(1 for r in group if r["net_r"] > 0)
        usd = sum(r["usd"] for r in group)
        print(f"\n  {label}: {len(group)} trades · win {100 * wins / len(group):.0f}%"
              f" · {sum(rs):+.2f}R · ${usd:+,.0f}")
        if len(rs) > 2:
            print(f"    avg {statistics.mean(rs):+.2f}R · stdev {statistics.pstdev(rs):.2f}"
                  f" · best {max(rs):+.2f} · worst {min(rs):+.2f}")
    print("\n  expectation from the backtest, for comparison: ES inside_day +0.62R avg,")
    print("  ES fade +0.58R, CL fade +0.55R. A forward sample of 20 trades or fewer says")
    print("  almost nothing either way — that is the point of logging instead of arguing.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true", help="log finished sessions, show what is open")
    ap.add_argument("--pending", action="store_true", help="only print resting orders, write nothing")
    ap.add_argument("--report", action="store_true", help="summarise the ledger")
    ap.add_argument("--dry-run", action="store_true", help="do not write to the ledger")
    args = ap.parse_args()
    if args.report:
        report()
    elif args.pending:
        scan(write=False)
    else:
        scan(write=not args.dry_run)


if __name__ == "__main__":
    main()
