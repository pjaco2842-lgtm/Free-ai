#!/usr/bin/env python3
"""
The lab: many rules × many markets, validated in BOTH directions of time.

The idea that makes this different from research.py
---------------------------------------------------
A normal backtest fits on 2010-2020 and tests on 2020-2026. That one-directional
test can be fooled: a rule can be mediocre for a decade and then catch one regime.
So every rule is validated twice:

    forward  : choose parameters on 2010-2020  -> measure on 2020-2026
    backward : choose parameters on 2020-2026  -> measure on 2010-2020

A rule survives only if the half it did NOT choose on is positive in both
directions. That is a much harder door than either test alone, and it is the
closest thing to "would this have worked if I'd started at any point".

Also reported: the coin flip (random entries, same stop, same number of trades) for
anything that survives, and a portfolio that combines survivors with a hard cap on
risk per trade.

Everything is daily bars, because free intraday history is capped at 60 days.

    python3 trading/lab.py                       # full sweep, both directions
    python3 trading/lab.py --markets NQ=F,ES=F   # one or two markets
    python3 trading/lab.py --equity 25000 --target 26250
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import statistics
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scanner import Bar  # noqa: E402

UA = {"User-Agent": "research-lab/1.0 (local backtest)"}
SPLIT = "2020-01-01"
COMMISSION = 1.24
SLIP_TICKS = 1
MIN_TRAIN_TRADES = 8       # fewer than this and a "best" parameter is coin-flip noise

# symbol: (name, micro $(point, tick)
MARKETS = {
    "NQ=F": ("Nasdaq-100", 2.0, 0.25),      # MNQ
    "ES=F": ("S&P 500", 5.0, 0.25),         # MES
    "YM=F": ("Dow 30", 0.5, 1.0),           # MYM
    "RTY=F": ("Russell 2000", 5.0, 0.10),   # M2K
    "GC=F": ("Gold", 10.0, 0.10),           # MGC
    "CL=F": ("Crude oil", 100.0, 0.01),     # MCL
    # --- added by the second sweep: other asset classes, micros where they exist
    "ZN=F": ("10-Yr T-Note", 1000.0, 0.015625),
    "ZB=F": ("30-Yr T-Bond", 1000.0, 0.03125),
    "6E=F": ("Euro FX", 125000.0, 0.00005),
    "SI=F": ("Silver (micro)", 1000.0, 0.005),
    "HG=F": ("Copper (micro)", 2500.0, 0.0005),
    "NG=F": ("Nat gas (micro)", 2500.0, 0.001),
    "ZC=F": ("Corn", 50.0, 0.25),           # price is in cents: $50 per cent
    "ZS=F": ("Soybeans", 50.0, 0.25),
    "BTC-USD": ("Bitcoin", 1.0, 1.0),
    "ETH-USD": ("Ethereum", 1.0, 0.1),
    "QQQ": ("QQQ ETF", 1.0, 0.01),
    "SPY": ("SPY ETF", 1.0, 0.01),
    "IWM": ("IWM ETF", 1.0, 0.01),
    "GLD": ("GLD ETF", 1.0, 0.01),
    "TLT": ("TLT ETF", 1.0, 0.01),
}

# per-side commission, USD. Equities/ETFs are cheap and pay no futures fee; crypto
# is a maker/taker split, so an ETF-like number is the honest conservative choice.
COMMS = {"QQQ": 0.35, "SPY": 0.35, "IWM": 0.35, "GLD": 0.35, "TLT": 0.35,
         "BTC-USD": 2.0, "ETH-USD": 2.0}


# ----------------------------------------------------------------- data
def fetch_daily(symbol: str) -> list[Bar]:
    start = int(datetime(2009, 1, 1, tzinfo=timezone.utc).timestamp())
    end = int(datetime.now(timezone.utc).timestamp())
    q = urllib.parse.urlencode({"period1": start, "period2": end, "interval": "1d"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?{q}"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode())
    r = data["chart"]["result"][0]
    stamps, quote = r["timestamp"], r["indicators"]["quote"][0]
    out = []
    for i, t in enumerate(stamps):
        o, h, l, c = quote["open"][i], quote["high"][i], quote["low"][i], quote["close"][i]
        if None in (o, h, l, c):
            continue
        out.append(Bar(int(t), float(o), float(h), float(l), float(c), float(quote["volume"][i] or 0)))
    return out


def atr_series(bars: list[Bar], n: int = 14) -> list[float | None]:
    out: list[float | None] = [None] * len(bars)
    trs: list[float] = []
    for i, b in enumerate(bars):
        if i == 0:
            trs.append(b.h - b.l)
            continue
        pc = bars[i - 1].c
        trs.append(max(b.h - b.l, abs(b.h - pc), abs(b.l - pc)))
        if i >= n:
            out[i] = sum(trs[i - n + 1:i + 1]) / n
    return out


def ema(vals: list[float], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(vals)
    k = 2 / (n + 1)
    prev = None
    for i, v in enumerate(vals):
        prev = v if prev is None else v * k + prev * (1 - k)
        if i >= n - 1:
            out[i] = prev
    return out


# ----------------------------------------------------------------- rules
# Each rule returns a list of (signal_index, side). The trade is entered at the
# OPEN of signal_index + 1 and exited at the close of that bar (or after `hold`
# bars), so nothing here can see the future.
def r_open_break(bars, atr, emas, p):
    out = []
    for i in range(2, len(bars)):
        if bars[i].o > bars[i - 1].h:
            out.append((i, "long"))
        elif bars[i].o < bars[i - 1].l:
            out.append((i, "short"))
    return out


def r_fade_trend_day(bars, atr, emas, p):
    out = []
    thr = p["trend"]
    for i in range(3, len(bars)):
        a = atr[i - 1]
        if not a or (bars[i - 1].h - bars[i - 1].l) <= thr * a:
            continue
        up = bars[i - 1].c > bars[i - 2].c
        if bars[i].o > bars[i - 1].h and up:
            out.append((i, "short"))
        elif bars[i].o < bars[i - 1].l and not up:
            out.append((i, "long"))
    return out


def r_continue_trend_day(bars, atr, emas, p):
    out = []
    thr = p["trend"]
    for i in range(3, len(bars)):
        a = atr[i - 1]
        if not a or (bars[i - 1].h - bars[i - 1].l) <= thr * a:
            continue
        up = bars[i - 1].c > bars[i - 2].c
        if bars[i].o > bars[i - 1].h and up:
            out.append((i, "long"))
        elif bars[i].o < bars[i - 1].l and not up:
            out.append((i, "short"))
    return out


def r_monday_gap_fade(bars, atr, emas, p):
    out = []
    for i in range(4, len(bars)):
        if datetime.fromtimestamp(bars[i].t, timezone.utc).weekday() != 0:
            continue
        a = atr[i - 1]
        if not a:
            continue
        gap = (bars[i].o - bars[i - 1].c) / a
        if gap >= p["gap"]:
            out.append((i, "short"))
        elif gap <= -p["gap"]:
            out.append((i, "long"))
    return out


def r_nr_break(bars, atr, emas, p):
    n = p["lookback"]
    out = []
    for i in range(n + 1, len(bars)):
        rng = [bars[j].h - bars[j].l for j in range(i - n, i)]
        if not rng:
            continue
        if (bars[i - 1].h - bars[i - 1].l) > min(rng):
            continue
        if bars[i].o > bars[i - 1].h:
            out.append((i, "long"))
        elif bars[i].o < bars[i - 1].l:
            out.append((i, "short"))
    return out


def r_ema_pullback(bars, atr, emas, p):
    out = []
    fast, slow = emas[p["fast"]], emas[p["slow"]]
    for i in range(1, len(bars)):
        if fast[i] is None or slow[i] is None or fast[i - 1] is None:
            continue
        up = bars[i].c > slow[i]
        touched = bars[i].l <= fast[i] <= bars[i].h
        if up and touched and bars[i].c > bars[i].o:
            out.append((i, "long"))
        elif (not up) and touched and bars[i].c < bars[i].o:
            out.append((i, "short"))
    return out


def r_three_down(bars, atr, emas, p):
    out = []
    n = p["streak"]
    for i in range(n + 1, len(bars)):
        downs = all(bars[i - k].c < bars[i - k - 1].c for k in range(n))
        ups = all(bars[i - k].c > bars[i - k - 1].c for k in range(n))
        if downs:
            out.append((i, "long"))
        elif ups:
            out.append((i, "short"))
    return out


def r_close_extreme(bars, atr, emas, p):
    out = []
    sl = emas[p["slow"]]
    for i in range(1, len(bars)):
        if sl[i] is None:
            continue
        rng = bars[i].h - bars[i].l
        if rng <= 0:
            continue
        pos = (bars[i].c - bars[i].l) / rng
        if pos >= p["edge"] and bars[i].c > sl[i]:
            out.append((i, "long"))
        elif pos <= 1 - p["edge"] and bars[i].c < sl[i]:
            out.append((i, "short"))
    return out


def r_inside_day(bars, atr, emas, p):
    out = []
    for i in range(3, len(bars)):
        p1 = bars[i - 1]
        if not (p1.h <= bars[i - 2].h and p1.l >= bars[i - 2].l):
            continue
        if bars[i].o > p1.h:
            out.append((i, "long"))
        elif bars[i].o < p1.l:
            out.append((i, "short"))
    return out


# entry: "same_open" when the signal IS the open (you can trade the print you are
# reacting to); "next_open" when the signal comes from the close of the bar.
# Getting this wrong silently handicaps every gap rule by one full day.
RULES = {
    "open_break": (r_open_break, [{}], {"stop": 0.5, "entry": "same_open"}),
    "fade_trend_day": (r_fade_trend_day, [{"trend": t} for t in (1.2, 1.5, 2.0)],
                       {"stop": 0.5, "entry": "same_open"}),
    "continue_trend_day": (r_continue_trend_day, [{"trend": t} for t in (1.2, 1.5, 2.0)],
                           {"stop": 0.5, "entry": "same_open"}),
    "monday_gap_fade": (r_monday_gap_fade, [{"gap": g} for g in (0.3, 0.5, 0.8)],
                        {"stop": 0.75, "entry": "same_open"}),
    "nr_break": (r_nr_break, [{"lookback": n} for n in (5, 7, 10)],
                 {"stop": 0.5, "entry": "same_open"}),
    "inside_day": (r_inside_day, [{}], {"stop": 0.5, "entry": "same_open"}),
    "ema_pullback": (r_ema_pullback, [{"fast": 20, "slow": 50}, {"fast": 20, "slow": 200}],
                     {"stop": 1.0, "entry": "next_open"}),
    "three_down": (r_three_down, [{"streak": 3}, {"streak": 4}],
                   {"stop": 1.0, "entry": "next_open"}),
    "close_extreme": (r_close_extreme, [{"edge": 0.8, "slow": 50}, {"edge": 0.9, "slow": 200}],
                      {"stop": 0.75, "entry": "next_open"}),
}


# ----------------------------------------------------------------- simulation
def simulate(bars, atr, signals, stop_atr, pv, tick, hold=1, entry="next_open", comm=None):
    """One position at a time. Stop is checked before the close, always.

    `entry` must stay a string for the whole loop. It used to be overwritten by
    the fill price on the first trade, which quietly sent every later trade in a
    same-open rule in a day late.
    """
    same_open = entry == "same_open"
    cost_usd = 2 * ((COMMISSION if comm is None else comm) + SLIP_TICKS * tick * pv)
    trades = []
    busy = -1
    for i, side in signals:
        j = i if same_open else i + 1
        if j >= len(bars) or j <= busy:
            continue
        a = atr[i - 1] if i >= 1 else None
        if not a:
            continue
        px = bars[j].o
        risk = stop_atr * a
        if risk <= 0:
            continue
        stop = px - risk if side == "long" else px + risk
        exit_px = bars[j].c
        stopped = False
        for k in range(j, min(j + hold, len(bars))):
            if side == "long" and bars[k].l <= stop:
                exit_px, stopped = stop, True
                break
            if side == "short" and bars[k].h >= stop:
                exit_px, stopped = stop, True
                break
            exit_px = bars[k].c
        r = (exit_px - px) / risk if side == "long" else (px - exit_px) / risk
        trades.append({
            "date": datetime.fromtimestamp(bars[j].t, timezone.utc).strftime("%Y-%m-%d"),
            "side": side, "r": r, "net": r - cost_usd / (risk * pv),
            "risk_pts": risk, "stopped": stopped,
        })
        busy = j + hold - 1
    return trades


def score(trades):
    if not trades:
        return {"trades": 0, "net_r": 0.0, "win_rate": 0.0}
    return {
        "trades": len(trades),
        "net_r": round(sum(t["net"] for t in trades), 2),
        "win_rate": round(100 * sum(1 for t in trades if t["net"] > 0) / len(trades), 1),
    }


def coin_flip(bars, atr, trades, stop_atr, pv, tick, runs=400, hold=1, entry="next_open", comm=None):
    if len(trades) < 5:
        return {}
    usable = [i for i in range(2, len(bars) - 2) if atr[i]]
    if not usable:
        return {}
    n = len(trades)
    cost_usd = 2 * ((COMMISSION if comm is None else comm) + SLIP_TICKS * tick * pv)
    real = sum(t["net"] for t in trades)
    better = 0
    same_open = entry == "same_open"   # read once: the loop body reassigns the price
    for _ in range(runs):
        total = 0.0
        for i in random.sample(usable, min(n, len(usable))):
            a = atr[i]
            risk = stop_atr * a
            j = i if same_open else i + 1
            if j >= len(bars):
                continue
            side = random.choice(("long", "short"))
            px = bars[j].o
            stop = px - risk if side == "long" else px + risk
            exit_px = bars[j].c
            for k in range(j, min(j + hold, len(bars))):
                if side == "long" and bars[k].l <= stop:
                    exit_px = stop
                    break
                if side == "short" and bars[k].h >= stop:
                    exit_px = stop
                    break
                exit_px = bars[k].c
            r = (exit_px - px) / risk if side == "long" else (px - exit_px) / risk
            total += r - cost_usd / (risk * pv)
        if total >= real:
            better += 1
    return {"p_value": round(better / runs, 3), "percentile": int(round(100 * (1 - better / runs)))}


def run_rule(bars, atr, emas, name, spec, pv, tick, comm=None):
    fn, grid, cfg = spec
    stop = cfg["stop"]
    entry = cfg["entry"]
    # every (params) variant, simulated once
    variants = []
    for params in grid:
        sig = fn(bars, atr, emas, params)
        trades = simulate(bars, atr, sig, stop, pv, tick, entry=cfg["entry"], comm=comm)
        variants.append((params, trades))

    results = {}
    for label in ("forward", "backward"):
        scored = []
        for params, trades in variants:
            if label == "forward":
                train = [t for t in trades if t["date"] < SPLIT]
            else:
                train = [t for t in trades if t["date"] >= SPLIT]
            if len(train) >= MIN_TRAIN_TRADES:
                scored.append((sum(t["net"] for t in train), params, trades, train))
        if not scored:
            results[label] = {"skip": "not enough training trades"}
            continue
        scored.sort(key=lambda x: -x[0])
        _, best_params, trades, train = scored[0]
        # the test half is always the half the parameters were NOT chosen on
        if label == "forward":
            test = [t for t in trades if t["date"] >= SPLIT]
        else:
            test = [t for t in trades if t["date"] < SPLIT]
        results[label] = {
            "params": best_params,
            "train": score(train),
            "test": score(test),
            "test_trades": test,
        }
    return results


def portfolio(trades_by_rule, start, contracts, pv, kind="fade only"):
    """Combine survivors chronologically, one open position at a time overall."""
    allt = []
    for name, trades in trades_by_rule.items():
        for t in trades:
            allt.append((t["date"], name, t))
    allt.sort(key=lambda x: x[0])
    bal = start
    peak = start
    max_dd = 0.0
    taken = 0
    flat_days = 0
    curve = []
    for date, name, t in allt:
        pnl = t["net"] * t["risk_pts"] * pv * contracts
        bal += pnl
        peak = max(peak, bal)
        max_dd = max(max_dd, peak - bal)
        taken += 1
        curve.append((date, bal, pnl, name))
    return {"trades": taken, "final": bal, "pnl": bal - start, "max_dd": max_dd, "curve": curve}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--markets", default="", help="comma list, empty = all six")
    ap.add_argument("--json", default="lab_results.json")
    ap.add_argument("--equity", type=float, default=25000.0)
    ap.add_argument("--target", type=float, default=26250.0)
    ap.add_argument("--contracts", type=int, default=1)
    ap.add_argument("--runs", type=int, default=400)
    ap.add_argument("--fixed", action="store_true",
                    help="score each rule's first parameter set on both halves instead of re-choosing")
    args = ap.parse_args()

    wanted = [m.strip() for m in args.markets.split(",") if m.strip()] or list(MARKETS)
    report = {"generated": datetime.now(timezone.utc).isoformat(), "split": SPLIT, "rows": []}

    print("=" * 100)
    print("  THE LAB — every rule on every market, validated in both directions of time")
    print(f"  forward: choose on <{SPLIT}, test on >= |   backward: choose on >=, test on <")
    print("=" * 100)

    for symbol in wanted:
        name, pv, tick = MARKETS[symbol]
        comm = COMMS.get(symbol, COMMISSION)
        try:
            bars = fetch_daily(symbol)
        except Exception as err:  # noqa: BLE001 - a dead symbol must not kill the sweep
            print(f"\n{symbol}: fetch failed ({err})")
            continue
        atr = atr_series(bars)
        emas = {k: ema([b.c for b in bars], k) for k in (20, 50, 200)}
        print(f"\n{'-' * 100}\n  {symbol}  {name}  · {len(bars)} daily bars\n{'-' * 100}")
        if args.fixed:
            print(f"  {'rule':<20}{'2010-2020':>11}{'2020-2026':>10}{'':>13}   same params, no re-selection")
        else:
            print(f"  {'rule':<20}{'fwd train':>11}{'fwd test':>10}{'bwd train':>11}{'bwd test':>10}   verdict")

        for rule, spec in RULES.items():
            if args.fixed:
                fn, grid, cfg = spec
                trades = simulate(bars, atr, fn(bars, atr, emas, grid[0]), cfg["stop"], pv, tick,
                                  entry=cfg["entry"], comm=comm)
                is_rows = [t for t in trades if t["date"] < SPLIT]
                oos_rows = [t for t in trades if t["date"] >= SPLIT]
                a, b = score(is_rows), score(oos_rows)
                ok = a["net_r"] > 0 and b["net_r"] > 0 and min(a["trades"], b["trades"]) >= MIN_TRAIN_TRADES
                row = {"symbol": symbol, "rule": rule, "mode": "fixed",
                       "is": a, "oos": b, "pass": ok}
                tail = "PASS" if ok else "fail"
                if ok and args.runs:
                    hold = cfg.get("hold", 1)
                    cf_a = coin_flip(bars, atr, is_rows, cfg["stop"], pv, tick, args.runs,
                                     hold=hold, entry=cfg["entry"], comm=comm)
                    cf_b = coin_flip(bars, atr, oos_rows, cfg["stop"], pv, tick, args.runs,
                                     hold=hold, entry=cfg["entry"], comm=comm)
                    row["coin_flip_is"], row["coin_flip_oos"] = cf_a, cf_b
                    tail = (f"PASS  luck p {cf_a.get('p_value')} / {cf_b.get('p_value')}")
                    row["luck_ok"] = (cf_a.get("p_value", 1) < 0.05 and cf_b.get("p_value", 1) < 0.05)
                print(f"  {rule:<20}{a['net_r']:>11.2f}{b['net_r']:>10.2f}"
                      f"{a['trades']:>7}tr{b['trades']:>6}tr   {tail}")
                report["rows"].append(row)
                continue
            res = run_rule(bars, atr, emas, rule, spec, pv, tick, comm=comm)
            fwd = res.get("forward", {})
            bwd = res.get("backward", {})
            if "skip" in fwd or "skip" in bwd:
                print(f"  {rule:<20}{'—':>11}{'—':>10}{'—':>11}{'—':>10}   skip (sample too small)")
                continue
            ft, bt = fwd["test"], bwd["test"]
            ok = ft["net_r"] > 0 and bt["net_r"] > 0
            verdict = "PASS" if ok else "fail"
            print(f"  {rule:<20}{fwd['train']['net_r']:>11.2f}{ft['net_r']:>10.2f}"
                  f"{bwd['train']['net_r']:>11.2f}{bt['net_r']:>10.2f}   {verdict}")
            cfg = spec[2]
            row = {"symbol": symbol, "name": name, "rule": rule, "forward": {k: v for k, v in fwd.items() if k != "test_trades"},
                   "backward": {k: v for k, v in bwd.items() if k != "test_trades"}, "pass": ok,
                   "fwd_test_trades": ft["trades"], "bwd_test_trades": bt["trades"]}
            if ok:
                cf = coin_flip(bars, atr, fwd["test_trades"], cfg["stop"], pv, tick, args.runs,
                               entry=cfg["entry"], comm=comm)
                cf2 = coin_flip(bars, atr, bwd["test_trades"], cfg["stop"], pv, tick, args.runs,
                                entry=cfg["entry"], comm=comm)
                row["coin_flip_forward"] = cf
                row["coin_flip_backward"] = cf2
                row["trades_forward"] = fwd["test_trades"]
                row["trades_backward"] = bwd["test_trades"]
                print(f"  {'  coin flip':<20}{'':>11}{'p=' + str(cf.get('p_value')):>10}"
                      f"{'':>11}{'p=' + str(cf2.get('p_value')):>10}   pct {cf.get('percentile')}/{cf2.get('percentile')}")
            report["rows"].append(row)

    survivors = [r for r in report["rows"] if r["pass"] and r.get("mode") != "fixed"]
    print(f"\n{'=' * 100}\n  {len(survivors)} of {len(report['rows'])} rule/market combinations are positive in BOTH directions\n{'=' * 100}")
    for r in survivors:
        print(f"  {r['symbol']:<8}{r['rule']:<20} fwd {r['forward']['test']['net_r']:+.2f}R "
              f"({r['fwd_test_trades']} tr)   bwd {r['backward']['test']['net_r']:+.2f}R "
              f"({r['bwd_test_trades']} tr)   p {r.get('coin_flip_forward', {}).get('p_value')} / "
              f"{r.get('coin_flip_backward', {}).get('p_value')}")

    if survivors:
        pv = MARKETS[survivors[0]["symbol"]][1]
        combined = {}
        for r in survivors:
            tr = (r.get("trades_forward") or []) + (r.get("trades_backward") or [])
            combined[f"{r['symbol']}:{r['rule']}"] = tr
        port = portfolio(combined, args.equity, args.contracts, pv)
        print(f"\n  PORTFOLIO of every survivor · {args.contracts} contract(s) · ${args.equity:,.0f} start")
        print(f"    trades {port['trades']}   final ${port['final']:,.0f}   P&L ${port['pnl']:+,.0f}   max DD ${port['max_dd']:,.0f}")
        need = args.target - args.equity
        hit = next((d for d, bal, _, _ in port["curve"] if bal >= args.target), None)
        print(f"    target ${args.target:,.0f} (need +${need:,.0f}): {'reached ' + hit if hit else 'not reached in 16 years'}")
        report["portfolio"] = {k: v for k, v in port.items() if k != "curve"}

    Path(args.json).write_text(json.dumps(report, indent=1))
    print(f"\n  written: {args.json}")
    print("  A PASS here is a candidate, not a conclusion: both halves positive, then the coin flip decides.")


if __name__ == "__main__":
    main()
