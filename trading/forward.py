#!/usr/bin/env python3
"""
Forward-test the rules that survived every backtest gate. No orders, no broker.

Why this exists
---------------
The lab says three rules have an edge that random entries did not produce in both
halves of history. Backtests can still be wrong, so the only thing that settles it
is logging every signal as it appears, one session at a time, and never editing the
file afterwards.

Because the surviving rules open and close inside a single session (enter at the
open, stop is fixed, hold to the close), a completed session is a finished trade:
no pending state, no simulated fills to guess at. That is what makes this simple.

    python3 trading/forward.py --scan      # append any new sessions, print them
    python3 trading/forward.py --report    # the ledger so far vs the backtest
    cat trading/forward/ledger.jsonl       # the raw record, one line per trade

The ledger is append-only. If a session is later revised by the data provider the
old row stays; a mismatch is information, not something to overwrite.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lab import COMMISSION, COMMS, MARKETS, RULES, atr_series, ema, fetch_daily, simulate  # noqa: E402
from target import WATCHLIST  # noqa: E402

LEDGER = Path(__file__).resolve().parent / "forward" / "ledger.jsonl"
SINCE = Path(__file__).resolve().parent / "forward" / "since.txt"
EQUITY = 25000.0
RISK = 0.02          # the size the account analysis shows is needed for one contract to fit


def read_ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    rows = []
    for line in LEDGER.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def scan() -> int:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # A forward test starts the day you start it. Without this, the first run
    # back-fills the whole backtest into the "forward" ledger and it proves nothing.
    if not SINCE.exists():
        SINCE.write_text(today + "\n")
    since = SINCE.read_text().strip() or today
    seen = {(r["symbol"], r["rule"], r["date"]) for r in read_ledger()}
    added = []
    for symbol, rule, params in WATCHLIST:
        name, pv, tick = MARKETS[symbol]
        comm = COMMS.get(symbol, COMMISSION)
        bars = fetch_daily(symbol)
        atr = atr_series(bars)
        emas = {k: ema([b.c for b in bars], k) for k in (20, 50, 200)}
        fn, _grid, cfg = RULES[rule]
        trades = simulate(bars, atr, fn(bars, atr, emas, params), cfg["stop"], pv, tick,
                          hold=cfg.get("hold", 1), entry=cfg["entry"], comm=comm)
        for t in trades:
            if t["date"] >= today:
                continue                       # session not finished yet
            if t["date"] < since:
                continue                       # before this forward test began
            if (symbol, rule, t["date"]) in seen:
                continue
            risk_usd = EQUITY * RISK
            unit = t["risk_pts"] * pv
            contracts = int(risk_usd // unit) if unit > 0 else 0
            row = {"symbol": symbol, "rule": rule, "date": t["date"], "side": t["side"],
                   "r": round(t["r"], 3), "net_r": round(t["net"], 3),
                   "risk_usd": round(unit, 2), "contracts": contracts,
                   "pnl_usd": round(t["net"] * unit * contracts, 2) if contracts else 0.0,
                   "stopped": t["stopped"],
                   "logged": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
            added.append(row)
    if added:
        with LEDGER.open("a") as fh:
            for row in added:
                fh.write(json.dumps(row) + "\n")
    for row in added:
        flag = "" if row["contracts"] else "   (0 contracts: risk too big for the account)"
        print(f"  {row['date']}  {row['symbol']:8}{row['rule']:17}{row['side']:6}"
              f"{row['net_r']:+.2f}R  ${row['pnl_usd']:+,.0f}{flag}")
    if not added:
        print("  no new completed sessions")
    else:
        print(f"  {len(added)} new trade(s) appended to {LEDGER}")
    return len(added)


def report() -> None:
    rows = read_ledger()
    if not rows:
        print("  ledger is empty — run --scan")
        return
    by_rule: dict[str, list[dict]] = {}
    for r in rows:
        by_rule.setdefault(f"{r['symbol']} {r['rule']}", []).append(r)
    since = SINCE.read_text().strip() if SINCE.exists() else "?"
    print(f"  forward ledger since {since}: {len(rows)} trades, "
          f"{len({r['date'] for r in rows})} sessions\n")
    print(f"  {'rule':<28}{'trades':>7}{'win%':>7}{'net R':>8}{'$/trade':>9}")
    for label, rs in sorted(by_rule.items()):
        wins = sum(1 for r in rs if r["net_r"] > 0)
        print(f"  {label:<28}{len(rs):>7}{100 * wins / len(rs):>7.0f}"
              f"{sum(r['net_r'] for r in rs):>8.1f}"
              f"{sum(r['pnl_usd'] for r in rs) / len(rs):>9.0f}")
    print(f"\n  combined {sum(r['net_r'] for r in rows):+.1f}R · ${sum(r['pnl_usd'] for r in rows):+,.0f} "
          f"on ${EQUITY:,.0f} at {100 * RISK:.0f}% risk")
    print("  A sample this small proves nothing yet. The backtest says what to expect;")
    print("  only months of rows say whether the backtest was right.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true", help="append newly completed sessions")
    ap.add_argument("--report", action="store_true", help="summarise the ledger")
    args = ap.parse_args()
    if args.report:
        report()
    elif args.scan:
        scan()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
