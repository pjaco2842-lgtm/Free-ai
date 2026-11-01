"""Fetch OHLCV bars from Yahoo's chart endpoint and write plain CSV.

Every number the desk quotes has to come from a reproducible pull, so this is a
script rather than a one-off command: same symbols, same ranges, same files.

usage: python3 fetch_bars.py [--jobs]
writes trading/data/<SYMBOL>_<interval>.csv   columns: date,open,high,low,close,volume
"""
import csv
import datetime as dt
import json
import os
import sys
import time
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

JOBS = [
    ("ES=F",  "10y", "1d",  "ES_F_1d"),
    ("ES=F",  "730d", "60m", "ES_F_1h"),
    ("ES=F",  "60d", "5m",  "ES_F_5m"),
    ("NQ=F",  "10y", "1d",  "NQ_F_1d"),
    # ^GSPC is deliberately absent: Yahoo's max range returned 169 rows spanning 42
    # years (monthly-thinned), which would silently corrupt any daily measurement.
]


def chart(sym, rng, iv):
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           + urllib.parse.quote(sym) + "?range=" + rng + "&interval=" + iv)
    last = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=40) as r:
                j = json.load(r)
            if not j.get("chart", {}).get("result"):
                raise RuntimeError("no result: " + str(j.get("chart", {}).get("error"))[:120])
            res = j["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            vol = q.get("volume") or [None] * len(res["timestamp"])
            rows = []
            for i, t in enumerate(res["timestamp"]):
                o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
                if None in (o, h, l, c):
                    continue
                stamp = dt.datetime.utcfromtimestamp(t)
                label = (stamp.strftime("%Y-%m-%d") if iv.endswith("d")
                         else stamp.strftime("%Y-%m-%d %H:%M"))
                rows.append([label, o, h, l, c, vol[i] if vol[i] is not None else 0])
            return rows
        except Exception as e:                      # noqa: BLE001 - report, retry, then give up
            last = e
            wait = 3 * (attempt + 1)
            print(f"  retry {attempt + 1}/5 in {wait}s: {e}", file=sys.stderr)
            time.sleep(wait)
    raise SystemExit(f"{sym} {iv}: {last}")


def main():
    os.makedirs(DATA, exist_ok=True)
    for sym, rng, iv, name in JOBS:
        path = os.path.join(DATA, name + ".csv")
        rows = chart(sym, rng, iv)
        if len(rows) < 30:
            print(f"{name}: only {len(rows)} bars, refusing to write")
            continue
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "open", "high", "low", "close", "volume"])
            w.writerows(rows)
        print(f"{name}.csv  {len(rows):>6} bars  {rows[0][0]} -> {rows[-1][0]}  "
              f"last close {rows[-1][4]:.2f}")


if __name__ == "__main__":
    main()
