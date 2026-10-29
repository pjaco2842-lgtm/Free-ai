#!/usr/bin/env python3
"""
The desk — seven agents argue about every trade, then a chair decides.

Why a committee instead of one rule
-----------------------------------
A single rule can only say "buy". It cannot tell you it is about to be wrong.
This file splits the job the way a real desk does, and the split is deliberate:
the agent that suggests a trade is never the agent that approves it.

    trend       context: is the bigger trend with us or against us
    structure   context: is this a compression/expansion setup
    momentum    context: is short-horizon push on our side
    volatility  sizing: does one contract's stop fit the risk budget
    edge        is the reward worth the cost, net of commission and slippage
    odds        what are the chances — an interval, not a promise
    skeptic     the agent whose only job is to say no, and can veto

The chair trades only when at least two context agents agree, the skeptic does
not object, expectancy clears a cost hurdle, and the win rate's lower bound is
better than a coin flip. Every agent's argument is written down, so a bad
decision can be traced to whichever agent argued for it.

What makes this different from trading/basket.py
------------------------------------------------
basket.py decides from daily bars and assumes the stop hit first when a bar
touches both stop and target. That is pessimistic on purpose, but it is still a
guess. Futures trade twenty-three hours, so here every trade is resolved against
fifteen-minute bars: the desk can see whether the stop or the target actually
traded first, and at what time of night. Where intraday history does not reach
back, it falls back to the daily assumption and labels the row `daily`, so the
two are never mixed in one statistic.

Two ledgers, on purpose
-----------------------
`trading/desk/ledger.jsonl` is the forward record: it starts the day the desk
first ran and can never be back-filled. That is the only file that proves
anything. `trading/desk/shadow.jsonl` is a replay of recent sessions so there is
something to look at today — useful, honest, and explicitly *not* forward.

    python3 trading/desk.py --cycle      # forward pass: decide, resolve, log
    python3 trading/desk.py --backfill 60 # shadow replay of the last 60 days
    python3 trading/desk.py --pending    # resting orders for the next session
    python3 trading/desk.py --report     # the record
    python3 trading/desk.py --status     # open risk right now

Nothing here places an order. No broker, no key, no account number. "Fill"
always means a simulated fill at a price the market actually printed.
"""

from __future__ import annotations

import argparse
import bisect
import json
import os
import math
import statistics
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from basket import CONFIGS, HAIRCUT, contracts_for, pending_orders  # noqa: E402
from edge import CONTRACTS  # noqa: E402
from lab import COMMS, COMMISSION, RULES, atr_series, ema, fetch_daily  # noqa: E402
from scanner import Bar, rsi  # noqa: E402
from account import ACCOUNT  # noqa: E402  (the firm's rulebook)
from bots import DAILY_STOP, EQUITY, MAX_OPEN, RISK, live as bots_live  # noqa: E402

HERE = Path(__file__).resolve().parent
DESK = HERE / "desk"
STATE = DESK / "state.json"
LEDGER = DESK / "ledger.jsonl"
DECISIONS = DESK / "decisions.jsonl"
SHADOW = DESK / "shadow.jsonl"
SHADOW_DECISIONS = DESK / "shadow_decisions.jsonl"
REPORT = DESK / "report.md"
SINCE = DESK / "since.txt"
BOARD = DESK / "board.json"

# EQUITY, RISK, DAILY_STOP and MAX_OPEN are read from trading/desk/account.json
# through bots.py, so the forward pass and the board can never disagree about
# what the account allows.
MIN_EDGE_R = 0.10        # below this net expectancy a signal is not worth the cost
UA = {"User-Agent": "Mozilla/5.0 (compatible; free-ai-desk/1.0)"}


# --------------------------------------------------------------- utilities
def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def day_of(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def clock(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%MZ")


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


def append_jsonl(path: Path, rows: list[dict]) -> int:
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return len(rows)


def wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% interval for a win rate. Ten trades can look great and prove nothing."""
    if n == 0:
        return 0.0, 1.0
    p = wins / n
    d = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, mid - half), min(1.0, mid + half)


# ------------------------------------------------------------------- data
def fetch_intraday(symbol: str) -> list[Bar]:
    """Fifteen-minute bars for the last sixty days, hourly as a fallback."""
    for interval, span in (("15m", "60d"), ("1h", "1mo")):
        q = urllib.parse.urlencode({"interval": interval, "range": span})
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?{q}"
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as res:
                data = json.loads(res.read().decode())
            result = data["chart"]["result"][0]
            stamps, quote = result["timestamp"], result["indicators"]["quote"][0]
        except Exception:  # noqa: BLE001 - a missing feed must not kill the cycle
            continue
        bars = []
        for i, t in enumerate(stamps):
            o, h, l, c = quote["open"][i], quote["high"][i], quote["low"][i], quote["close"][i]
            if None in (o, h, l, c):
                continue
            bars.append(Bar(int(t), float(o), float(h), float(l), float(c),
                            float(quote["volume"][i] or 0)))
        if bars:
            return bars
    return []


class Intraday:
    """Fifteen-minute bars indexed by session, so a daily trade can be replayed.

    A session is [daily_bar.t, next_daily_bar.t). Using the daily timestamps as
    boundaries avoids guessing at any exchange's 6pm-to-5pm convention.
    """

    def __init__(self, bars: list[Bar], daily: list[Bar]):
        self.bars = bars
        self.stamps = [b.t for b in bars]
        self.daily = daily

    def session(self, i: int) -> list[Bar]:
        if not self.bars or i >= len(self.daily):
            return []
        start = self.daily[i].t
        end = self.daily[i + 1].t if i + 1 < len(self.daily) else math.inf
        lo = bisect.bisect_left(self.stamps, start)
        hi = bisect.bisect_left(self.stamps, end)
        return self.bars[lo:hi]

    def sessions(self, i: int, count: int) -> list[Bar]:
        out: list[Bar] = []
        for k in range(i, min(i + count, len(self.daily))):
            out.extend(self.session(k))
        return out


# --------------------------------------------------------------- the agents
def agent_trend(symbol, cfg, bars, atr, emas, side, ctx) -> dict:
    """Is the larger trend on our side, and still leaning that way?"""
    fast, slow = emas.get(50), emas.get(200)
    if not fast or not slow or fast[-1] is None or slow[-1] is None:
        return {"agent": "trend", "vote": "pass", "score": 0.0,
                "note": "not enough history for a trend read"}
    above = fast[-1] > slow[-1]
    want = side == "long"
    with_trend = above == want
    slope = 0.0
    if len(fast) > 11 and fast[-11] is not None:
        slope = (fast[-1] - fast[-11]) / max(abs(slow[-1]), 1e-9)
    same_way = (slope > 0) == want
    score = (0.6 if with_trend else -0.6) + (0.4 if same_way else -0.4)
    note = (f"EMA50 {'above' if above else 'below'} EMA200 "
            f"({fast[-1]:,.1f} vs {slow[-1]:,.1f}), 10-bar slope {100 * slope:+.2f}%")
    return {"agent": "trend", "vote": "take" if score > 0 else "against",
            "score": round(score, 2), "note": note}


def agent_structure(symbol, cfg, bars, atr, emas, side, ctx) -> dict:
    """Is there compression about to expand, and does the breakout agree?"""
    if len(bars) < 12:
        return {"agent": "structure", "vote": "pass", "score": 0.0, "note": "short history"}
    last, prev = bars[-1], bars[-2]
    inside = prev.h <= bars[-3].h and prev.l >= bars[-3].l
    ranges = [b.h - b.l for b in bars[-8:-1]]
    nr = (last.h - last.l) <= min(ranges) if ranges else False
    pos = (last.c - last.l) / max(last.h - last.l, 1e-9)
    agree = (side == "long" and pos >= 0.5) or (side == "short" and pos <= 0.5)
    patterns = []
    if inside:
        patterns.append("inside day")
    if nr:
        patterns.append("narrowest range of 7")
    if cfg["rule"] in ("inside_day", "nr_break") and not patterns:
        return {"agent": "structure", "vote": "against", "score": -0.5,
                "note": "this rule needs an inside or narrow day; neither is present"}
    score = 0.5 * (1 if agree else -1) + (0.5 if patterns else 0.0)
    note = (f"{', '.join(patterns) or 'no compression pattern'}; close at "
            f"{100 * pos:.0f}% of the day's range")
    return {"agent": "structure", "vote": "take" if score > 0 else "against",
            "score": round(score, 2), "note": note}


def agent_momentum(symbol, cfg, bars, atr, emas, side, ctx) -> dict:
    """Short-horizon push, and whether it is already exhausted."""
    vals = [v for v in rsi([b.c for b in bars], 14) if v is not None]
    if not vals:
        return {"agent": "momentum", "vote": "pass", "score": 0.0, "note": "no RSI yet"}
    r = vals[-1]
    want = side == "long"
    stretched = r >= 70 if want else r <= 30
    favours = r > 50 if want else r < 50
    score = (0.5 if favours else -0.5) - (0.5 if stretched else 0.0)
    note = f"RSI14 {r:.0f}" + (" — already stretched" if stretched else "")
    return {"agent": "momentum", "vote": "take" if score > 0 else "against",
            "score": round(score, 2), "note": note}


def agent_volatility(symbol, cfg, bars, atr, emas, side, ctx) -> dict:
    """Sizing, not direction: does one contract's stop fit the risk budget?"""
    live = [a for a in atr[-120:] if a]
    if len(live) < 20:
        return {"agent": "volatility", "vote": "pass", "score": 0.0,
                "note": "no volatility history", "size_mult": 1.0, "percentile": 50}
    a = live[-1]
    pct = round(100 * sum(1 for v in live if v <= a) / len(live))
    stop_pts = cfg["stop"] * a
    meta = CONTRACTS[symbol]
    stop_usd = stop_pts * meta["pv"]
    cost = 2 * (COMMS.get(symbol, COMMISSION) + meta["tick"] * meta["pv"])
    fits = contracts_for(stop_pts, meta["pv"], cost)
    verdict = "take" if fits > 0 else "against"
    note = (f"ATR {a:,.2f} at the {pct}th percentile; one stop is ${stop_usd:,.0f} "
            f"({100 * stop_usd / EQUITY:.1f}% of equity, budget ${EQUITY * RISK:,.0f}) -> "
            f"{'fits' if fits else 'does not fit'}")
    return {"agent": "volatility", "vote": verdict,
            "score": round(0.3 if fits else -1.0, 2), "note": note,
            "size_mult": 0.5 if pct >= 90 else 1.0,
            "stop_usd": round(stop_usd, 2), "percentile": pct}


def agent_edge(symbol, cfg, bars, atr, emas, side, ctx) -> dict:
    """Is the reward worth the cost? Expectancy net of commission and slippage."""
    hist = ctx["trades"]
    if len(hist) < 8:
        return {"agent": "edge", "vote": "pass", "score": 0.0,
                "note": f"only {len(hist)} prior trades — not enough to price this",
                "expectancy_r": None}
    nets = [t["net"] for t in hist]
    mean = statistics.mean(nets)
    gross = statistics.mean(t["r"] for t in hist)
    drag = gross - mean
    passed = mean >= MIN_EDGE_R
    note = (f"{len(hist)} trades, expectancy {mean:+.2f}R net of {drag:.2f}R of cost "
            f"(gross {gross:+.2f}R); hurdle {MIN_EDGE_R:+.2f}R")
    return {"agent": "edge", "vote": "take" if passed else "against",
            "score": round(mean, 2), "note": note, "expectancy_r": round(mean, 3)}


def agent_odds(symbol, cfg, bars, atr, emas, side, ctx) -> dict:
    """What are the chances?"""
    hist = ctx["trades"]
    if len(hist) < 8:
        return {"agent": "odds", "vote": "pass", "score": 0.0,
                "note": "not enough trades for odds", "win_rate": None}
    n = len(hist)
    wins = sum(1 for t in hist if t["net"] > 0)
    lo, hi = wilson(wins, n)
    beat_coin = lo >= 0.35
    note = (f"{wins}/{n} = {100 * wins / n:.0f}% win, 95% interval "
            f"{100 * lo:.0f}–{100 * hi:.0f}%; "
            f"{'better than a coin flip' if beat_coin else 'not distinguishable from a coin flip'}")
    return {"agent": "odds", "vote": "take" if beat_coin else "against",
            "score": round(wins / n - 0.5, 2), "note": note,
            "win_rate": round(100 * wins / n, 1),
            "interval": [round(100 * lo, 1), round(100 * hi, 1)]}


def agent_skeptic(symbol, cfg, bars, atr, emas, side, ctx) -> dict:
    """The only job is to say no. A veto stops the trade."""
    reasons: list[str] = []
    state = ctx["state"]
    if state.get("day_pnl", 0.0) <= -DAILY_STOP:
        reasons.append(f"daily stop already hit (${state['day_pnl']:,.0f})")
    if ctx["open_risk"] >= MAX_OPEN:
        reasons.append(f"{ctx['open_risk']} positions already open")
    pct = ctx["volatility"].get("percentile", 0)
    if pct >= 97:
        reasons.append(f"volatility at the {pct}th percentile — a stop this size is a guess")
    for other in ctx["open_positions"]:
        if other["side"] == side and other["symbol"] != symbol:
            corr = ctx["corr"].get(tuple(sorted((symbol, other["symbol"]))))
            if corr is not None and corr >= 0.7:
                reasons.append(f"already {side} {other['symbol']} at {corr:.2f} correlation "
                               "— that is the same bet twice")
    if cfg["rule"] in ("fade_trend_day", "continue_trend_day"):
        thr = cfg["params"].get("trend", 1.5)
        gap = (bars[-1].h - bars[-1].l) / max(atr[-1] or 1e-9, 1e-9)
        if gap < thr:
            reasons.append(f"the range rule needs a {thr}x ATR day, the last was {gap:.2f}x")
    hist = ctx["trades"]
    if len(hist) >= 20 and statistics.mean(t["net"] for t in hist) < 0:
        reasons.append(f"its own {len(hist)}-trade history is negative")
    return {"agent": "skeptic", "vote": "veto" if reasons else "clear",
            "score": -1.0 if reasons else 0.0,
            "note": "; ".join(reasons) if reasons else "no objection found",
            "veto": bool(reasons)}


# ---------------------------------------------------------------- the chair
def chair(votes: list[dict], ctx: dict) -> dict:
    """Aggregate. The chair may only say no; it can never invent a trade."""
    by = {v["agent"]: v for v in votes}
    directors = [by[a] for a in ("trend", "structure", "momentum") if a in by]
    support = sum(1 for d in directors if d["vote"] == "take")
    oppose = sum(1 for d in directors if d["vote"] == "against")
    edge = by.get("edge", {})
    odds = by.get("odds", {})
    vol = by.get("volatility", {})
    blockers = []
    if by.get("skeptic", {}).get("veto"):
        blockers.append("skeptic veto")
    if support < 2:
        blockers.append(f"only {support}/3 context agents agree")
    if oppose > 1:
        blockers.append(f"{oppose}/3 context agents disagree")
    if edge.get("expectancy_r") is None or edge.get("expectancy_r", 0) < MIN_EDGE_R:
        blockers.append("expectancy below the cost hurdle")
    if odds.get("win_rate") is None or odds.get("vote") != "take":
        blockers.append("win rate not better than a coin flip")
    if vol.get("vote") == "against":
        blockers.append("one contract's stop does not fit the risk budget")
    tradable = not blockers
    return {"decision": "TRADE" if tradable else "PASS",
            "support": support, "oppose": oppose,
            "size_mult": vol.get("size_mult", 1.0) if tradable else 0.0,
            "blockers": blockers,
            "reason": "all five checks passed" if tradable else "; ".join(blockers)}


# ----------------------------------------------------- intraday fill resolver
def bracket_detailed(symbol, cfg, bars, atr, intraday, comm, pv, tick, entry_mode) -> list[dict]:
    """Every signal as a trade, with fill order taken from the finest bars we have.

    The daily backtest has to assume the stop hit first when one bar touches
    both. Where fifteen-minute bars exist this walks them in order and reports
    what actually traded first — including at 2am, which is the point of a
    twenty-three hour market.
    """
    fn, _grid, _rcfg = RULES[cfg["rule"]]
    emas = {k: ema([b.c for b in bars], k) for k in (20, 50, 200)}
    sig = fn(bars, atr, emas, cfg["params"])
    hold = cfg["hold"]
    same_open = entry_mode == "same_open"
    cost = 2 * (comm + tick * pv)
    out: list[dict] = []
    busy = -1

    for i, side in sig:
        j = i if same_open else i + 1
        if j >= len(bars) or j <= busy:
            continue
        a = atr[i - 1] if i >= 1 else None
        if not a:
            continue
        risk, reward = cfg["stop"] * a, cfg["target"] * a
        if risk <= 0 or reward <= 0:
            continue

        session = intraday.sessions(j, hold) if intraday else []
        if session:
            px = session[0].o
            stop = px - risk if side == "long" else px + risk
            tgt = px + reward if side == "long" else px - reward
            exit_px, reason, when = None, "time", session[-1].t
            for b in session:
                if side == "long":
                    if b.l <= stop:
                        exit_px, reason, when = stop, "stop", b.t
                        break
                    if b.h >= tgt:
                        exit_px, reason, when = tgt, "target", b.t
                        break
                else:
                    if b.h >= stop:
                        exit_px, reason, when = stop, "stop", b.t
                        break
                    if b.l <= tgt:
                        exit_px, reason, when = tgt, "target", b.t
                        break
            if exit_px is None:
                exit_px = session[-1].c
            precision = "15m"
        else:
            px = bars[j].o
            stop = px - risk if side == "long" else px + risk
            tgt = px + reward if side == "long" else px - reward
            exit_px, reason, when = bars[j].c, "time", bars[j].t
            for k in range(j, min(j + hold, len(bars))):
                if side == "long":
                    if bars[k].l <= stop:
                        exit_px, reason, when = stop, "stop", bars[k].t
                        break
                    if bars[k].h >= tgt:
                        exit_px, reason, when = tgt, "target", bars[k].t
                        break
                else:
                    if bars[k].h >= stop:
                        exit_px, reason, when = stop, "stop", bars[k].t
                        break
                    if bars[k].l <= tgt:
                        exit_px, reason, when = tgt, "target", bars[k].t
                        break
                exit_px = bars[k].c
            precision = "daily"

        r = (exit_px - px) / risk if side == "long" else (px - exit_px) / risk
        out.append({
            "symbol": symbol, "rule": cfg["rule"], "params": cfg["params"],
            "date": day_of(bars[j].t), "side": side, "idx": j,
            "entry": px, "stop": stop, "target": tgt, "exit": exit_px,
            "reason": reason, "r": r, "net": r - cost / (risk * pv),
            "risk_pts": risk, "pv": pv, "round_trip_cost_usd": cost,
            "exited_at": clock(when) if when else None,
            "precision": precision, "tradeable": cfg["tradeable"],
            "finished": (j + hold - 1) < len(bars) - 1 or reason != "time",
        })
        busy = j + hold - 1
    return out


# ------------------------------------------------------------- correlation
def correlations(data: dict[str, list[Bar]]) -> dict[tuple[str, str], float]:
    """Daily close-to-close correlation, so the desk can spot the same bet twice."""
    rets = {}
    for sym, bars in data.items():
        rets[sym] = [bars[k].c / bars[k - 1].c - 1
                     for k in range(1, len(bars)) if bars[k - 1].c][-120:]
    out: dict[tuple[str, str], float] = {}
    names = list(rets)
    for a in range(len(names)):
        for b in range(a + 1, len(names)):
            x, y = rets[names[a]], rets[names[b]]
            n = min(len(x), len(y))
            if n < 30:
                continue
            x, y = x[-n:], y[-n:]
            mx, my = statistics.mean(x), statistics.mean(y)
            cov = sum((x[i] - mx) * (y[i] - my) for i in range(n)) / n
            sx, sy = statistics.pstdev(x), statistics.pstdev(y)
            if sx and sy:
                out[tuple(sorted((names[a], names[b])))] = round(cov / (sx * sy), 2)
    return out


# ------------------------------------------------------------------- state
def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except json.JSONDecodeError:
            pass
    return {"equity": EQUITY, "realised": 0.0, "day": None, "day_pnl": 0.0,
            "open_positions": [], "created": now_iso(), "cycles": 0}


def save_state(state: dict) -> None:
    DESK.mkdir(parents=True, exist_ok=True)
    state["updated"] = now_iso()
    tmp = STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE)


# ------------------------------------------------------------------- cycle
def cycle(write: bool = True, verbose: bool = True, shadow_days: int = 0) -> dict:
    DESK.mkdir(parents=True, exist_ok=True)
    shadow = shadow_days > 0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if shadow:
        since = (datetime.now(timezone.utc) - timedelta(days=shadow_days)).strftime("%Y-%m-%d")
        ledger_path, decision_path = SHADOW, SHADOW_DECISIONS
    else:
        if not SINCE.exists():
            SINCE.write_text(today + "\n")
        since = SINCE.read_text().strip() or today
        ledger_path, decision_path = LEDGER, DECISIONS

    state = load_state()
    state["cycles"] = state.get("cycles", 0) + 1
    if state.get("day") != today:
        state["day"] = today
        state["day_pnl"] = 0.0

    seen = {(r["symbol"], r["rule"], r["date"]) for r in read_jsonl(ledger_path)}
    decided = {(r["symbol"], r["rule"], r["date"]) for r in read_jsonl(decision_path)}

    data: dict[str, list[Bar]] = {}
    intra: dict[str, Intraday] = {}
    for symbol in CONFIGS:
        try:
            bars = fetch_daily(symbol)
        except Exception as err:  # noqa: BLE001
            if verbose:
                print(f"  {symbol}: daily feed unavailable ({err})")
            continue
        data[symbol] = bars
        intra[symbol] = Intraday(fetch_intraday(symbol), bars)
    corr = correlations(data)

    new_rows: list[dict] = []
    new_decisions: list[dict] = []
    if verbose:
        print("=" * 108)
        print(f"  DESK {'SHADOW REPLAY' if shadow else 'CYCLE'}  {now_iso()}   "
              f"equity ${state['equity']:,.0f}   sessions from {since}")
        print("=" * 108)

    for symbol, configs in CONFIGS.items():
        bars = data.get(symbol)
        if not bars:
            continue
        atr = atr_series(bars)
        emas = {k: ema([b.c for b in bars], k) for k in (20, 50, 200)}
        meta = CONTRACTS[symbol]
        comm = COMMS.get(symbol, COMMISSION)
        if verbose:
            print(f"\n  {symbol}  {meta['name']}  as {meta['trade_as']}  "
                  f"${meta['pv']:,.0f}/pt  last {bars[-1].c:,.2f}  "
                  f"({len(intra[symbol].bars)} intraday bars)")

        for cfg in configs:
            _fn, _g, rcfg = RULES[cfg["rule"]]
            trades = bracket_detailed(symbol, cfg, bars, atr, intra[symbol], comm,
                                      meta["pv"], meta["tick"], rcfg["entry"])
            tag = "" if cfg["tradeable"] else "  [record only]"
            if verbose:
                print(f"    {cfg['rule']:<19}{cfg['stop']}/{cfg['target']}/{cfg['hold']}{tag}")

            for t in trades:
                key = (symbol, cfg["rule"], t["date"])
                if not (t["finished"] and t["date"] >= since and key not in seen):
                    continue
                n = (contracts_for(t["risk_pts"], meta["pv"], t["round_trip_cost_usd"])
                     if cfg["tradeable"] else 0)
                usd = t["net"] * HAIRCUT * t["risk_pts"] * meta["pv"] * n
                new_rows.append({
                    "symbol": symbol, "rule": cfg["rule"], "params": cfg["params"],
                    "date": t["date"], "side": t["side"],
                    "entry": round(t["entry"], 4), "stop": round(t["stop"], 4),
                    "target": round(t["target"], 4), "exit": round(t["exit"], 4),
                    "exit_reason": t["reason"], "exited_at": t["exited_at"],
                    "r": round(t["r"], 3), "net_r": round(t["net"], 3),
                    "contracts": n, "usd": round(usd, 2),
                    "precision": t["precision"], "tradeable": cfg["tradeable"],
                    "shadow": shadow, "logged": now_iso(),
                })
                seen.add(key)
                if verbose:
                    mark = "WIN " if t["net"] > 0 else "LOSS"
                    print(f"      {mark} {t['date']} {t['side']:<5} {t['reason']:<6}"
                          f" {t['r']:+.2f}R  {n} lot(s)  ${usd:+,.0f}  "
                          f"[{t['precision']} fill]")

            if verbose:
                for t in trades:
                    if not t["finished"]:
                        n = contracts_for(t["risk_pts"], meta["pv"], t["round_trip_cost_usd"])
                        print(f"      OPEN  {t['date']} {t['side']:<5} entry {t['entry']:,.2f}"
                              f"  stop {t['stop']:,.2f}  target {t['target']:,.2f}  {n} lot(s)")
                for order in pending_orders(symbol, cfg, bars, atr, emas):
                    cost = 2 * (comm + meta["tick"] * meta["pv"])
                    n = contracts_for(order["stop_pts"], meta["pv"], cost)
                    fits = (f"{n} lot(s)" if n > 0 else "does not fit the budget") \
                        if cfg["tradeable"] else "record only"
                    print(f"      ORDER {order['side'].upper():<5} stop {order['trigger']:,.2f}"
                          f"  ·  risk {order['stop_pts']:,.2f}  ·  target {order['target_pts']:,.2f}"
                          f"  ·  {fits}")

            # ---- the committee speaks
            finished = [t for t in trades if t["finished"]]
            for t in (reversed(finished) if shadow else finished[-1:]):
                key = (symbol, cfg["rule"], t["date"])
                if key in decided or t["date"] < since:
                    continue
                # The agents must see the world as it looked on the signal night,
                # not as it looks now. Reading today's bar to judge a trade from
                # three weeks ago is how a replay lies to you.
                cut = t["idx"] + 1
                b = bars[:cut]
                a = atr[:cut]
                e = {k: v[:cut] for k, v in emas.items()}
                ctx = {
                    "trades": [x for x in finished if x["date"] < t["date"]],
                    "state": state, "corr": corr,
                    "open_positions": state.get("open_positions", []),
                    "open_risk": len(state.get("open_positions", [])),
                    "volatility": {},
                }
                ctx["volatility"] = agent_volatility(symbol, cfg, b, a, e, t["side"], ctx)
                votes = [
                    agent_trend(symbol, cfg, b, a, e, t["side"], ctx),
                    agent_structure(symbol, cfg, b, a, e, t["side"], ctx),
                    agent_momentum(symbol, cfg, b, a, e, t["side"], ctx),
                    ctx["volatility"],
                    agent_edge(symbol, cfg, b, a, e, t["side"], ctx),
                    agent_odds(symbol, cfg, b, a, e, t["side"], ctx),
                    agent_skeptic(symbol, cfg, b, a, e, t["side"], ctx),
                ]
                verdict = chair(votes, ctx)
                n = (contracts_for(t["risk_pts"], meta["pv"], t["round_trip_cost_usd"])
                     if cfg["tradeable"] else 0)
                record = {
                    "at": now_iso(), "symbol": symbol, "rule": cfg["rule"],
                    "date": t["date"], "side": t["side"], "price": round(t["entry"], 4),
                    "votes": votes, "verdict": verdict,
                    "outcome_r": round(t["net"], 3),
                    "outcome_usd": round(t["net"] * HAIRCUT * t["risk_pts"] * meta["pv"] * n, 2),
                    "shadow": shadow,
                    "agreed_with_outcome": (verdict["decision"] == "TRADE") == (t["net"] > 0),
                }
                new_decisions.append(record)
                decided.add(key)
                if verbose:
                    print(f"      CHAIR  {verdict['decision']}  {t['side']} {t['date']}"
                          f"  ·  {verdict['reason']}")
                    for v in votes:
                        print(f"        {v['agent']:<11} {v['vote']:<8} {v['note']}")

    if write:
        append_jsonl(ledger_path, new_rows)
        append_jsonl(decision_path, new_decisions)
        if not shadow:
            save_state(state)
        write_report()
    if verbose:
        print(f"\n  {'wrote' if write else 'would write'} {len(new_rows)} trade(s) and "
              f"{len(new_decisions)} committee record(s) -> {ledger_path.parent}")
    return {"trades": new_rows, "decisions": new_decisions, "state": state}


# ------------------------------------------------------------------ reports
def _block(rows: list[dict], decisions: list[dict], title: str, note: str) -> list[str]:
    lines = [f"## {title}", "", note, ""]
    if not rows:
        return lines + ["No completed signals yet.", ""]
    traded = [r for r in rows if r.get("tradeable")]
    lines += ["| set | trades | win (95% interval) | avg R | total R | USD |",
              "|---|---|---|---|---|---|"]
    for group, label in ((rows, "all recorded"), (traded, "sized (tradeable)")):
        if not group:
            continue
        rs = [r["net_r"] for r in group]
        wins = sum(1 for r in rs if r > 0)
        lo, hi = wilson(wins, len(rs))
        lines.append(f"| {label} | {len(rs)} | {100 * wins / len(rs):.0f}% "
                     f"({100 * lo:.0f}–{100 * hi:.0f}%) | {statistics.mean(rs):+.2f} | "
                     f"{sum(rs):+.2f} | ${sum(r['usd'] for r in group):+,.0f} |")
    approved = {(d["symbol"], d["rule"], d["date"]) for d in decisions
                if d["verdict"]["decision"] == "TRADE"}
    chair_rows = [r for r in traded if (r["symbol"], r["rule"], r["date"]) in approved]
    if chair_rows:
        rs = [r["net_r"] for r in chair_rows]
        wins = sum(1 for r in rs if r > 0)
        lo, hi = wilson(wins, len(rs))
        lines.append(f"| **chair approved only** | {len(rs)} | {100 * wins / len(rs):.0f}% "
                     f"({100 * lo:.0f}–{100 * hi:.0f}%) | {statistics.mean(rs):+.2f} | "
                     f"{sum(rs):+.2f} | ${sum(r['usd'] for r in chair_rows):+,.0f} |")
    lines.append("")

    timed = [r for r in rows if r.get("precision") == "15m"]
    if timed:
        decided = sum(1 for r in timed if r["exit_reason"] != "time")
        lines += [f"Fills: {len(timed)} trades resolved on fifteen-minute bars, "
                  f"{decided} ended on a stop or target rather than the clock — those are "
                  "the fills a daily backtest can only approximate.", ""]
        overnight = [r for r in timed if r.get("exited_at") and
                     int(r["exited_at"][11:13]) not in range(13, 21)]
        if overnight:
            rs = [r["net_r"] for r in overnight]
            lines += [f"{len(overnight)} of them closed outside US cash hours "
                      f"(avg {statistics.mean(rs):+.2f}R) — the twenty-three hour market "
                      "fills trades the daytime chart never shows.", ""]

    lines += ["| date | market | rule | side | entry | exit | why | R | USD |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in rows[-15:]:
        lines.append(f"| {r['date']} | {r['symbol']} | {r['rule']} | {r['side']} | "
                     f"{r['entry']:,.2f} | {r['exit']:,.2f} | {r['exit_reason']} | "
                     f"{r['net_r']:+.2f} | ${r['usd']:+,.0f} |")
    return lines + [""]


def write_report() -> None:
    fwd_rows = [r for r in read_jsonl(LEDGER) if not r.get("shadow")]
    fwd_dec = [d for d in read_jsonl(DECISIONS) if not d.get("shadow")]
    sh_rows = read_jsonl(SHADOW)
    sh_dec = read_jsonl(SHADOW_DECISIONS)
    state = load_state()

    lines = ["# The desk — forward record", "",
             f"Updated {now_iso()} · equity ${state['equity']:,.0f} · "
             f"{len(fwd_rows)} forward signals · {len(sh_rows)} shadow signals", ""]
    lines += _block(fwd_rows, fwd_dec, "Forward record",
                    "Starts the day the desk first ran and is never back-filled. "
                    "This is the only section that proves anything.")
    if sh_rows:
        lines += _block(sh_rows, sh_dec, "Shadow replay (recent sessions, not forward)",
                        "The same rules and the same agents, replayed over the last "
                        "sixty days so there is something to read today. Useful for "
                        "finding bugs and for judging the fills. It is **not** evidence "
                        "— those sessions already happened.")

    decisions = fwd_dec + sh_dec
    if decisions:
        took = [d for d in decisions if d["verdict"]["decision"] == "TRADE"]
        skipped = [d for d in decisions if d["verdict"]["decision"] == "PASS"]
        lines += ["## Are the agents adding anything?", ""]
        lines += ["| | decisions | avg outcome R | USD |", "|---|---|---|---|"]
        for group, label in ((took, "chair said TRADE"), (skipped, "chair said PASS")):
            if group:
                avg = statistics.mean(d["outcome_r"] for d in group)
                usd = sum(d.get("outcome_usd", 0) for d in group)
                lines.append(f"| {label} | {len(group)} | {avg:+.2f} | ${usd:+,.0f} |")
        lines.append("")
        if took and skipped:
            a = statistics.mean(d["outcome_r"] for d in took)
            b = statistics.mean(d["outcome_r"] for d in skipped)
            if a > b:
                lines += ["The chair is separating good signals from bad so far. Small "
                          "samples lie, so read this as a direction, not a result.", ""]
            else:
                lines += ["**The chair is not adding value yet** — it is rejecting trades "
                          "that did better than the ones it approved. Worth knowing before "
                          "a funded account depends on it.", ""]
        vetoes: dict[str, int] = {}
        for d in skipped:
            for b in d["verdict"]["blockers"]:
                vetoes[b] = vetoes.get(b, 0) + 1
        if vetoes:
            lines += ["Why the chair passed:", ""]
            lines += [f"- {reason} — {n}x"
                      for reason, n in sorted(vetoes.items(), key=lambda kv: -kv[1])]
            lines.append("")

    lines += ["## What this record cannot tell you", "",
              "Twenty trades is not a result. The backtest expectation for the tradeable",
              "rules is +0.55R to +0.62R per trade; anything within about ±0.4R of that",
              "after twenty trades is still noise. The number to act on is the one that",
              "survives a hundred.", ""]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines))


def report() -> None:
    write_report()
    print(REPORT.read_text())
    print(f"(written to {REPORT})")


def status() -> None:
    state = load_state()
    rows = [r for r in read_jsonl(LEDGER) if r.get("tradeable")]
    print("=" * 88)
    print(f"  DESK STATUS   {now_iso()}")
    print("=" * 88)
    print(f"  equity ${state['equity']:,.0f}   realised ${state['realised']:+,.0f}"
          f"   today ${state['day_pnl']:+,.0f} (stop at ${-DAILY_STOP:,.0f})")
    print(f"  cycles run {state.get('cycles', 0)}   first run {state.get('created')}")
    print(f"  open positions: {len(state.get('open_positions', []))}")
    for p in state.get("open_positions", []):
        print(f"    {p['symbol']} {p['side']} entry {p['entry']:,.2f} "
              f"stop {p['stop']:,.2f} target {p['target']:,.2f}")
    if rows:
        rs = [r["net_r"] for r in rows]
        print(f"  closed tradeable signals: {len(rs)} · {sum(rs):+.2f}R · "
              f"${sum(r['usd'] for r in rows):+,.0f} · "
              f"win {100 * sum(1 for r in rs if r > 0) / len(rs):.0f}%")
    else:
        print("  closed tradeable signals: 0 — nothing has completed yet")
    print()


def board_cmd(as_json: bool = False, classic: bool = False) -> None:
    """Today's six-bot board for all five markets, written for the dashboard.

    Separate from `--cycle` on purpose: a cycle answers "was the committee right
    about a finished trade", which needs history. The board answers "what would
    the desk do right now", which is the only thing a live hour can answer.
    """
    if classic:
        os.environ["DESK_CLASSIC"] = "1"
    rows = bots_live()
    DESK.mkdir(parents=True, exist_ok=True)
    BOARD.write_text(json.dumps({"at": now_iso(), "rows": rows}, indent=1))
    if as_json:
        print(json.dumps(rows, indent=1))
        return
    from bots import _print
    _print(rows)
    # The board file is overwritten every hour, so a call only survives if it is
    # appended here. This is the log that later makes confidence measurable.
    calls = DESK / "calls.jsonl"
    with calls.open("a") as fh:
        for r in rows:
            if r.get("error"):
                continue
            b = r.get("bots", {})
            fh.write(json.dumps({
                "at": r["at"], "symbol": r["symbol"], "call": r["call"],
                "confidence": r["confidence"],
                "setup": (b.get("1_opportunity") or {}).get("setup"),
                "regime": r.get("regime"),
                "governor": r.get("governor"),
            }) + "\n")
    # A markdown board, because the JSON is for programs and this is for a phone.
    md = ["# The board — " + now_iso(), "",
          "| market | call | conf | regime | setup | risk | roll |",
          "|---|---|---|---|---|---|---|"]
    for r in rows:
        if r.get("error"):
            md.append(f"| {r['symbol']} | feed down | — | — | — | — | — |")
            continue
        b = r.get("bots", {})
        md.append("| {sym} | **{call}** | {conf} | {reg} | {setup} | {risk} | {roll}d |".format(
            sym=r["symbol"], call=r["call"], conf=r["confidence"],
            reg=r.get("regime", "?"),
            setup=(b.get("1_opportunity") or {}).get("setup", "?"),
            risk=(b.get("5_risk") or {}).get("action", "?"),
            roll=(b.get("9_roll") or {}).get("days", "?")))
    md.append("")
    for r in rows:
        if r.get("call") in ("BUY", "SELL"):
            md.append(f"- **{r['symbol']} {r['call']}** — {r['why']}")
    md.append("")
    (DESK / "board.md").write_text("\n".join(md))
    print(f"  board written to {BOARD} and board.md; call appended to {calls.name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycle", action="store_true", help="one forward pass: decide, resolve, log")
    ap.add_argument("--backfill", type=int, default=0, metavar="DAYS",
                    help="shadow replay of the last N days (separate ledger)")
    ap.add_argument("--dry-run", action="store_true", help="a pass that writes nothing")
    ap.add_argument("--pending", action="store_true", help="resting orders only")
    ap.add_argument("--report", action="store_true", help="write and print the record")
    ap.add_argument("--status", action="store_true", help="open risk right now")
    ap.add_argument("--board", action="store_true", help="the bots, right now")
    ap.add_argument("--classic", action="store_true",
                    help="the original six bots only (A/B against the 13)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()
    if args.board:
        board_cmd(args.json, args.classic)
    elif args.report:
        report()
    elif args.status:
        status()
    elif args.pending:
        cycle(write=False)
    elif args.backfill:
        cycle(write=not args.dry_run, shadow_days=args.backfill)
    else:
        cycle(write=not args.dry_run)


if __name__ == "__main__":
    main()
