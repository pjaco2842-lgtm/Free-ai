#!/usr/bin/env python3
"""
Scan markets and test the rules from trading/ai-signal-bot.pine — for free.

Why this exists
---------------
TradingView shows you a chart; it cannot hand your agent the numbers behind it.
This script pulls free candles from public APIs, computes the same indicators
the Pine script draws, and answers two questions:

    python3 trading/scanner.py scan --symbol NQ=F          # what is true now
    python3 trading/scanner.py backtest --symbol NQ=F      # does it actually work

The second command is the important one. A signal stack is worth nothing until
you have measured it on history you did not cherry-pick.

Data sources (no keys, no accounts):
    yahoo      NQ=F, ES=F, AAPL ...   unofficial, ~5 days of 5m history
    coinbase   BTC-USD, ETH-USD ...   300 candles per request
    kraken     XBTUSD ...             720 candles per request

Only stdlib. Nothing to install.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

UA = {"User-Agent": "Mozilla/5.0 (compatible; local-scanner/1.0)"}


# ------------------------------------------------------------------ data
@dataclass
class Bar:
    t: int
    o: float
    h: float
    l: float
    c: float
    v: float


def _get(url: str, tries: int = 3) -> dict | list:
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as res:
                return json.loads(res.read().decode())
        except Exception as err:  # noqa: BLE001 - network varies wildly
            last = err
            time.sleep(1.5 * (attempt + 1))
    raise SystemExit(f"fetch failed: {url}\n  {last}")


def fetch_yahoo(symbol: str, interval: str, span: str) -> list[Bar]:
    query = urllib.parse.urlencode({"interval": interval, "range": span})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?{query}"
    data = _get(url)
    result = data["chart"]["result"][0]
    stamps = result["timestamp"]
    q = result["indicators"]["quote"][0]
    bars = []
    for i, t in enumerate(stamps):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        bars.append(Bar(t, float(o), float(h), float(l), float(c), float(q["volume"][i] or 0)))
    return bars


def fetch_coinbase(product: str, granularity: int) -> list[Bar]:
    url = (f"https://api.exchange.coinbase.com/products/{product}/candles"
           f"?granularity={granularity}")
    rows = _get(url)
    rows = sorted(rows, key=lambda r: r[0])
    return [Bar(int(r[0]), float(r[3]), float(r[2]), float(r[1]), float(r[4]), float(r[5]))
            for r in rows]


def fetch_kraken(pair: str, interval: int) -> list[Bar]:
    url = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={interval}"
    data = _get(url)
    if data.get("error"):
        raise SystemExit(f"kraken: {data['error']}")
    key = next(k for k in data["result"] if k != "last")
    rows = data["result"][key]
    return [Bar(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[6]))
            for r in rows]


def load(source: str, symbol: str, tf: str, bars: int) -> list[Bar]:
    if source == "coinbase":
        gran = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "6h": 21600, "1d": 86400}[tf]
        return fetch_coinbase(symbol, gran)[-bars:]
    if source == "kraken":
        gran = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}[tf]
        data = fetch_kraken(symbol, gran)
        return data[-(bars + 1):-1]  # kraken repeats the forming candle last
    interval = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "60m", "1d": "1d"}[tf]
    span = {"1m": "2d", "5m": "5d", "15m": "1mo", "1h": "3mo", "1d": "2y"}[tf]
    return fetch_yahoo(symbol, interval, span)[-bars:]


# ------------------------------------------------------------ indicators
def sma(values: list[float], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    total = 0.0
    for i, v in enumerate(values):
        total += v
        if i >= n:
            total -= values[i - n]
        if i >= n - 1:
            out[i] = total / n
    return out


def wma(values: list[float], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    weight = n * (n + 1) / 2
    for i in range(n - 1, len(values)):
        acc = 0.0
        for k in range(n):
            acc += values[i - k] * (n - k)
        out[i] = acc / weight
    return out


def hma(values: list[float], n: int) -> list[float | None]:
    half, root = max(1, n // 2), max(1, int(math.sqrt(n)))
    w_half, w_full = wma(values, half), wma(values, n)
    diff = [None if (a is None or b is None) else 2 * a - b for a, b in zip(w_half, w_full)]
    out: list[float | None] = [None] * len(values)
    for i in range(root - 1, len(values)):
        window = diff[i - root + 1:i + 1]
        if any(v is None for v in window):
            continue
        weight = root * (root + 1) / 2
        out[i] = sum(v * (root - k) for k, v in enumerate(reversed(window))) / weight
    return out


def rsi(closes: list[float], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(closes)
    if len(closes) <= n:
        return out
    gains = losses = 0.0
    for i in range(1, n + 1):
        change = closes[i] - closes[i - 1]
        gains += max(change, 0.0)
        losses += max(-change, 0.0)
    avg_g, avg_l = gains / n, losses / n
    out[n] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
    for i in range(n + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        avg_g = (avg_g * (n - 1) + max(change, 0.0)) / n
        avg_l = (avg_l * (n - 1) + max(-change, 0.0)) / n
        out[i] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
    return out


def stoch(highs, lows, closes, k_len: int, smooth: int, d_len: int):
    raw: list[float | None] = [None] * len(closes)
    for i in range(k_len - 1, len(closes)):
        hh = max(highs[i - k_len + 1:i + 1])
        ll = min(lows[i - k_len + 1:i + 1])
        raw[i] = 50.0 if hh == ll else (closes[i] - ll) / (hh - ll) * 100
    filled = [v for v in raw if v is not None]
    k_smooth = sma(filled, smooth)
    k = [None] * len(raw)
    j = 0
    for i, v in enumerate(raw):
        if v is not None:
            k[i] = k_smooth[j]
            j += 1
    filled_k = [v for v in k if v is not None]
    d_smooth = sma(filled_k, d_len)
    d = [None] * len(k)
    j = 0
    for i, v in enumerate(k):
        if v is not None:
            d[i] = d_smooth[j]
            j += 1
    return k, d


def atr(highs, lows, closes, n: int) -> list[float | None]:
    trs = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    out: list[float | None] = [None] * len(closes)
    if len(trs) < n:
        return out
    prev = sum(trs[:n]) / n
    out[n - 1] = prev
    for i in range(n, len(trs)):
        prev = (prev * (n - 1) + trs[i]) / n
        out[i] = prev
    return out


def rolling_extreme(values: list[float], n: int, highest: bool):
    out: list[float | None] = [None] * len(values)
    for i in range(n - 1, len(values)):
        window = values[i - n + 1:i + 1]
        out[i] = max(window) if highest else min(window)
    return out


# --------------------------------------------------------------- strategy
DEFAULTS = dict(struct=50, band=5.0, rsi_len=14, k=9, smooth=3, d=3,
                hull_fast=9, hull_slow=16, atr_len=14, sl_atr=1.0, tp_r=2.0)


def series(bars: list[Bar], p: dict) -> dict:
    closes = [b.c for b in bars]
    highs = [b.h for b in bars]
    lows = [b.l for b in bars]
    k, d = stoch(highs, lows, closes, p["k"], p["smooth"], p["d"])
    hf, hs = hma(closes, p["hull_fast"]), hma(closes, p["hull_slow"])
    a = atr(highs, lows, closes, p["atr_len"])
    osc = [None if (x is None or y is None or not z) else (x - y) / z * 100
           for x, y, z in zip(hf, hs, a)]
    hi = rolling_extreme(highs, p["struct"], True)
    lo = rolling_extreme(lows, p["struct"], False)
    pos = [None if (h is None or l is None or h == l) else (c - l) / (h - l) * 100
           for c, h, l in zip(closes, hi, lo)]
    return dict(close=closes, high=highs, low=lows, open=[b.o for b in bars],
                rsi=rsi(closes, p["rsi_len"]), k=k, d=d, osc=osc, atr=a, pos=pos)


def signals(s: dict, p: dict, window: int = 12) -> tuple[list[bool], list[bool]]:
    """Setup + trigger.

    Requiring every condition to happen on the SAME bar fired almost never
    (0-2 trades across hundreds of bars). So: the zone/RSI pair opens a setup,
    the setup stays valid for `window` bars, and a momentum cross inside that
    window is the trigger. Still deterministic, still non-repainting.
    """
    n = len(s["close"])
    longs, shorts = [False] * n, [False] * n
    band = p["band"]
    last_long = last_short = -10**9
    for i in range(1, n):
        need = (s["osc"][i], s["osc"][i - 1], s["rsi"][i],
                s["k"][i], s["d"][i], s["k"][i - 1], s["d"][i - 1], s["pos"][i])
        if any(v is None for v in need):
            continue
        osc, osc_prev, r, kk, dd, kp, dp, pos = need

        if pos < 50 - band and r > 50:
            last_long = i
        if pos > 50 + band and r < 50:
            last_short = i

        osc_up, osc_dn = osc > 0 >= osc_prev, osc < 0 <= osc_prev
        sto_up, sto_dn = kk > dd and kp <= dp, kk < dd and kp >= dp

        if (osc_up or sto_up) and pos < 50 and r > 50 and i - last_long <= window:
            longs[i] = True
        if (osc_dn or sto_dn) and pos > 50 and r < 50 and i - last_short <= window:
            shorts[i] = True
    return longs, shorts


# --------------------------------------------------------------- commands
def _params(args) -> dict:
    return {**DEFAULTS, "struct": args.struct, "band": args.band,
            "sl_atr": args.sl_atr, "tp_r": args.tp_r}


def cmd_scan(args) -> None:
    p = _params(args)
    bars = load(args.source, args.symbol, args.tf, args.bars)
    if len(bars) < 60:
        raise SystemExit(f"not enough history for {args.symbol} ({len(bars)} bars)")
    s = series(bars, p)
    longs, shorts = signals(s, p)
    i = len(bars) - 1
    price = bars[i].c

    recent = None
    for back in range(1, 60):
        j = i - back
        if j >= 0 and (longs[j] or shorts[j]):
            recent = {"side": "long" if longs[j] else "short",
                      "bars_ago": back, "at": bars[j].t, "price": bars[j].c}
            break

    risk = (s["atr"][i] or 0) * p["sl_atr"]
    out = {
        "symbol": args.symbol, "source": args.source, "tf": args.tf,
        "bars": len(bars), "price": price, "time": bars[i].t,
        "zone": "n/a" if s["pos"][i] is None else
                ("discount" if s["pos"][i] < 50 - p["band"] else
                 "premium" if s["pos"][i] > 50 + p["band"] else "equilibrium"),
        "pos_pct": None if s["pos"][i] is None else round(s["pos"][i], 1),
        "rsi": None if s["rsi"][i] is None else round(s["rsi"][i], 1),
        "stoch_k": None if s["k"][i] is None else round(s["k"][i], 1),
        "stoch_d": None if s["d"][i] is None else round(s["d"][i], 1),
        "butterfly": None if s["osc"][i] is None else round(s["osc"][i], 2),
        "atr": None if s["atr"][i] is None else round(s["atr"][i], 2),
        "signal_now": "long" if longs[i] else "short" if shorts[i] else "none",
        "last_signal": recent,
        "if_long_then": {"entry": price, "stop": round(price - risk, 2),
                         "target": round(price + risk * p["tp_r"], 2)},
        "if_short_then": {"entry": price, "stop": round(price + risk, 2),
                          "target": round(price - risk * p["tp_r"], 2)},
    }
    print(json.dumps(out, indent=2))


def cmd_backtest(args) -> None:
    p = _params(args)
    bars = load(args.source, args.symbol, args.tf, args.bars)
    if len(bars) < 100:
        raise SystemExit(f"not enough history for {args.symbol} ({len(bars)} bars)")
    s = series(bars, p)
    longs, shorts = signals(s, p)

    trades = []
    i = 2
    while i < len(bars) - 1:
        if longs[i] or shorts[i]:
            side = "long" if longs[i] else "short"
            entry = bars[i + 1].o
            risk = (s["atr"][i] or 0) * p["sl_atr"]
            if risk <= 0:
                i += 1
                continue
            stop = entry - risk if side == "long" else entry + risk
            target = entry + risk * p["tp_r"] if side == "long" else entry - risk * p["tp_r"]
            result = None
            j = i + 1
            while j < len(bars) and j <= i + args.max_hold:
                hit_stop = bars[j].l <= stop if side == "long" else bars[j].h >= stop
                hit_target = bars[j].h >= target if side == "long" else bars[j].l <= target
                if hit_stop:            # stop first: the conservative assumption
                    result = -1.0
                elif hit_target:
                    result = p["tp_r"]
                if result is not None:
                    break
                j += 1
            if result is None:
                result = ((bars[min(j, len(bars) - 1)].c - entry) / risk) if side == "long" \
                    else ((entry - bars[min(j, len(bars) - 1)].c) / risk)
            trades.append({"side": side, "t": bars[i].t, "entry": entry, "r": round(result, 2),
                           "bars_held": j - i})
            i = j + 1
        else:
            i += 1

    if not trades:
        print(json.dumps({"symbol": args.symbol, "tf": args.tf, "trades": 0,
                          "note": "no signals fired on this history"}, indent=2))
        return

    rs = [t["r"] for t in trades]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    equity, peak, max_dd = 0.0, 0.0, 0.0
    for r in rs:
        equity += r
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    summary = {
        "symbol": args.symbol, "source": args.source, "tf": args.tf,
        "bars": len(bars), "from": bars[0].t, "to": bars[-1].t,
        "trades": len(rs),
        "win_rate_pct": round(len(wins) / len(rs) * 100, 1),
        "avg_R": round(sum(rs) / len(rs), 3),
        "total_R": round(sum(rs), 2),
        "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses else None,
        "best_R": max(rs), "worst_R": min(rs),
        "max_drawdown_R": round(max_dd, 2),
        "avg_bars_held": round(sum(t["bars_held"] for t in trades) / len(trades), 1),
        "long_trades": sum(1 for t in trades if t["side"] == "long"),
        "short_trades": sum(1 for t in trades if t["side"] == "short"),
    }
    print(json.dumps(summary, indent=2))
    if len(rs) < 20:
        print("\nNOTE: fewer than 20 trades. That is noise, not evidence.", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description="Scan / backtest the AI Signal Bot rules.")
    ap.add_argument("command", choices=["scan", "backtest"])
    ap.add_argument("--symbol", default="NQ=F")
    ap.add_argument("--source", default="yahoo", choices=["yahoo", "coinbase", "kraken"])
    ap.add_argument("--tf", default="5m", choices=["1m", "5m", "15m", "1h", "4h", "6h", "1d"])
    ap.add_argument("--bars", type=int, default=400)
    ap.add_argument("--struct", type=int, default=DEFAULTS["struct"])
    ap.add_argument("--band", type=float, default=DEFAULTS["band"])
    ap.add_argument("--sl-atr", type=float, default=DEFAULTS["sl_atr"])
    ap.add_argument("--tp-r", type=float, default=DEFAULTS["tp_r"])
    ap.add_argument("--max-hold", type=int, default=60)
    args = ap.parse_args()
    cmd_scan(args) if args.command == "scan" else cmd_backtest(args)


if __name__ == "__main__":
    main()
