#!/usr/bin/env python3
"""
Study the rules on five futures markets, honestly: learn on 2010-2020, then
open 2020-2026 exactly once and report whatever happens.

    python3 trading/research.py

Why it is built this way
------------------------
If you tune parameters on all your data and then look at the result on the same
data, you will always find something that "works". The parameter set that wins
on 2010-2020 is chosen here WITHOUT ever seeing 2020-2026, and the out-of-sample
number is printed unedited. If it degrades, that is the finding.

Data
----
Yahoo daily bars for the continuous front-month series:
    NQ=F  Nasdaq-100      ES=F  S&P 500      GC=F  Gold
    CL=F  Crude oil       NKD=F Nikkei 225 (USD)
Continuous series are not tradable instruments: they stitch contracts together
and ignore roll cost, so treat results as directional evidence, not P&L.

What is tuned
-------------
struct (swing lookback), band (premium/discount dead zone), sl_atr (stop in
ATRs), tp_r (target as a multiple of risk). Everything else stays fixed.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scanner import Bar, DEFAULTS, series, signals  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (compatible; local-research/1.0)"}

SYMBOLS = {
    "NQ=F": "Nasdaq-100",
    "ES=F": "S&P 500",
    "GC=F": "Gold",
    "CL=F": "Crude oil",
    "NKD=F": "Nikkei 225 (USD)",
}

IS_START = int(datetime(2010, 1, 1, tzinfo=timezone.utc).timestamp())
IS_END = int(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp())
OOS_END = int(datetime.now(timezone.utc).timestamp())

GRID = {
    "struct": [30, 50, 80],
    "band": [0.0, 5.0, 10.0],
    "sl_atr": [1.0, 2.0],
    "tp_r": [1.5, 2.0, 3.0],
}


def fetch_daily(symbol: str, start: int, end: int) -> list[Bar]:
    query = urllib.parse.urlencode({"period1": start, "period2": end, "interval": "1d"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?{query}"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode())
    result = data["chart"]["result"][0]
    stamps, quote = result["timestamp"], result["indicators"]["quote"][0]
    bars = []
    for i, t in enumerate(stamps):
        o, h, l, c = quote["open"][i], quote["high"][i], quote["low"][i], quote["close"][i]
        if None in (o, h, l, c):
            continue
        bars.append(Bar(int(t), float(o), float(h), float(l), float(c), float(quote["volume"][i] or 0)))
    return bars


def simulate(bars: list[Bar], s: dict, longs: list[bool], shorts: list[bool],
             sl_atr: float, tp_r: float, max_hold: int = 20) -> dict:
    """One position at a time; entry next open; stop assumed first inside a bar."""
    trades: list[float] = []
    i = 2
    while i < len(bars) - 1:
        if not (longs[i] or shorts[i]):
            i += 1
            continue
        side = "long" if longs[i] else "short"
        atr = s["atr"][i]
        if not atr:
            i += 1
            continue
        risk = atr * sl_atr
        entry = bars[i + 1].o
        stop = entry - risk if side == "long" else entry + risk
        target = entry + risk * tp_r if side == "long" else entry - risk * tp_r
        outcome = None
        j = i + 1
        while j < len(bars) and j <= i + max_hold:
            if side == "long":
                hit_stop, hit_target = bars[j].l <= stop, bars[j].h >= target
            else:
                hit_stop, hit_target = bars[j].h >= stop, bars[j].l <= target
            if hit_stop:
                outcome = -1.0
            elif hit_target:
                outcome = tp_r
            if outcome is not None:
                break
            j += 1
        if outcome is None:
            last = bars[min(j, len(bars) - 1)].c
            outcome = ((last - entry) if side == "long" else (entry - last)) / risk
        trades.append(outcome)
        i = j + 1

    if not trades:
        return {"trades": 0, "win_rate": None, "total_r": 0.0, "avg_r": None, "max_dd": 0.0}
    equity = peak = dd = 0.0
    for r in trades:
        equity += r
        peak = max(peak, equity)
        dd = max(dd, peak - equity)
    wins = sum(1 for r in trades if r > 0)
    return {
        "trades": len(trades),
        "win_rate": round(wins / len(trades) * 100, 1),
        "total_r": round(sum(trades), 2),
        "avg_r": round(sum(trades) / len(trades), 3),
        "max_dd": round(dd, 2),
    }


def cache(bars, struct: int, band: float):
    p = {**DEFAULTS, "struct": struct, "band": band}
    s = series(bars, p)
    longs, shorts = signals(s, p)
    return s, longs, shorts


def tune(bars) -> tuple[dict, dict]:
    """Grid search on in-sample data only."""
    memo = {}
    best = None
    for struct in GRID["struct"]:
        for band in GRID["band"]:
            key = (struct, band)
            if key not in memo:
                memo[key] = cache(bars, struct, band)
            s, longs, shorts = memo[key]
            for sl in GRID["sl_atr"]:
                for tp in GRID["tp_r"]:
                    stats = simulate(bars, s, longs, shorts, sl, tp)
                    if stats["trades"] < 20:
                        continue
                    candidate = {"struct": struct, "band": band, "sl_atr": sl, "tp_r": tp}
                    score = stats["total_r"]
                    if best is None or score > best[0]:
                        best = (score, candidate, stats)
    if best is None:
        return {}, {"trades": 0, "note": "no configuration produced 20+ in-sample trades"}
    return best[1], best[2]


def main() -> None:
    print("Learning period: 2010-01-01 → 2020-01-01. Holdout: 2020-01-01 → today.")
    print("The holdout is never used to choose parameters.\n")

    rows = []
    for symbol, name in SYMBOLS.items():
        try:
            is_bars = fetch_daily(symbol, IS_START, IS_END)
            oos_bars = fetch_daily(symbol, IS_END, OOS_END)
        except Exception as err:  # noqa: BLE001 - network is the variable here
            print(f"{symbol}: download failed ({err})")
            continue
        if len(is_bars) < 300 or len(oos_bars) < 300:
            print(f"{symbol}: not enough history ({len(is_bars)} / {len(oos_bars)} bars)")
            continue

        params, is_stats = tune(is_bars)
        if not params:
            print(f"{symbol}: {is_stats['note']}")
            continue

        s, longs, shorts = cache(oos_bars, params["struct"], params["band"])
        oos_stats = simulate(oos_bars, s, longs, shorts, params["sl_atr"], params["tp_r"])

        rows.append({
            "symbol": symbol, "name": name,
            "is_bars": len(is_bars), "oos_bars": len(oos_bars),
            "params": params, "in_sample": is_stats, "out_of_sample": oos_stats,
        })
        print(f"{symbol:7} {name:18} chosen {params}")
        print(f"{'':7} in-sample  {is_stats['trades']:>3} trades  win {is_stats['win_rate']}%  "
              f"total {is_stats['total_r']:+.1f}R  avg {is_stats['avg_r']:+.2f}R")
        print(f"{'':7} holdout    {oos_stats['trades']:>3} trades  win {oos_stats['win_rate']}%  "
              f"total {oos_stats['total_r']:+.1f}R  avg {oos_stats['avg_r']:+.2f}R  "
              f"maxDD {oos_stats['max_dd']}R")
        verdict = ("held up" if (oos_stats["total_r"] or 0) > 0 else "did not hold up")
        print(f"{'':7} verdict: {verdict}\n")

    if not rows:
        print("no results")
        return

    tested = [r for r in rows if r["out_of_sample"]["trades"] >= 10]
    positives = [r for r in tested if (r["out_of_sample"]["total_r"] or 0) > 0]
    total_r = sum(r["out_of_sample"]["total_r"] or 0 for r in rows)
    print("=" * 68)
    print(f"symbols studied: {len(rows)} · with 10+ holdout trades: {len(tested)} · "
          f"positive in holdout: {len(positives)}")
    print(f"combined holdout result: {total_r:+.1f}R")
    print("Read this as evidence about the RULES, not as a promised return.")

    out = Path(__file__).resolve().parent / "research_results.json"
    out.write_text(json.dumps({"generated": datetime.now(timezone.utc).isoformat(),
                               "rows": rows}, indent=2))
    print(f"details written to {out}")


if __name__ == "__main__":
    main()
