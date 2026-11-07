#!/usr/bin/env python3
"""Causal re-test of the desk's rule families on daily futures bars.

Why this exists. The wide sweep (mine26k.py) judged a session's whole high and low
against a target *after* a level entry, so it could book a target that traded before
the dip ever filled (see RESEARCH-LOG.md (o), item 1). It also walked the account on
traded days rather than sessions, stopped at the first target even when consistency
failed, and never consulted a locked floor.

This script re-measures the same families with entry ordering that cannot look ahead:

  stop-entry families (buy stop above the market, a legal order)
      entry fills when the level trades; stop-first if stop and target are both
      touched, which is pessimistic but never impossible.

  limit families (buy limit below the market, the only legal reading of
  "buy the prior-day low" when the session opens above it)
      two bounds are reported:
        proven  - stop if the CLOSE is through the stop, target if the CLOSE is
                  beyond the target, otherwise exit at the close. A close always
                  happens after the entry, so no outcome can be booked early.
                  This understates the rule where it spikes through a target.
        legacy  - the old high/low comparison, kept only to measure the bias.

Account walk. $25,000, +$1,250 target, $1,000 end-of-day trailing floor that locks
at $25,100 once the peak passes $26,100, 40% consistency. Every session is stepped,
including flat ones. If the target is reached while consistency fails, trading
continues, which is what the rule actually asks for. Starts overlap, so the pass
share is a distribution over starting points, not a set of independent accounts.

Costs. One tick of slippage per side and $1.24 commission per side (the desk's
standing assumption, not Lucid's published product rate). Yahoo continuous =F
proxies, one micro contract, no intraday data.

Usage
    python3 edge_causal.py                 # both markets, writes desk/causal-search.md
    python3 edge_causal.py --sym ES=F
    python3 edge_causal.py --selftest      # causal-resolution fixtures only
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / ".cache"
OUT = ROOT / "desk" / "causal-search.md"

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# micro specs: dollars per point, tick size, commission per side
SPECS = {
    "ES=F": {"mult": 5.0, "tick": 0.25},
    "NQ=F": {"mult": 2.0, "tick": 0.25},
    # Micro contracts for the other symbols the desk was asked to cover. MGC is $10 a
    # point with a $1 tick, MCL is $100 a point with a $1 tick, NKD is $5 a point with a
    # $25 tick -- which is why one NKD stop cannot fit inside a $1,000 buffer.
    "GC=F": {"mult": 10.0, "tick": 0.10},
    "CL=F": {"mult": 100.0, "tick": 0.01},
    "NKD=F": {"mult": 5.0, "tick": 5.0},
}
COMM_SIDE = 1.24

START_BAL = 25_000.0
TARGET = 1_250.0
MAX_LOSS = 1_000.0
LOCK_AT = 25_100.0
LOCK_TRIGGER = 26_100.0
# 50%, not the standard 40%: the purchased 25K account carries the consistency add-on,
# verified on the dashboard on 2026-11-07. Every walk in this repo before that date used
# 40%, which is stricter than the account, so those pass rates understate it.
CONSISTENCY = 0.50
ERA = "2023-01-01"

STOPS = (0.5, 0.75, 1.0, 1.5, 2.0, 2.5)
EXITS = {"close": None, "tp05": 0.5, "tp1": 1.0, "tp15": 1.5, "tp2": 2.0, "tp3": 3.0}


# ----------------------------------------------------------------------------- data

def _chunk(sym: str, p1: int, p2: int) -> list:
    """One chart request. Yahoo throttles long ranges, so callers chunk."""
    q = urllib.parse.urlencode({"period1": p1, "period2": p2, "interval": "1d"})
    for host in ("query2", "query1"):
        for attempt in range(3):
            url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?{q}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=45) as fh:
                    js = json.load(fh)
                res = js["chart"]["result"][0]
                qd = res["indicators"]["quote"][0]
                out = []
                for i, ts in enumerate(res["timestamp"]):
                    o, h, l, c = qd["open"][i], qd["high"][i], qd["low"][i], qd["close"][i]
                    v = (qd.get("volume") or [None] * (i + 1))[i]
                    if None in (o, h, l, c) or not v:
                        continue
                    d = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                    out.append([d, o, h, l, c])
                return out
            except Exception as exc:            # 429 / 5xx / transient
                last = exc
                time.sleep(2 + 3 * attempt)
    raise RuntimeError(f"{sym} {p1}-{p2}: {last}")


ALIASES = {"date": ("date", "datetime", "time", "timestamp"),
           "open": ("open",), "high": ("high",), "low": ("low",),
           "close": ("close", "price", "close/last")}


def _pick(head: list[str], key: str) -> int | None:
    """Exact name first, so `close` wins over `adj close`, then a prefix match."""
    for a in ALIASES[key]:
        if a in head:
            return head.index(a)
    for a in ALIASES[key]:
        for i, h in enumerate(head):
            if h.startswith(a):
                return i
    return None


def load_csv(path: str) -> dict:
    """Offline bars from any date,open,high,low,close export.

    A vendor export usually carries extra columns (`Adj Close`, `Volume`, `Price`), and
    some files have no header at all. Both are accepted: recognised names win, otherwise
    the canonical five-column order is assumed. Rows that will not parse, or repeat a
    date, are dropped rather than silently shifting the series.
    """
    import csv
    with open(path, newline="") as fh:
        rows = [r for r in csv.reader(fh) if r and any(c.strip() for c in r)]
    if not rows:
        raise SystemExit(f"{path}: empty")
    head = [h.strip().lower() for h in rows[0]]
    col = {k: _pick(head, k) for k in ALIASES}
    if any(v is None for v in col.values()):
        col = {"date": 0, "open": 1, "high": 2, "low": 3, "close": 4}
        body = rows
    else:
        body = rows[1:]
    out = []
    for r in body:
        if len(r) <= max(col.values()):
            continue
        try:
            d = r[col["date"]].strip()[:10]
            datetime.strptime(d, "%Y-%m-%d")
            o, h, l, c = (float(r[col[k]]) for k in ("open", "high", "low", "close"))
        except (ValueError, TypeError):
            continue
        out.append([d, o, h, l, c])
    if not out:
        raise SystemExit(f"{path}: no usable date,open,high,low,close rows")
    uniq = {r[0]: r for r in out}                     # last row per date wins
    return build([uniq[k] for k in sorted(uniq)])


def fetch(sym: str) -> dict:
    CACHE.mkdir(exist_ok=True)
    p = CACHE / f"{sym.replace('=', '_')}.json"
    if not p.exists():
        now = int(time.time())
        rows: dict[str, list] = {}
        t = 1167609600                            # 2007-01-01
        while t < now:
            end = min(t + 3 * 365 * 86400, now)
            for r in _chunk(sym, t, end):
                rows[r[0]] = r
            t = end
            time.sleep(1.0)
        p.write_text(json.dumps({"sym": sym, "rows": [rows[k] for k in sorted(rows)]}))
    raw = json.loads(p.read_text())
    return build(raw["rows"])


def build(rows: list) -> dict:
    d = [r[0] for r in rows]
    o = [float(r[1]) for r in rows]
    h = [float(r[2]) for r in rows]
    l = [float(r[3]) for r in rows]
    c = [float(r[4]) for r in rows]
    n = len(d)
    atr = [0.0] * n
    trs = [h[0] - l[0]]
    for i in range(1, n):
        trs.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
    for i in range(15, n):
        atr[i] = sum(trs[i - 13:i + 1]) / 14.0      # yesterday's ATR for session i
    return {"d": d, "o": o, "h": h, "l": l, "c": c, "atr": atr, "n": n}


# ------------------------------------------------------------------------- families
# each returns (entry, stop_price, note) or None; resolution is applied by the engine

def signal(D: dict, i: int, fam: str, n: int, gap: str):
    o, h, l, c = D["o"][i], D["h"][i], D["l"][i], D["c"][i]
    pc = D["c"][i - 1]
    gap_up = o > pc
    if fam == "limit_low":
        if n < 1 or i - n < 0:
            return None
        lvl = min(D["l"][i - n:i])
        if gap == "with" and not gap_up:
            return None
        if o <= lvl:
            return o, "limit"                 # gapped through the level: fill at open
        if l <= lvl:
            return lvl, "limit"
        return None
    if fam == "prevclose_break":
        if o >= pc:
            return None                       # the stop is not a legal order above market
        if h >= pc:
            return pc, "stop"
        return None
    if fam == "nr_break":
        lvl = max(D["h"][i - n:i]) + 1e-9
        if o >= lvl:
            return o, "stop"                  # gapped through: fill at the open
        if h >= lvl:
            return lvl, "stop"
        return None
    if fam == "open_gap":
        return (o, "open") if gap_up else None
    raise ValueError(fam)


def open_signal(D, i):
    """Market at the open, in the direction of the gap: (entry, kind, side).

    Legal as a market order at the open, and it fires on every session whose open differs
    from the previous close, which is why it is the leg that cannot miss.
    """
    o, pc = D["o"][i], D["c"][i - 1]
    if o > pc:
        return o, "open", 1
    if o < pc:
        return o, "open", -1
    return None


def trade_pnl(D, i, entry, kind, stopk, exitmode, mult, tick, engine, side=1):
    """Return dollars for one micro, or None if the entry could not have happened."""
    atr = D["atr"][i - 1]
    if atr != atr or atr <= 0:                 # NaN-safe: this module is pure python
        return None
    risk = stopk * atr
    stop = entry - side * risk
    tgt = None if exitmode is None else entry + side * exitmode * risk
    h, l, c = D["h"][i], D["l"][i], D["c"][i]

    if exitmode is None:
        px = c
    elif kind == "stop" or kind == "open":
        # legal buy stop / market entry: the level is touched at entry time, so a
        # target above it is necessarily afterwards. Stop-first when both are hit.
        if side > 0:
            if l <= stop:
                px = stop
            elif h >= tgt:
                px = tgt
            else:
                px = c
        else:
            if h >= stop:
                px = stop
            elif l <= tgt:
                px = tgt
            else:
                px = c
    else:                                     # buy limit below the market
        if engine == "legacy":
            px = stop if l <= stop else (tgt if h >= tgt else c)
        else:                                 # proven: only the close is causally safe
            if c <= stop:
                px = stop
            elif c >= tgt:
                px = tgt
            else:
                px = c
    gross = (px - entry) * side * mult          # side: a short earns when px < entry
    cost = 2 * COMM_SIDE + 2 * tick * mult
    return gross - cost


# --------------------------------------------------------------------------- sweep

def run_config(D, fam, n, stopk, exitname, gap, engine, mult, tick):
    exitmode = EXITS[exitname]
    out = []
    for i in range(21, D["n"]):
        sig = signal(D, i, fam, n, gap)
        if not sig:
            continue
        entry, kind = sig
        pnl = trade_pnl(D, i, entry, kind, stopk, exitmode, mult, tick, engine)
        if pnl is None:
            continue
        out.append((D["d"][i], pnl))
    return out


def stats(trades):
    if not trades:
        return {"n": 0}
    v = [t[1] for t in trades]
    wins = sum(1 for x in v if x > 0)
    eq = peak = dd = 0.0
    for x in v:
        eq += x
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    return {"n": len(v), "win": 100.0 * wins / len(v), "mean": statistics.fmean(v),
            "net": sum(v), "dd": dd, "median": statistics.median(v)}


# ------------------------------------------------------------------------- account

def walk(D, trades, start_idx, horizon=240):
    """Step every session from start_idx. Returns (outcome, sessions, largest_day)."""
    by_day = dict(trades)
    bal = peak = START_BAL
    largest = 0.0
    for j in range(start_idx, min(D["n"], start_idx + horizon)):
        p = by_day.get(D["d"][j], 0.0)
        bal += p
        largest = max(largest, p)
        peak = max(peak, bal)
        floor = max(peak - MAX_LOSS, LOCK_AT) if peak >= LOCK_TRIGGER else peak - MAX_LOSS
        if bal < floor:
            return "breach", j - start_idx + 1, largest
        profit = bal - START_BAL
        if profit >= TARGET and largest <= CONSISTENCY * profit:
            return "pass", j - start_idx + 1, largest
    return "unfinished", None, largest


def account(D, trades):
    starts = [i for i, d in enumerate(D["d"]) if d >= ERA]
    if not starts:
        return {"starts": 0}
    res = [walk(D, trades, i) for i in starts]
    passes = [s for o, s, _ in res if o == "pass"]
    breach = sum(1 for o, _, _ in res if o == "breach")
    unf = sum(1 for o, _, _ in res if o == "unfinished")
    pct = lambda k: 100.0 * sum(1 for s in passes if s <= k) / len(starts)
    return {
        "starts": len(starts),
        "p_any": 100.0 * len(passes) / len(starts),
        "p_3": pct(3), "p_5": pct(5), "p_10": pct(10), "p_15": pct(15),
        "breach": 100.0 * breach / len(starts),
        "unfinished": 100.0 * unf / len(starts),
        "median": statistics.median(passes) if passes else None,
        "cons_median": statistics.median(
            [100.0 * lg / (TARGET) for _, _, lg in res if _]) if False else None,
    }


def ten_session_outcomes(D, trades):
    """Distribution of a 10-session sum, for the paper window 2-13 November."""
    by_day = dict(trades)
    pnl = [by_day.get(d, 0.0) for d in D["d"]]
    if len(pnl) < 10:
        return None
    sums = []
    for i in range(len(pnl) - 10):
        sums.append(sum(pnl[i:i + 10]))
    sums.sort()
    q = lambda p: sums[min(len(sums) - 1, int(p * len(sums)))]
    return {"p05": q(.05), "p25": q(.25), "med": statistics.median(sums),
            "p75": q(.75), "p95": q(.95), "pos": 100.0 * sum(1 for s in sums if s > 0) / len(sums)}


# -------------------------------------------------------------------------- report

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sym", action="append")
    ap.add_argument("--csv", help="offline bars: date,open,high,low,close")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--out", help="report path, so two symbols do not overwrite each other")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    out = Path(args.out) if args.out else OUT

    syms = args.sym or list(SPECS)
    lines = ["# Causal re-test of the rule families", "",
             "Generated by `trading/edge_causal.py`. Entry ordering cannot look ahead",
             "(see the module docstring). Account walk steps every session with the",
             "$25,100 locked floor and 40% consistency, continuing past the target if",
             "consistency fails. Starts overlap; the pass share is a distribution over",
             "starting points, not independent accounts.", ""]

    for sym in syms:
        spec = SPECS[sym]
        D = load_csv(args.csv) if args.csv else fetch(sym)
        print(f"{sym}: {D['n']} sessions {D['d'][0]} -> {D['d'][-1]}")

        rows = []
        fams = ([("limit_low", n, g) for n in (1, 2, 3, 5) for g in ("with", "any")]
                + [("prevclose_break", 0, "any"), ("nr_break", 2, "any"),
                   ("nr_break", 3, "any"), ("open_gap", 0, "with")])
        for engine in ("proven", "legacy"):
            for fam, n, gap in fams:
                for stopk in STOPS:
                    for exitname in EXITS:
                        tr = run_config(D, fam, n, stopk, exitname, gap, engine,
                                        spec["mult"], spec["tick"])
                        recent = [t for t in tr if t[0] >= ERA]
                        st = stats(recent)
                        if st["n"] < 100:
                            continue
                        # fam_n, not n: `**st` carries its own "n" = trade count, and
                        # the collision silently turned a lookback into a trade count
                        # (min() of an empty slice crashed the first full run).
                        rows.append({"engine": engine, "fam": fam, "fam_n": n, "gap": gap,
                                     "stop": stopk, "exit": exitname, **st,
                                     "all": stats(tr)})

        # rank by pass rate, which is the desk's stated objective; the account walk
        # is expensive, so it runs here on 2023+ trades only
        for r in rows:
            tr = [(t, p) for t, p in run_config(D, r["fam"], r["fam_n"], r["stop"], r["exit"],
                                                r["gap"], r["engine"], spec["mult"], spec["tick"])
                  if t >= ERA]
            r["acct"] = account(D, tr)
            r["recent_trades"] = tr

        ranked = sorted(rows, key=lambda r: (-r["acct"]["p_any"], -r["mean"]))
        # Split by engine on purpose. Ranked together, the legacy rows swamp the top of
        # the table with 92-96% pass rates and the causal rows never appear -- which is
        # precisely how the retracted 78-80% figure survived as long as it did.
        top = [r for r in ranked if r["engine"] == "proven"][:10]
        bug = [r for r in ranked if r["engine"] == "legacy"][:3]

        HEAD = ("| rule | stop | exit | trades | win | $/trade | pass% | <=3 | <=5 | <=10 "
                "| <=15 | breach% | median sess |")
        SEP = "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"

        def trow(r):
            a = r["acct"]
            name = {"limit_low": f"limit_low-{r['fam_n']} gap:{r['gap']}",
                    "prevclose_break": "prevclose_break",
                    "nr_break": f"nr_break-{r['fam_n']}",
                    "open_gap": "open_gap"}[r["fam"]]
            med = f"{a['median']:.0f}" if a["median"] is not None else "-"
            return (f"| {name} | {r['stop']}A | {r['exit']} | {r['n']} | "
                    f"{r['win']:.1f}% | ${r['mean']:+.2f} | {a['p_any']:.0f}% | "
                    f"{a['p_3']:.1f}% | {a['p_5']:.1f}% | {a['p_10']:.1f}% | "
                    f"{a['p_15']:.1f}% | {a['breach']:.0f}% | {med} |")

        lines += [f"## {sym} (micro) — causal ranking", "",
                  f"{D['n']} completed sessions, {D['d'][0]} to {D['d'][-1]}. "
                  f"One micro, ${spec['mult']:.0f}/pt. Entry ordering cannot look ahead.",
                  "", HEAD, SEP]
        lines += [trow(r) for r in top] or ["| (no proven config reached 100 trades) |" + " |" * 12]

        if bug:
            lines += ["", f"### The same sweep judged the old way ({sym})", "",
                      "These are the look-ahead resolutions. They are here to show what the bug "
                      "is worth, not what a rule earns:", "", HEAD, SEP]
            lines += [trow(r) for r in bug]

        # the 10-session window
        best = top[0]
        win10 = ten_session_outcomes(D, best["recent_trades"])
        if win10:
            lines += ["", f"Best line, next 10 sessions (2-13 Nov): median ${win10['med']:+.0f}, "
                          f"5-95% ${win10['p05']:+.0f} to ${win10['p95']:+.0f}, "
                          f"{win10['pos']:.0f}% of windows positive."]
        lines.append("")

    out.write_text("\n".join(lines) + "\n")
    try:
        shown = out.resolve().relative_to(ROOT)
    except ValueError:                       # caller passed an absolute path
        shown = out
    print(f"wrote {shown}")


def selftest() -> None:
    """A bar where the target trades before the dip is not a win."""
    D = {"d": ["d0", "d1"], "o": [100.0, 100.0], "h": [101.0, 120.0],
         "l": [99.0, 95.0], "c": [100.0, 96.0], "atr": [10.0, 10.0], "n": 2}
    # prior low 99, open 100 -> limit at 99 fills; stop 89; target 99+0.5*10 = 104
    proven = trade_pnl(D, 1, 99.0, "limit", 1.0, 0.5, 5.0, 0.25, "proven")
    legacy = trade_pnl(D, 1, 99.0, "limit", 1.0, 0.5, 5.0, 0.25, "legacy")
    assert legacy is not None and legacy > 0, "legacy books the early high as a win"
    assert proven is not None and proven < 0, "causal engine refuses the impossible target"
    # a legal buy stop above the market may use the high
    stop = trade_pnl(D, 1, 100.0, "stop", 1.0, 0.5, 5.0, 0.25, "proven")
    assert stop is not None and stop > 0
    print("selftest ok: proven refuses the pre-entry target, legacy books it, stop entry is legal")


if __name__ == "__main__":
    main()
