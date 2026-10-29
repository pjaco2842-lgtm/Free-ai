#!/usr/bin/env python3
"""
Win rate vs expectancy, on the five contracts you actually want to trade.

The question
------------
"I want to win a coin flip" and "I want the highest winnings" are not the same
request, and on a fixed stop they pull in opposite directions. This script
measures both at once so the trade-off is a number instead of an argument:

  * every entry rule the lab already has
  * every exit on a grid of stop / target / max-hold
  * each setting scored on BOTH halves of history (pre-2020 and post-2020),
    because a win rate that only exists in one half is a fit, not an edge
  * a random-entry coin flip with the identical bracket, to ask whether the
    entry rule did anything at all

High win rate is easy to buy: a tight target and a wide stop wins most of the
time and loses money. The interesting rows are the ones where the win rate is
above 50% AND the net expectancy is positive in both halves.

    python3 trading/edge.py
    python3 trading/edge.py --markets NQ=F,GC=F --min-trades 15
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lab  # noqa: E402
from lab import COMMS, COMMISSION, RULES, atr_series, ema, fetch_daily  # noqa: E402

SPLIT = lab.SPLIT

# The five contracts, priced as the micro where a micro exists, because that is
# what a $25,000 account can actually size. NKD has no micro at CME, so it is
# the full $5/point contract and will be reported as unaffordable if it is.
#   GCZ2026 -> GC=F front month until the November roll
#   ESZ2026 -> ES=F    NQZ2026 -> NQ=F    CLZ2026 -> CL=F    NKDZ2026 -> NKD=F
CONTRACTS = {
    "NQ=F": {"name": "NQZ2026 E-mini Nasdaq", "trade_as": "MNQ", "pv": 2.0, "tick": 0.25},
    "ES=F": {"name": "ESZ2026 E-mini S&P 500", "trade_as": "MES", "pv": 5.0, "tick": 0.25},
    "GC=F": {"name": "GCZ2026 Gold", "trade_as": "MGC", "pv": 10.0, "tick": 0.10},
    "CL=F": {"name": "CLZ2026 Crude oil", "trade_as": "MCL", "pv": 100.0, "tick": 0.01},
    "NKD=F": {"name": "NKDZ2026 Nikkei USD", "trade_as": "NKD (no micro)", "pv": 5.0, "tick": 5.0},
}

STOPS = (0.5, 0.75, 1.0, 1.5)
TARGETS = (0.5, 0.75, 1.0, 1.5, 2.0, 3.0)
HOLDS = (1, 2, 3, 5, 10)


def bracket(bars, atr, signals, stop_atr, target_atr, hold, pv, tick, entry, comm):
    """Enter, then walk forward until stop, target, or max-hold close.

    Stop is tested before target inside the same bar. That is the pessimistic
    reading of an ambiguous bar and it is applied to every row equally.
    """
    same_open = entry == "same_open"
    cost_usd = 2 * (comm + lab.SLIP_TICKS * tick * pv)
    out = []
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
        reward = target_atr * a
        if risk <= 0 or reward <= 0:
            continue
        stop = px - risk if side == "long" else px + risk
        tgt = px + reward if side == "long" else px - reward
        exit_px = bars[j].c
        reason, bars_held = "time", 0
        last = min(j + hold, len(bars))
        for k in range(j, last):
            bars_held = k - j + 1
            if side == "long":
                if bars[k].l <= stop:
                    exit_px, reason = stop, "stop"
                    break
                if bars[k].h >= tgt:
                    exit_px, reason = tgt, "target"
                    break
            else:
                if bars[k].h >= stop:
                    exit_px, reason = stop, "stop"
                    break
                if bars[k].l <= tgt:
                    exit_px, reason = tgt, "target"
                    break
            exit_px = bars[k].c
        r = (exit_px - px) / risk if side == "long" else (px - exit_px) / risk
        out.append({
            "date": datetime.fromtimestamp(bars[j].t, timezone.utc).strftime("%Y-%m-%d"),
            "side": side,
            "r": r,
            "net": r - cost_usd / (risk * pv),
            "risk_pts": risk,
            "pv": pv,
            "round_trip_cost_usd": cost_usd,
            "entry": px, "stop": stop, "target": tgt,
            "exit": exit_px, "reason": reason, "bars_held": bars_held,
            "finished": reason != "time" or j + hold - 1 < len(bars) - 1,
        })
        busy = j + hold - 1
    return out


def bracket_label(row) -> str:
    return f"{row['stop']}/{row['target']}/{row['hold']}"


def stats(trades):
    if not trades:
        return {"trades": 0, "win_rate": 0.0, "net_r": 0.0, "avg_r": 0.0}
    return {
        "trades": len(trades),
        "win_rate": 100 * sum(1 for t in trades if t["net"] > 0) / len(trades),
        "net_r": sum(t["net"] for t in trades),
        "avg_r": sum(t["net"] for t in trades) / len(trades),
    }


def coin_flip(bars, atr, trades, stop_atr, target_atr, hold, pv, tick, entry, comm, runs):
    """Random entries, same bracket, same number of trades. How lucky was the rule?"""
    usable = [i for i in range(2, len(bars) - 2) if atr[i]]
    if not trades or len(usable) < len(trades):
        return None
    real = sum(t["net"] for t in trades)
    same_open = entry == "same_open"
    cost_usd = 2 * (comm + lab.SLIP_TICKS * tick * pv)
    better = 0
    n = len(trades)
    for _ in range(runs):
        total = 0.0
        for i in random.sample(usable, n):
            a = atr[i]
            j = i if same_open else i + 1
            if j >= len(bars):
                continue
            side = random.choice(("long", "short"))
            px = bars[j].o
            risk, reward = stop_atr * a, target_atr * a
            stop = px - risk if side == "long" else px + risk
            tgt = px + reward if side == "long" else px - reward
            exit_px = bars[j].c
            for k in range(j, min(j + hold, len(bars))):
                if side == "long":
                    if bars[k].l <= stop:
                        exit_px = stop
                        break
                    if bars[k].h >= tgt:
                        exit_px = tgt
                        break
                else:
                    if bars[k].h >= stop:
                        exit_px = stop
                        break
                    if bars[k].l <= tgt:
                        exit_px = tgt
                        break
                exit_px = bars[k].c
            r = (exit_px - px) / risk if side == "long" else (px - exit_px) / risk
            total += r - cost_usd / (risk * pv)
        if total >= real:
            better += 1
    return round(better / runs, 3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--markets", default=",".join(CONTRACTS))
    ap.add_argument("--min-trades", type=int, default=12,
                    help="minimum trades in EACH half before a setting is eligible")
    ap.add_argument("--runs", type=int, default=150, help="coin-flip resamples for finalists")
    ap.add_argument("--equity", type=float, default=25000.0)
    ap.add_argument("--save-all", action="store_true",
                    help="write every one of the ~9,300 rows to the json (several MB)")
    ap.add_argument("--json", default="trading/edge.json")
    args = ap.parse_args()

    random.seed(7)
    wanted = [m.strip() for m in args.markets.split(",") if m.strip()]
    rows = []
    cache = {}

    print("=" * 108)
    print("  EDGE — stop/target/hold grid on the five contracts, scored on both halves of history")
    print(f"  split {SPLIT}: a setting has to work in the half that follows and the half that precedes")
    print("=" * 108)

    for symbol in wanted:
        cfg = CONTRACTS[symbol]
        pv, tick = cfg["pv"], cfg["tick"]
        comm = COMMS.get(symbol, COMMISSION)
        try:
            bars = fetch_daily(symbol)
        except Exception as err:  # noqa: BLE001
            print(f"\n{symbol}: fetch failed ({err})")
            continue
        atr = atr_series(bars)
        emas = {k: ema([b.c for b in bars], k) for k in (20, 50, 200)}
        cache[symbol] = (bars, atr, comm)
        print(f"\n{'-' * 108}\n  {symbol}  {cfg['name']}  trade as {cfg['trade_as']}"
              f"   ${pv:,.0f}/point, tick {tick}, {len(bars)} bars\n{'-' * 108}")

        for rule, spec in RULES.items():
            fn, grid, rcfg = spec
            entry = rcfg["entry"]
            for params in grid:
                sig = fn(bars, atr, emas, params)
                for stop_atr, target_atr, hold in itertools.product(STOPS, TARGETS, HOLDS):
                    trades = bracket(bars, atr, sig, stop_atr, target_atr, hold, pv, tick, entry, comm)
                    early = [t for t in trades if t["date"] < SPLIT]
                    late = [t for t in trades if t["date"] >= SPLIT]
                    a, b = stats(early), stats(late)
                    if a["trades"] < args.min_trades or b["trades"] < args.min_trades:
                        continue
                    rows.append({
                        "symbol": symbol, "rule": rule, "params": params,
                        "stop": stop_atr, "target": target_atr, "hold": hold,
                        "entry": entry, "pv": pv, "tick": tick,
                        "pre2020": a, "post2020": b,
                        "win_rate": (a["win_rate"] * a["trades"] + b["win_rate"] * b["trades"])
                        / (a["trades"] + b["trades"]),
                        "avg_r": (a["net_r"] + b["net_r"]) / (a["trades"] + b["trades"]),
                        "net_r": a["net_r"] + b["net_r"],
                        "survives": a["net_r"] > 0 and b["net_r"] > 0,
                        "trades": a["trades"] + b["trades"],
                    })

        print(f"  {len(rows)} eligible settings so far")

    if not rows:
        print("\nno eligible settings — nothing to report")
        return

    # ---- 1. the win-rate ceiling, and what it costs
    print("\n" + "=" * 108)
    print("  1. HIGHEST WIN RATE FIRST — what a coin-flip win rate actually earns you")
    print("=" * 108)
    print(f"  {'market':8}{'rule':18}{'stop/tgt/hold':>15}{'trades':>7}{'win%':>7}"
          f"{'avg R':>7}{'pre-2020':>10}{'post-2020':>11}  verdict")
    top_wr = sorted(rows, key=lambda r: -r["win_rate"])[:12]
    for r in top_wr:
        verdict = "both halves +" if r["survives"] else "loses in a half"
        label = bracket_label(r)
        print(f"  {r['symbol']:8}{r['rule']:18}{label:>15}"
              f"{r['trades']:>7}{r['win_rate']:>7.1f}{r['avg_r']:>7.2f}"
              f"{r['pre2020']['net_r']:>+10.1f}{r['post2020']['net_r']:>+11.1f}  {verdict}")

    above = [r for r in rows if r["win_rate"] >= 50]
    print(f"\n  settings at or above a 50% win rate: {len(above)} of {len(rows)}"
          f"   ·  positive in both halves: {sum(1 for r in above if r['survives'])}")

    # ---- 2. the honest list: both halves positive, then ranked by expectancy
    surv = [r for r in rows if r["survives"]]
    surv.sort(key=lambda r: -r["avg_r"])
    print("\n" + "=" * 108)
    print("  2. POSITIVE IN BOTH HALVES — ranked by expectancy, not by win rate")
    print("=" * 108)
    if not surv:
        print("  none. every stop/target/hold combination lost money in at least one half.")
    else:
        print(f"  {'market':8}{'rule':18}{'stop/tgt/hold':>15}{'trades':>7}{'win%':>7}"
              f"{'avg R':>7}{'total R':>9}{'pre-2020':>10}{'post-2020':>11}")
        for r in surv[:20]:
            label = bracket_label(r)
            print(f"  {r['symbol']:8}{r['rule']:18}{label:>15}"
                  f"{r['trades']:>7}{r['win_rate']:>7.1f}{r['avg_r']:>7.2f}"
                  f"{r['net_r']:>+9.1f}{r['pre2020']['net_r']:>+10.1f}{r['post2020']['net_r']:>+11.1f}")

    # ---- 3. best per market, coin-flipped
    print("\n" + "=" * 108)
    print("  3. BEST SURVIVING SETTING PER MARKET — and whether it beat random entries")
    print("=" * 108)
    finalists = []
    for symbol in wanted:
        mine = [r for r in surv if r["symbol"] == symbol]
        if not mine:
            print(f"  {symbol:8} nothing survived both halves")
            continue
        best = max(mine, key=lambda r: r["avg_r"])
        finalists.append(best)
        bars, atr, comm = cache[symbol]
        fn, _grid, rcfg = RULES[best["rule"]]
        sig = fn(bars, atr, {k: ema([b.c for b in bars], k) for k in (20, 50, 200)}, best["params"])
        trades = bracket(bars, atr, sig, best["stop"], best["target"], best["hold"],
                         best["pv"], best["tick"], best["entry"], comm)
        p = coin_flip(bars, atr, trades, best["stop"], best["target"], best["hold"],
                      best["pv"], best["tick"], best["entry"], comm, args.runs)
        best["coin_flip_p"] = p
        luck = "beats luck" if p is not None and p < 0.05 else "indistinguishable from luck"
        label = bracket_label(best)
        print(f"  {symbol:8}{best['rule']:18}{label:>15}"
              f"  win {best['win_rate']:.0f}%  avg {best['avg_r']:+.2f}R  "
              f"coin-flip p = {p}  ->  {luck}")

    # ---- 4. honest selection test: choose on one half, score on the other
    print("\n" + "=" * 108)
    print("  4. THE SELECTION TEST — choose using one half only, then score the half it never saw")
    print("=" * 108)
    print("  Picking the best row out of thousands is how backtests lie. Here the choice is made")
    print("  blind to the test half, once in each direction, exactly like the lab does.")
    print(f"\n  {'market':8}{'chosen on pre-2020':>42}{'then post-2020':>26}")
    picked = {}
    for symbol in wanted:
        mine = [r for r in rows if r["symbol"] == symbol]
        if not mine:
            continue
        pre = max(mine, key=lambda r: r["pre2020"]["avg_r"])
        post = max(mine, key=lambda r: r["post2020"]["avg_r"])
        held = post["pre2020"]["net_r"] > 0
        held_back = pre["post2020"]["net_r"] > 0
        picked[symbol] = {"by_pre": pre, "by_post": post,
                          "held_forward": held, "held_backward": held_back}
        lab_pre = bracket_label(pre)
        lab_post = bracket_label(post)
        print(f"  {symbol:8}{pre['rule'] + ' ' + lab_pre:>30}{pre['post2020']['net_r']:>+9.1f}R"
              f"  |  {post['rule'] + ' ' + lab_post:>18}{post['pre2020']['net_r']:>+9.1f}R")
    held_n = sum(1 for p in picked.values() if p["held_forward"])
    held_b = sum(1 for p in picked.values() if p["held_backward"])
    print(f"\n  settings chosen on the early half that stayed positive later: {held_n}/{len(picked)}")
    print(f"  settings chosen on the late half that were positive earlier:  {held_b}/{len(picked)}")

    # ---- 5. how often does the basket actually fire?
    print("\n" + "=" * 108)
    print("  5. SIGNAL FREQUENCY — the thing that decides whether a one-week attempt is possible")
    print("=" * 108)
    day_hits = {}
    per_year = {}
    for best in finalists:
        symbol = best["symbol"]
        bars, atr, comm = cache[symbol]
        fn, _g, _c = RULES[best["rule"]]
        sig = fn(bars, atr, {k: ema([b.c for b in bars], k) for k in (20, 50, 200)}, best["params"])
        trades = bracket(bars, atr, sig, best["stop"], best["target"], best["hold"],
                         best["pv"], best["tick"], best["entry"], comm)
        per_year[symbol] = len(trades) / 16.9
        for t in trades:
            day_hits.setdefault(t["date"], []).append(symbol)
    total_days = sum(per_year.values())
    print(f"  {'market':8}{'trades':>8}{'per year':>10}")
    for symbol, rate in per_year.items():
        n = sum(1 for d in day_hits.values() if symbol in d)
        print(f"  {symbol:8}{n:>8}{rate:>10.1f}")
    print(f"\n  combined basket: {total_days:.1f} trades/yr across five markets "
          f"({100 * total_days / 252:.0f}% of sessions have a trade)")
    all_days = sorted(day_hits)
    if all_days:
        first = datetime.strptime(all_days[0], "%Y-%m-%d")
        last = datetime.strptime(all_days[-1], "%Y-%m-%d")
        weeks = max((last - first).days / 7, 1)
        print(f"  calendar weeks with at least one signal: {weeks:.0f} weeks, {len(all_days)} signal days "
              f"-> {100 * len(all_days) / weeks:.0f}% of weeks have something to trade")

    # ---- 6. is one contract even affordable, and what it takes to make $1,250
    print("\n" + "=" * 108)
    print("  6. CAN YOU TRADE IT — one contract's typical risk at $25,000")
    print("=" * 108)
    print(f"  {'market':8}{'avg stop $':>12}{'stop % of 25K':>15}{'fits 1% risk ($250)':>22}")
    for symbol in wanted:
        cfg = CONTRACTS[symbol]
        bars, atr, comm = cache[symbol]
        live = [a for a in atr[-60:] if a]
        a = statistics.median(live) if live else 0
        best = next((r for r in finalists if r["symbol"] == symbol), None)
        stop_mult = best["stop"] if best else 1.0
        risk_usd = a * stop_mult * cfg["pv"]
        print(f"  {symbol:8}{risk_usd:>12,.0f}{100 * risk_usd / 25000:>14.2f}%"
              f"{('fits' if risk_usd <= 250 else 'does not fit'):>22}")

    # ---- 7. the account replay: five markets as one $25,000 account
    print("\n" + "=" * 108)
    print("  7. THE ACCOUNT — all five as one $25,000 book, chasing your real $1,250 target")
    print("=" * 108)
    basket = []
    for best in finalists:
        symbol = best["symbol"]
        bars, atr, comm = cache[symbol]
        fn, _g, _c = RULES[best["rule"]]
        sig = fn(bars, atr, {k: ema([b.c for b in bars], k) for k in (20, 50, 200)}, best["params"])
        for t in bracket(bars, atr, sig, best["stop"], best["target"], best["hold"],
                         best["pv"], best["tick"], best["entry"], comm):
            t["symbol"], t["rule"] = symbol, best["rule"]
            basket.append(t)

    from target import run_account, lucid_start_sweep  # noqa: E402

    for risk_pct in (0.01, 0.02):
        acct = run_account(basket, args.equity, risk_pct, contracts_cap=20,
                           haircut=0.75, daily_stop_frac=0.02, daily_loss_limit=600.0)
        years = 16.9
        cagr = (acct["final"] / args.equity) ** (1 / years) - 1 if acct["final"] > 0 else -1
        print(f"\n  risk {100 * risk_pct:.0f}%/day, 25% haircut on every R, $600 daily loss cap:")
        print(f"    {acct['taken']} trades, {acct['skipped']} skipped (one contract did not fit)")
        print(f"    final ${acct['final']:,.0f} from ${args.equity:,.0f}  ->  {100 * cagr:+.1f}%/yr")
        print(f"    worst drawdown ${acct['max_dd']:,.0f} ({acct['min_dd_pct']:.1f}%) · "
              f"days stopped out: {acct['daily_stop_hits']}")
        for horizon, label in ((None, "no deadline"), (5, "one week")):
            sweep = lucid_start_sweep(basket, args.equity, 1250.0, risk_pct,
                                      max_loss=1000.0, consistency=0.50, contracts_cap=20,
                                      daily_contracts_cap=20, daily_stop_frac=0.02,
                                      daily_loss_limit=600.0, haircut=0.75,
                                      horizon_days=horizon)
            med = sweep["median_days_to_pass"]
            print(f"    {label:11} pass {sweep['passes']}/{sweep['starts']} "
                  f"({sweep['passed_without_breach_pct']:.1f}%)  breach {sweep['breaches']}  "
                  f"no signal {sweep['no_trade_windows']}  median days to pass {med if med is None else round(med)}")

    # ---- 8. the out-of-sample account: settings chosen blind, equity only after the split
    print("\n" + "=" * 108)
    print("  8. OUT-OF-SAMPLE BOOK — settings fixed using 2009-2019 only, account run 2020-2026 only")
    print("=" * 108)
    oos = []
    for symbol, pick in picked.items():
        best = pick["by_pre"]
        bars, atr, comm = cache[symbol]
        fn, _g, _c = RULES[best["rule"]]
        sig = fn(bars, atr, {k: ema([b.c for b in bars], k) for k in (20, 50, 200)}, best["params"])
        for t in bracket(bars, atr, sig, best["stop"], best["target"], best["hold"],
                         best["pv"], best["tick"], best["entry"], comm):
            if t["date"] >= SPLIT:
                t["symbol"], t["rule"] = symbol, best["rule"]
                oos.append(t)
    if oos:
        acct = run_account(oos, args.equity, 0.01, contracts_cap=20, haircut=0.75,
                           daily_stop_frac=0.02, daily_loss_limit=600.0)
        span = 6.8
        print(f"  {acct['taken']} trades over {span:.1f} years · final ${acct['final']:,.0f}"
              f"  ->  {100 * ((acct['final'] / args.equity) ** (1 / span) - 1):+.1f}%/yr")
        print(f"  worst drawdown ${acct['max_dd']:,.0f} ({acct['min_dd_pct']:.1f}% of the $25,000)"
              f" · skipped (did not fit) {acct['skipped']}")
        need = args.equity + 1250
        hit = next((d for d, bal, *_ in acct["curve"] if bal >= need), None)
        print(f"  first time the book reached ${need:,.0f}: {hit or 'never in 2020-2026'}")
    else:
        print("  no out-of-sample trades were produced")

    # The full grid is ~9,300 rows and several megabytes, which does not belong in a
    # repo. Keep the findings and the ends of each distribution; --save-all keeps it all.
    keep = rows if args.save_all else (
        sorted(rows, key=lambda r: -r["avg_r"])[:40]
        + sorted(rows, key=lambda r: -r["win_rate"])[:40]
        + [r for r in finalists if r not in rows])
    out = {"split": SPLIT, "min_trades": args.min_trades,
           "eligible": len(rows), "above_50_win": len(above),
           "survivors": len(surv), "rows_kept": len(keep), "rows": keep,
           "finalists": finalists, "selection_test": picked,
           "signal_days_per_week_pct": round(100 * len(all_days) / weeks, 1) if all_days else None,
           "basket_trades_per_year": round(total_days, 1),
           "oos_account": ({k: v for k, v in acct.items() if k != "curve"} if oos else None)}
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(out, indent=1))
    print(f"\n  written: {args.json}")
    print("  A survivor is a candidate, not a promise: it is a fixed setting on one market,")
    print("  chosen from many, so treat the winner's number as the optimistic end.")


if __name__ == "__main__":
    main()
