#!/usr/bin/env python3
"""
The six bots. One watches, one hunts, one reads, one plans, one protects, one calls.

    BOT 1  opportunity   scans for unusual movement and names the setup
    BOT 2  catalyst      what just happened: verified news, scheduled events, blackouts
    BOT 3  sentiment     what the crowd is saying — and how much of it is hype
    BOT 4  levels        trend, entry, stop, target
    BOT 5  risk          protect the account: size it, reduce it, or reject it
    BOT 6  final call    BUY / SELL / WAIT / SKIP, with a confidence and a reason

Design rules that are not negotiable
------------------------------------
* **No bot can overrule BOT 5.** A trade that fails the risk gate is `SKIP`, even
  if every other bot is screaming buy. The risk engine sits between the strategy
  and execution on purpose.
* **BOT 2 can only delay, never authorise.** A scheduled event inside the blackout
  window turns a call into `WAIT`. Absence of news is not evidence, so a silent or
  degraded swarm changes confidence by exactly zero and is reported as unknown.
* **BOT 3 cannot veto alone.** Sentiment is the weakest signal in this stack —
  it is a lexicon over headlines plus a price-crowding proxy, not a model reading
  X. It shades confidence and flags hype; it never blocks.
* **BOT 6 may only emit four words.** `validate_call()` enforces the enum, the
  confidence range and plain numbers, so a malformed or injected bot output fails
  closed instead of becoming an order.

What this is not: an LLM. Nothing here calls a model, so nothing here can be
prompt-injected, hallucinate a price, or invent a headline. Headlines arrive as
sanitised text from trading/swarm.py and are treated as data only.

    python3 trading/bots.py --board        # all five markets, right now
    python3 trading/bots.py --board --json # machine-readable
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from account import ACCOUNT, buffer_now  # noqa: E402  (the firm's rulebook)
from basket import CONFIGS, HAIRCUT, contracts_for  # noqa: E402
from edge import CONTRACTS  # noqa: E402
from lab import COMMS, COMMISSION, atr_series, ema  # noqa: E402
from scanner import rsi  # noqa: E402

# All of these come from trading/desk/account.json — the LucidFlex rulebook, not
# from taste. Change the account, change that file; do not re-tune these here.
EQUITY = float(ACCOUNT["start_balance"])
RISK = float(ACCOUNT["desk"]["risk_per_trade_pct"]) / 100.0
TARGET = float(ACCOUNT["profit_target"])
MAX_LOSS = float(ACCOUNT["max_loss"])
CONSISTENCY = float(ACCOUNT["consistency"]["rule"])
BUFFER_STOPS = float(ACCOUNT["desk"]["buffer_guard_stops"])
HALT_AT = ACCOUNT["desk"]["governor_halt_fraction"]
CAUTION_AT = ACCOUNT["desk"]["governor_caution_fraction"]
MAX_OPEN = int(ACCOUNT["desk"]["max_open"])
DAILY_STOP = ACCOUNT["desk"]["daily_stop"]  # Optional self-imposed stop, not the firm's DLL.
MIN_OPPORTUNITY = 45     # below this there is no setup worth planning

SETUP_NAMES = ("breakout", "pullback", "momentum", "continuation", "reversal")
CALLS = ("BUY", "SELL", "WAIT", "SKIP")


def classic_mode() -> bool:
    """DESK_CLASSIC=1 drops back to the original six bots.

    The seven context bots can only *remove* or *delay* a trade - none of them can
    create one - so classic mode is never more conservative than the full desk; it
    is the same desk with fewer refusals, which makes it a clean A/B test.
    """
    return os.environ.get("DESK_CLASSIC") == "1"


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _finite(*vals: float) -> bool:
    return all(isinstance(v, (int, float)) and math.isfinite(v) for v in vals)


# --------------------------------------------------------------------- BOT 1
def bot1_opportunity(bars, atr, emas) -> dict:
    """Is anything unusual happening, and what kind of setup is it?

    "Unusual" is measured against the market's own recent behaviour, never against
    an absolute number: a 40-point ES day is loud, a 40-point NQ day is a nap.
    """
    if len(bars) < 40 or len(atr) < 40:
        return {"bot": 1, "name": "opportunity", "score": 0, "setup": "none",
                "setups": [], "note": "not enough history", "metrics": {}}

    last, prev = bars[-1], bars[-2]
    rng = max(last.h - last.l, 1e-9)
    body = abs(last.c - last.o) / rng
    close_pos = (last.c - last.l) / rng

    hist = [b.h - b.l for b in bars[-21:-1]]
    mean_rng = statistics.mean(hist)
    sd_rng = statistics.pstdev(hist) or 1e-9
    range_z = (rng - mean_rng) / sd_rng

    vols = [b.v for b in bars[-21:-1] if b.v]
    rvol = (last.v / statistics.mean(vols)) if vols and last.v else 1.0

    a = atr[-1] or 1e-9
    gap_atr = (last.o - prev.c) / a if prev.c else 0.0
    live_atr = [x for x in atr[-120:] if x]
    atr_pct = round(100 * sum(1 for x in live_atr if x <= a) / len(live_atr)) if live_atr else 50

    window = bars[-20:]
    wide = bars[-60:]
    compression = ((max(b.h for b in window) - min(b.l for b in window)) /
                   max(max(b.h for b in wide) - min(b.l for b in wide), 1e-9))

    fast, slow = emas.get(50), emas.get(200)
    trend = 0
    if fast and slow and fast[-1] is not None and slow[-1] is not None:
        trend = 1 if fast[-1] > slow[-1] else -1
    fast20 = (emas.get(20) or [None])[-1] if emas.get(20) else None
    near_fast = bool(fast20 is not None and
                     min(abs(last.l - fast20), abs(last.h - fast20)) < 0.35 * a)
    rs = [v for v in rsi([b.c for b in bars], 14) if v is not None]
    r = rs[-1] if rs else 50.0
    higher_lows = last.l > prev.l
    lower_highs = last.h < prev.h

    setups = []

    def add(name: str, conf: float, note: str) -> None:
        setups.append({"name": name, "confidence": round(_clamp(conf), 0), "note": note})

    # breakout: expansion out of compression, closing at the extreme
    if range_z > 0.6 and compression < 0.85:
        side = "up" if close_pos >= 0.5 else "down"
        add("breakout", 40 + 18 * min(range_z, 2.5) + 20 * (1 - compression) +
            10 * (1 if (side == "up" and rvol > 1.2) or (side == "down" and rvol > 1.2) else 0),
            f"range {range_z:+.1f}σ vs 20 days, prior 20-day range is "
            f"{100 * compression:.0f}% of the 60-day range, close at "
            f"{100 * close_pos:.0f}% and volume {rvol:.1f}x")

    # pullback: with the trend, back at the fast average, then closing its way
    if trend and near_fast:
        with_side = (trend > 0 and last.c > last.o) or (trend < 0 and last.c < last.o)
        add("pullback", 42 + 25 * (1 if with_side else 0) + 12 * (1 if rvol < 1.1 else 0),
            f"price at the 20 EMA inside a {'rising' if trend > 0 else 'falling'} "
            f"50/200 structure, bar closed {'with' if with_side else 'against'} the trend")

    # momentum: wide body, wide range, close at the extreme
    if range_z > 1.0 and body > 0.55:
        add("momentum", 40 + 20 * min(range_z, 3) + 25 * body + 8 * min(rvol, 2),
            f"{body:.0%} body on a {range_z:+.1f}σ range, volume {rvol:.1f}x average")

    # continuation: trend intact, structure still making progress
    if (trend > 0 and higher_lows and close_pos > 0.5) or (trend < 0 and lower_highs and close_pos < 0.5):
        add("continuation", 45 + 15 * (1 if abs(gap_atr) < 1 else 0) + 10 * min(rvol, 2),
            f"trend {'up' if trend > 0 else 'down'}, "
            f"{'higher' if trend > 0 else 'lower'} {'lows' if trend > 0 else 'highs'} "
            f"intact, gap {gap_atr:+.2f} ATR")

    # reversal: stretched RSI plus a rejection close
    if (r >= 70 and close_pos < 0.35) or (r <= 30 and close_pos > 0.65):
        add("reversal", 40 + 22 * min(abs(r - 50) / 20, 1.5) + 15 * (1 - abs(close_pos - 0.5) * 2) ** 0,
            f"RSI14 {r:.0f} with the close at {100 * close_pos:.0f}% of the range "
            f"— stretched, and the close rejected the extreme")

    setups.sort(key=lambda s: -s["confidence"])
    best = setups[0] if setups else {"name": "none", "confidence": 0, "note": "no pattern present"}
    score = _clamp(best["confidence"] * 0.7 + min(atr_pct, 100) * 0.15 + min(range_z, 3) * 5)
    if atr_pct >= 97:
        score -= 15  # the most unusual thing that can happen is a stop that cannot be sized
    return {
        "bot": 1, "name": "opportunity",
        "score": round(_clamp(score)),
        "setup": best["name"],
        "setups": setups[:3],
        "note": best["note"],
        "metrics": {"range_z": round(range_z, 2), "rvol": round(rvol, 2),
                    "gap_atr": round(gap_atr, 2), "atr_percentile": atr_pct,
                    "compression": round(compression, 2), "rsi": round(r, 1),
                    "trend": trend, "close_pos": round(close_pos, 2)},
    }


# --------------------------------------------------------------------- BOT 2
def _easterless_events(now: datetime, symbol: str) -> list[dict]:
    """Scheduled, rule-based events. Recurring ones are computed; one-offs are not.

    FOMC and CPI dates are *not* derivable from a calendar rule, so they are not
    guessed here. Put them in trading/desk/calendar.json and they are read in.
    An invented date is worse than a missing one: it creates a false blackout and
    a false sense of safety.
    """
    out: list[dict] = []
    et = now.astimezone(timezone.utc)

    def at(dt: datetime, label: str, markets: tuple[str, ...], impact: str) -> None:
        if symbol not in markets:
            return
        out.append({"label": label, "at": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "impact": impact})

    # EIA petroleum status: Wednesday 15:30 UTC (10:30 ET) — crude and products
    days_ahead = (2 - et.weekday()) % 7
    eia = (et + timedelta(days=days_ahead)).replace(hour=15, minute=30, second=0, microsecond=0)
    at(eia, "EIA petroleum status", ("CL=F",), "high")

    # Non-farm payrolls: first Friday, 13:30 UTC (08:30 ET)
    first = et.replace(day=1, hour=13, minute=30, second=0, microsecond=0)
    nfp = first + timedelta(days=(4 - first.weekday()) % 7)
    if nfp < et:
        nxt = (et.replace(day=28) + timedelta(days=4)).replace(day=1)
        nfp = nxt + timedelta(days=(4 - nxt.weekday()) % 7)
    at(nfp, "Non-farm payrolls", ("ES=F", "NQ=F", "GC=F"), "high")

    # ISM manufacturing: first business day, 15:00 UTC (10:00 ET)
    ism = et.replace(day=1, hour=15, minute=0, second=0, microsecond=0)
    while ism.weekday() >= 5:
        ism += timedelta(days=1)
    at(ism, "ISM manufacturing", ("ES=F", "NQ=F"), "medium")

    # Month end / quarter end rebalance: last business day of the month
    nxt = (et.replace(day=28) + timedelta(days=4)).replace(day=1)
    last = nxt - timedelta(days=1)
    while last.weekday() >= 5:
        last -= timedelta(days=1)
    at(last.replace(hour=20, minute=0), "month-end rebalance", ("ES=F", "NQ=F"), "medium")

    # Quarterly roll: futures roll ~8 days before the third Friday
    third_fri = et.replace(day=1, hour=20, minute=0, second=0, microsecond=0)
    third_fri += timedelta(days=(4 - third_fri.weekday()) % 7) + timedelta(days=14)
    roll = third_fri - timedelta(days=8)
    at(roll, "quarterly futures roll", ("ES=F", "NQ=F", "GC=F"), "medium")

    return [e for e in out if e["at"] >= (et - timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ")]


def _calendar_events(symbol: str) -> list[dict]:
    path = Path(__file__).resolve().parent / "desk" / "calendar.json"
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text()).get("events", [])
    except json.JSONDecodeError:
        return []
    out = []
    for row in rows:
        if row.get("symbols") and symbol not in row["symbols"]:
            continue
        out.append({"label": str(row.get("label", "event"))[:60],
                    "at": str(row.get("at", ""))[:20],
                    "impact": str(row.get("impact", "high"))[:8],
                    "source": "calendar.json"})
    return out


def bot2_catalyst(symbol: str, news: dict | None, now: datetime | None = None) -> dict:
    """What just happened, and is a scheduled event about to hit?"""
    now = now or datetime.now(timezone.utc)
    markets = (news or {}).get("markets") or {}
    feed = markets.get(symbol, {})
    events = _easterless_events(now, symbol) + _calendar_events(symbol)

    blackout = False
    near = None
    soonest = None
    for ev in events:
        try:
            when = datetime.strptime(ev["at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        delta = (when - now).total_seconds() / 60
        if soonest is None or abs(delta) < abs(soonest[0]):
            soonest = (delta, ev)
        if ev["impact"] == "high" and -60 <= delta <= 30:
            blackout, near = True, (delta, ev)

    degraded = bool((news or {}).get("degraded")) or bool((news or {}).get("stale"))
    polarity = float(feed.get("polarity", 0.0))
    fresh = int(feed.get("fresh", 0))
    verified = bool(feed.get("verified_only", False))

    if blackout:
        verdict = "blackout"
        note = (f"{near[1]['label']} is {'in ' + str(int(near[0])) + ' min' if near[0] > 0 else str(int(-near[0])) + ' min ago'}"
                " — new risk inside the window is a coin toss with worse odds")
    elif degraded:
        verdict = "unknown"
        note = ("news feed is stale or unreachable — treated as unknown, not as quiet"
                if (news or {}).get("last") else "the swarm has never run")
    elif fresh == 0:
        verdict = "quiet"
        note = "no verified headline about this market inside the freshness window"
    else:
        verdict = "bullish" if polarity > 0.15 else "bearish" if polarity < -0.15 else "mixed"
        note = f"{fresh} verified fresh headline(s), polarity {polarity:+.2f}"

    return {
        "bot": 2, "name": "catalyst", "verdict": verdict, "blackout": blackout,
        "polarity": polarity if not degraded else 0.0,
        "fresh": fresh, "verified": verified, "degraded": degraded,
        "next_event": ({"label": soonest[1]["label"], "in_min": int(soonest[0]),
                        "impact": soonest[1]["impact"]} if soonest else None),
        "headlines": (feed.get("headlines") or [])[:4],
        "note": note,
    }


# --------------------------------------------------------------------- BOT 3
def bot3_sentiment(bars, atr, emas, news: dict | None, symbol: str) -> dict:
    """What people are saying — and how much of it is hype.

    Two halves, and both are weak on purpose so neither is trusted alone:
      * **headline tone** — a word list over verified fresh headlines. Trendy
        words are counted separately as hype rather than as opinion.
      * **crowding** — how far price has run from its own average in ATRs, plus
        RSI. When tone and crowding both scream, the crowd is usually late.
    """
    feed = ((news or {}).get("markets") or {}).get(symbol, {})
    tone = float(feed.get("polarity", 0.0))
    hype_hits = int(feed.get("hype_hits", 0))
    fresh = int(feed.get("fresh", 0))

    a = atr[-1] or 1e-9
    fast = emas.get(20)
    stretch = ((bars[-1].c - fast[-1]) / a) if fast and fast[-1] is not None else 0.0
    rs = [v for v in rsi([b.c for b in bars], 14) if v is not None]
    r = rs[-1] if rs else 50.0
    crowd = _clamp(50 + stretch * 18 + (r - 50) * 0.8)

    # hype = loud words per headline, weighted by how stretched price already is
    hype = _clamp(min(hype_hits / max(fresh, 1), 3) * 22 + max(stretch - 1.5, 0) * 18)

    score = _clamp(50 + tone * 45 - max(hype - 40, 0) * 0.35)
    label = ("euphoric" if score >= 75 else "positive" if score >= 58 else
             "negative" if score <= 42 else "mixed" if score <= 25 else "neutral")
    if score <= 25:
        label = "capitulating"
    return {
        "bot": 3, "name": "sentiment", "score": round(score), "label": label,
        "tone": round(tone, 2), "hype": round(hype), "crowding": round(crowd),
        "stretch_atr": round(stretch, 2), "rsi": round(r, 1),
        "basis": "headline lexicon + price crowding (no social feed, no model)",
        "note": (f"headline tone {tone:+.2f} over {fresh} verified item(s), "
                 f"hype {hype:.0f}/100, price {stretch:+.1f} ATR from the 20 EMA, "
                 f"RSI {r:.0f}"),
    }


# --------------------------------------------------------------------- BOT 4
def bot4_levels(symbol, bars, atr, emas, cfg, side: str) -> dict:
    """Trend, entry, stop, target — stated as prices, not opinions."""
    meta = CONTRACTS[symbol]
    a = atr[-1]
    if not a:
        return {"bot": 4, "name": "levels", "ok": False, "note": "no ATR"}
    last = bars[-1]
    entry = last.c
    risk = cfg["stop"] * a
    reward = cfg["target"] * a
    stop = entry - risk if side == "long" else entry + risk
    target = entry + reward if side == "long" else entry - reward

    fast, slow = emas.get(50), emas.get(200)
    trend = "flat"
    if fast and slow and fast[-1] is not None and slow[-1] is not None:
        trend = "up" if fast[-1] > slow[-1] else "down"
    aligned = (trend == "up" and side == "long") or (trend == "down" and side == "short")

    pdh, pdl = bars[-2].h, bars[-2].l
    week = bars[-6:-1] if len(bars) >= 6 else bars[-3:-1]
    pwh, pwl = max(b.h for b in week), min(b.l for b in week)
    round_step = 10 ** math.floor(math.log10(max(abs(entry), 1))) / 10 if entry else 1
    round_num = round(entry / round_step) * round_step

    # where the exit sits relative to structure, as a sanity check on the bracket
    room_up = (target - entry) / max(pdh - entry, 1e-9) if target > entry else None
    blockers = []
    if target > entry and pdh > entry and target < pdh:
        blockers.append("target sits inside yesterday's range")
    if not aligned:
        blockers.append(f"trend is {trend}, trade is {side}")

    return {
        "bot": 4, "name": "levels", "ok": True, "trend": trend, "aligned": aligned,
        "side": side, "entry": round(entry, 4), "stop": round(stop, 4),
        "target": round(target, 4), "risk_pts": round(risk, 4),
        "reward_pts": round(reward, 4), "rr": round(reward / risk, 2),
        "atr": round(a, 4), "trade_as": meta["trade_as"],
        "levels": {"prior_day_high": round(pdh, 4), "prior_day_low": round(pdl, 4),
                   "prior_week_high": round(pwh, 4), "prior_week_low": round(pwl, 4),
                   "round_number": round(round_num, 4),
                   "ema20": (round(emas[20][-1], 4)
                             if emas.get(20) and emas[20][-1] is not None else None)},
        "blockers": blockers,
        "note": (f"{trend} structure; {side} at {entry:,.2f} with stop {stop:,.2f} "
                 f"({risk:,.2f} pts) and target {target:,.2f} ({reward / risk:.1f}:1)"),
    }


# --------------------------------------------------------------------- BOT 5
def bot5_risk(symbol, plan: dict, state: dict | None, news: dict | None,
              catalyst: dict | None = None, vol_pct: int = 50,
              open_positions: list[dict] | None = None,
              correlations: dict | None = None) -> dict:
    """The account protector. Its only job is to say no, shrink, or allow.

    Every check below is a real limit from the plan, not a vibe: the risk budget,
    the daily stop, the position cap, the correlation rule, the consistency rule
    that actually fails a Lucid evaluation, and the volatility ceiling where a
    stop is a guess.
    """
    state = state or {}
    open_positions = open_positions or []
    correlations = correlations or {}
    meta = CONTRACTS[symbol]
    risk_pts, side = plan["risk_pts"], plan["side"]
    cost = 2 * (COMMS.get(symbol, COMMISSION) + meta["tick"] * meta["pv"])
    n = contracts_for(risk_pts, meta["pv"], cost, equity=EQUITY, risk_frac=RISK)
    stop_usd = risk_pts * meta["pv"] + cost
    win_usd = plan["reward_pts"] * meta["pv"] * HAIRCUT - cost

    checks: list[dict] = []
    hard: list[str] = []
    soft: list[str] = []

    def check(name: str, ok: bool, detail: str, fatal: bool = True) -> None:
        checks.append({"check": name, "ok": ok, "detail": detail})
        if not ok:
            (hard if fatal else soft).append(detail)

    check("budget", n > 0,
          f"one {meta['trade_as']} stop is ${stop_usd:,.0f} against a ${EQUITY * RISK:,.0f} budget")

    # The account's life, not the trade's size. A $1,000 end-of-day buffer is
    # about four micro stops, so the desk refuses new risk while it still has
    # fewer than BUFFER_STOPS (2.0) stops of room to be wrong in. This is the
    # check that turns "four losses and you're done" into "two losses and you stand down".
    # Two stops of room *before* entering, never one: after this loss the account
    # must still have a full stop of survival, and the desk must still be able to
    # trade its way back. Demanding the room after the trade instead would lock
    # the desk out of a recovery it is still capable of making.
    room_buffer = buffer_now(state)
    room_after = room_buffer - stop_usd
    stops = room_buffer / max(stop_usd, 1e-9)
    check("drawdown buffer", room_buffer >= BUFFER_STOPS * stop_usd,
          f"${room_buffer:,.0f} of the ${MAX_LOSS:,.0f} end-of-day buffer is left "
          f"({stops:.1f} stops); entering needs {BUFFER_STOPS:.1f} and would leave "
          f"${room_after:,.0f} ({room_after / max(stop_usd, 1e-9):.1f} stops)")
    day_pnl = float(state.get("day_pnl", 0.0))
    if DAILY_STOP is not None:
        check("daily stop", day_pnl > -float(DAILY_STOP),
              f"today is ${day_pnl:+,.0f}, stop at ${-float(DAILY_STOP):,.0f}")
    check("position cap", len(open_positions) < MAX_OPEN,
          f"{len(open_positions)} of {MAX_OPEN} allowed positions open")
    same_bet = []
    for other in open_positions:
        if other.get("side") != side:
            continue
        corr = correlations.get(tuple(sorted((symbol, other.get("symbol", "")))))
        if corr is not None and corr >= 0.70:
            same_bet.append(f"{other.get('symbol')} {corr:.2f}")
    check("correlation", not same_bet,
          f"already {side} " + ", ".join(same_bet) + " at ≥0.70 correlation" if same_bet
          else "no correlated position in the same direction")
    check("volatility", vol_pct < 97,
          f"ATR at the {vol_pct}th percentile of the last 120 sessions")

    # The consistency rule is what actually fails a Lucid evaluation: a single day
    # above half the target voids the pass even when the target is reached. It is
    # arithmetic, not judgement, and the arithmetic is worth stating plainly:
    # a best day of $967 against a $1,250 target is 77% of the profit, so that
    # evaluation cannot be passed with this bracket however well it trades.
    # A realised breach is fatal (the account is already void); a *projected* one
    # is a plan problem — soft-flagged with the number that would fix it, so the
    # desk keeps recording instead of going permanently silent.
    realised_best = float(state.get("best_day", 0.0))
    limit = TARGET * CONSISTENCY
    projected = max(realised_best, win_usd)
    min_target = 2 * win_usd
    check("consistency", projected <= limit,
          (f"a full win sets your best day at ${projected:,.0f} against a "
           f"${limit:,.0f} limit — this bracket needs a ${min_target:,.0f} profit target "
           f"to satisfy a {int(100 * CONSISTENCY)}% rule, or a partial exit near "
           f"${win_usd / 2:,.0f}"),
          fatal=realised_best > limit)
    if plan.get("blockers"):
        check("structure", False, "; ".join(plan["blockers"]), fatal=False)
    cat = catalyst or {}
    if cat.get("blackout"):
        check("event blackout", False, "a scheduled high-impact release is inside the window")
    if cat.get("degraded"):
        soft.append("news feed stale — sizing kept, confidence will be marked down")

    if hard:
        action = "reject"
    elif n > 1 and stop_usd > 0.6 * EQUITY * RISK:
        action = "reduce"
    elif soft:
        action = "approve"
    else:
        action = "approve"

    size = n if action in ("approve", "reduce") else 0
    if action == "reduce":
        size = 1
    return {
        "bot": 5, "name": "risk", "action": action, "contracts": size,
        "stop_usd": round(stop_usd, 2), "win_usd": round(win_usd, 2),
        "risk_pct": round(100 * stop_usd / EQUITY, 2),
        "checks": checks, "hard_blockers": hard, "soft_flags": soft,
        "headroom": {"daily_stop": round(float(DAILY_STOP) + day_pnl, 2) if DAILY_STOP is not None else None,
                     "consistency": round(limit - win_usd, 2),
                     "drawdown_buffer": round(room_buffer, 2)},
        "consistency": {"limit": round(limit, 2),
                        "projected_best_day": round(projected, 2),
                        "min_target_to_comply": round(min_target, 2)},
        "note": ("rejected: " + "; ".join(hard)) if hard else
                (f"approved {size} contract(s), ${stop_usd:,.0f} at risk "
                 f"({100 * stop_usd / EQUITY:.1f}% of equity), winning pays ${win_usd:,.0f}"),
    }


# --------------------------------------------------------------------- BOT 6
def bot6_final(opp: dict, cat: dict, sent: dict, plan: dict, risk: dict,
               history: list[dict] | None = None,
               extra: dict | None = None) -> dict:
    """The call. Four words only, one confidence, one reason, one falsifier."""
    history = history or []
    extra = extra or {}
    side = plan.get("side", "long")
    direction = "BUY" if side == "long" else "SELL"

    # A historical win rate turns "confident" into a number.
    odds_part = 50.0
    if len(history) >= 10:
        wins = sum(1 for t in history if t.get("net", 0) > 0)
        lo = max(0.0, wins / len(history) - 1.96 * math.sqrt((wins / len(history)) *
                                                             (1 - wins / len(history)) / len(history)))
        odds_part = 100 * lo
    elif history:
        odds_part = 55.0

    conf = (0.30 * opp.get("score", 0) + 0.15 * (70 if plan.get("aligned") else 30) +
            0.10 * (sent.get("score", 50)) + 0.20 * odds_part +
            0.10 * (100 if risk.get("action") == "approve" else 20) +
            0.15 * (70 if cat.get("verdict") in ("bullish", "bearish", "quiet") else 45))
    if cat.get("degraded"):
        conf = min(conf, 55.0)          # blind is not the same as safe
    if sent.get("hype", 0) > 70:
        conf -= 8
    if risk.get("soft_flags"):
        conf -= 5 * len(risk["soft_flags"])   # caveats cost conviction, not the trade

    gov = extra.get("governor") or {}
    roll = extra.get("roll") or {}
    regime = extra.get("regime") or {}
    setup = opp.get("setup")
    if regime.get("favours") and setup not in regime["favours"]:
        conf -= 10                      # wrong conditions for this setup
    if (extra.get("liquidity") or {}).get("thin"):
        conf -= 5
    if ((extra.get("calibration") or {}).get("samples") or 0) >= 20:
        worst = (extra["calibration"].get("accuracy") or {})
        if worst:
            conf -= 5                  # measured history, not a hunch

    if gov.get("action") == "halt":
        call, why = "SKIP", "governor halted the desk: " + "; ".join(gov.get("reasons", []))
    elif roll.get("status") == "block":
        call, why = "WAIT", roll.get("note", "contract roll is too close to add risk")
    elif risk.get("action") == "reject":
        call, why = "SKIP", risk.get("note", "risk gate rejected the trade")
    elif cat.get("blackout"):
        call, why = "WAIT", cat.get("note", "scheduled event inside the blackout window")
    elif opp.get("score", 0) < MIN_OPPORTUNITY:
        call, why = "WAIT", f"no setup worth planning (opportunity {opp.get('score', 0)}/100)"
    elif plan.get("blockers") and not plan.get("aligned"):
        call, why = "WAIT", "the trade fights the prevailing trend"
    elif conf < 45:
        call, why = "WAIT", f"confidence {conf:.0f} is below the 45 floor"
    else:
        call, why = direction, (f"{opp.get('setup')} setup at {opp.get('score')}/100, "
                                f"{cat.get('verdict')} news, {sent.get('label')} sentiment, "
                                f"{risk.get('contracts')} contract(s)")

    upcoming = (cat.get("next_event") or {}).get("label", "the next release")
    falsifier = (f"a close back through {plan.get('stop', 0):,.2f} invalidates it; "
                 f"if {upcoming} lands "
                 f"against the position before the target, take the stop, not a wider one")
    return {
        "bot": 6, "name": "final", "call": call, "side": side,
        "confidence": round(_clamp(conf)), "why": why, "falsifier": falsifier,
        "desk": {"regime": regime.get("label"), "governor": gov.get("action"),
                 "roll": roll.get("status")},
        "inputs": {"opportunity": opp.get("score"), "catalyst": cat.get("verdict"),
                   "sentiment": sent.get("label"), "risk": risk.get("action")},
    }


# --------------------------------------------------------------- BOT 0 regime
DESK = Path(__file__).resolve().parent / "desk"

REGIME_FAVOURS: dict[str, tuple[str, ...]] = {
    "trend_up": ("breakout", "momentum", "continuation", "pullback"),
    "trend_down": ("breakout", "momentum", "continuation", "pullback"),
    "chop": ("reversal", "pullback"),
    "high_vol": ("breakout", "reversal"),
    "drift": ("pullback", "continuation"),
    "unknown": SETUP_NAMES,
}


def _rows(name: str) -> list[dict]:
    path = DESK / name
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


def bot0_regime(bars, atr, emas) -> dict:
    """What kind of market is this? Every other bot is read against the answer.

    Five regimes from three things the market measures itself: where volatility
    sits in its own recent range, how far apart the 50/200 averages are in ATRs,
    and whether the last 20 days compressed inside the last 60. A setup that works
    in a trend is a different bet in chop, and the desk should say which one it is
    looking at rather than treating all conditions as equal.
    """
    live = [a for a in atr[-120:] if a]
    if len(live) < 20 or not bars:
        return {"bot": 0, "name": "regime", "label": "unknown",
                "favours": SETUP_NAMES, "note": "not enough history"}
    pct = round(100 * sum(1 for v in live if v <= atr[-1]) / len(live))
    a = atr[-1] or 1e-9
    fast, slow = emas.get(50), emas.get(200)
    sep = slope = 0.0
    if fast and slow and fast[-1] is not None and slow[-1] is not None:
        sep = (fast[-1] - slow[-1]) / a
    if fast and len(fast) > 21 and fast[-21] is not None:
        slope = (fast[-1] - fast[-21]) / a
    window = bars[-20:]
    wide = bars[-60:] if len(bars) >= 60 else bars
    comp = ((max(b.h for b in window) - min(b.l for b in window)) /
            max(max(b.h for b in wide) - min(b.l for b in wide), 1e-9))
    if pct >= 85:
        label = "high_vol"
    elif abs(sep) >= 1.5 and abs(slope) >= 1.0:
        label = "trend_up" if sep > 0 else "trend_down"
    elif abs(sep) < 0.5:
        label = "chop"
    else:
        label = "drift"
    return {"bot": 0, "name": "regime", "label": label,
            "favours": REGIME_FAVOURS[label], "atr_percentile": pct,
            "separation_atr": round(sep, 2), "slope_atr": round(slope, 2),
            "compression": round(comp, 2),
            "note": (f"{label}: 50/200 gap {sep:+.1f} ATR, 20-bar slope {slope:+.1f} ATR, "
                     f"20-day range {100 * comp:.0f}% of the 60-day, ATR {pct}th pct")}


def bot7_session(intraday: list | None, atr_now: float) -> dict:
    """Where in the twenty-three hour day are we, and how far has it already run?"""
    if not intraday:
        return {"bot": 7, "name": "session", "where": "daily only",
                "range_atr": None,
                "note": "no intraday bars — session context unavailable"}
    last = intraday[-1]
    stamp = datetime.fromtimestamp(last.t, tz=timezone.utc)
    hour = stamp.hour + stamp.minute / 60
    cash = 13.5 <= hour < 20.0
    recent = [b for b in intraday if b.t >= last.t - 18 * 3600]
    rng = (max(b.h for b in recent) - min(b.l for b in recent)) if recent else 0.0
    ratio = rng / max(atr_now, 1e-9)
    return {"bot": 7, "name": "session",
            "where": "US cash hours" if cash else "overnight / Globex",
            "hour_utc": round(hour, 2), "range_atr": round(ratio, 2),
            "stretched": ratio >= 1.6,
            "note": (f"{stamp:%H:%M}Z, {'cash hours' if cash else 'overnight'}; the last "
                     f"18 hours have travelled {ratio:.1f} ATR")}


def bot8_liquidity(intraday: list | None, atr_now: float) -> dict:
    """Can this be dealt at a fair price, or is the book thin?"""
    if not intraday:
        return {"bot": 8, "name": "liquidity", "score": 50, "thin": False,
                "note": "no intraday bars — liquidity unmeasured"}
    recent = intraday[-96:]
    ranges = [b.h - b.l for b in recent if b.h >= b.l]
    flat = sum(1 for b in recent if b.h == b.l)
    med = statistics.median(ranges) if ranges else 0.0
    med_ratio = med / max(atr_now, 1e-9)
    flat_share = flat / max(len(recent), 1)
    thin = med_ratio < 0.05 or flat_share > 0.20
    score = _clamp(100 - max(0.0, 0.10 - med_ratio) * 800 - flat_share * 150)
    return {"bot": 8, "name": "liquidity", "score": round(score), "thin": thin,
            "median_bar_atr": round(med_ratio, 3), "flat_share": round(flat_share, 2),
            "note": (f"median 15m bar is {med_ratio:.2f} ATR of the daily, "
                     f"{100 * flat_share:.0f}% of bars printed flat")}


def bot9_roll(symbol: str, now: datetime | None = None) -> dict:
    """How close is the contract roll? After it, the file name is a lie."""
    now = now or datetime.now(timezone.utc)
    quarter = symbol != "NKD=F"
    dates: list[datetime] = []
    if quarter:
        for year in (now.year, now.year + 1):
            for month in (3, 6, 9, 12):
                first = datetime(year, month, 1, tzinfo=timezone.utc)
                third_fri = first + timedelta(days=(4 - first.weekday()) % 7 + 14)
                dates.append(third_fri - timedelta(days=8))
        label = "quarterly roll"
    else:
        for k in range(5):
            index = now.month - 1 + k
            first = datetime(now.year + index // 12, index % 12 + 1, 1, tzinfo=timezone.utc)
            second_fri = first + timedelta(days=(4 - first.weekday()) % 7 + 7)
            dates.append(second_fri - timedelta(days=3))
        label = "monthly roll (approximate)"
    upcoming = min(d for d in dates if d >= now)
    days = (upcoming - now).total_seconds() / 86400
    status = "block" if days <= 3 else "warn" if days <= 7 else "ok"
    return {"bot": 9, "name": "roll", "status": status, "days": round(days, 1),
            "when": upcoming.strftime("%Y-%m-%d"), "label": label,
            "note": (f"{label} in {days:.1f} days ({upcoming:%Y-%m-%d}) — "
                     + {"block": "no new risk",
                        "warn": "the feed is about to change contract",
                        "ok": "comfortable"}[status])}


def bot10_benchmark(history: list[dict] | None, bars) -> dict:
    """Is any of this better than simply holding?"""
    if not history or len(history) < 10:
        return {"bot": 10, "name": "benchmark", "desk_total_r": 0.0,
                "buy_hold_pct": None,
                "note": f"{len(history or [])} settled trades — nothing to compare yet"}
    total = sum(float(t.get("net", 0)) for t in history)
    bh = (bars[-1].c / bars[0].c - 1) * 100 if bars else 0.0
    return {"bot": 10, "name": "benchmark", "desk_total_r": round(total, 2),
            "buy_hold_pct": round(bh, 1),
            "note": (f"{total:+.1f}R over {len(history)} trades against {bh:+.0f}% for "
                     "simply holding — R is per unit of risk and that is per unit of "
                     "capital, so this is context, not a score")}


def bot11_calibration(decisions: list[dict] | None) -> dict:
    """Has each agent been right? This is how a bot gets demoted on evidence."""
    settled = [d for d in (decisions or []) if d.get("votes")]
    if len(settled) < 20:
        return {"bot": 11, "name": "calibration", "samples": len(settled),
                "accuracy": {},
                "note": f"{len(settled)} settled decisions — calibration needs twenty"}
    tally: dict[str, list[int]] = {}
    for d in settled:
        good = float(d.get("outcome_r", 0)) > 0
        for v in d["votes"]:
            if v.get("vote") not in ("take", "against", "veto", "clear"):
                continue
            yes = v["vote"] in ("take", "clear")
            slot = tally.setdefault(str(v.get("agent")), [0, 0])
            slot[0] += 1
            slot[1] += int(yes == good)
    table = {a: round(100 * c / n) for a, (n, c) in tally.items() if n >= 5}
    return {"bot": 11, "name": "calibration", "samples": len(settled),
            "accuracy": table,
            "note": ("per-agent accuracy: " + ", ".join(
                f"{a} {p}%" for a, p in sorted(table.items(), key=lambda kv: -kv[1]))
                if table else "not enough per-agent samples")}


def bot12_governor(state: dict | None, history: list[dict] | None,
                   equity: float = EQUITY) -> dict:
    """The desk-level circuit breaker. It can stop everything, including BOT 6.

    BOT 5 protects one trade. This protects the account across all of them: a
    drawdown breaker, the daily stop, a losing streak and the kill switch. When it
    says halt, no market on the board is allowed to produce a BUY or a SELL.
    """
    state = state or {}
    eq = float(state.get("equity", equity))
    peak = float(state.get("peak_equity", equity))
    dd = max(peak - eq, 0.0)
    day = float(state.get("day_pnl", 0.0))
    losses = 0
    for t in reversed(history or []):
        if float(t.get("net", 0)) < 0:
            losses += 1
        else:
            break
    hard: list[str] = []
    soft: list[str] = []
    if (DESK / "KILL").exists():
        hard.append("kill switch engaged")
    buffer = buffer_now(state)
    halt_at = MAX_LOSS * float(HALT_AT) if HALT_AT is not None else None
    caution_at = MAX_LOSS * float(CAUTION_AT) if CAUTION_AT is not None else None
    if state.get("equity") is None or state.get("peak_eod") is None:
        hard.append("end-of-day high-water mark or equity is unknown")
    elif buffer <= 0 or (halt_at is not None and buffer <= halt_at):
        hard.append(f"${buffer:,.0f} of the ${MAX_LOSS:,.0f} drawdown buffer left")
    elif caution_at is not None and buffer <= caution_at:
        soft.append(f"${buffer:,.0f} of the ${MAX_LOSS:,.0f} drawdown buffer left")
    if DAILY_STOP is not None and day <= -float(DAILY_STOP):
        hard.append(f"daily loss ${day:,.0f}")
    if losses >= 4:
        soft.append(f"{losses} consecutive losses")
    action = "halt" if hard else "caution" if soft else "run"
    return {"bot": 12, "name": "governor", "action": action,
            "drawdown": round(dd, 2), "day_pnl": round(day, 2), "streak": losses,
            "buffer": round(buffer, 2),
            "reasons": hard + soft,
            "note": ({"halt": "HALTED: " + "; ".join(hard),
                      "caution": "caution: " + "; ".join(soft),
                      "run": f"clear — ${dd:,.0f} drawdown, ${day:+,.0f} today"}[action])}


def extra_context(symbol: str, bars, atr, emas, intraday=None, decisions=None,
                  state=None, history=None, now=None) -> dict:
    """Bots 0, 7, 8, 9, 10, 11, 12 — the context layer around the trade itself."""
    atr_now = atr[-1] if atr else 0.0
    return {
        "regime": bot0_regime(bars, atr, emas),
        "session": bot7_session(intraday, atr_now),
        "liquidity": bot8_liquidity(intraday, atr_now),
        "roll": bot9_roll(symbol, now),
        "benchmark": bot10_benchmark(history, bars),
        "calibration": bot11_calibration(decisions),
        "governor": bot12_governor(state, history),
    }


# ------------------------------------------------------------------ validation
def validate_call(rec: dict) -> dict:
    """Fail closed. A malformed bot record becomes SKIP, never an order."""
    problems = []
    if rec.get("call") not in CALLS:
        problems.append(f"call {rec.get('call')!r} not in {CALLS}")
    conf = rec.get("confidence")
    if not _finite(conf) or not 0 <= conf <= 100:
        problems.append(f"confidence {conf!r} outside 0-100")
    for key in ("why", "falsifier"):
        val = rec.get(key)
        if not isinstance(val, str) or not val.strip():
            problems.append(f"{key} missing")
        elif len(val) > 400:
            rec[key] = val[:400]
    if problems:
        rec = {**rec, "call": "SKIP", "confidence": 0,
               "why": "output failed validation: " + "; ".join(problems)}
        rec["invalid"] = problems
    return rec


# ----------------------------------------------------------------------- board
def board(symbol: str, bars, atr, emas, cfg: dict, side: str,
          news: dict | None = None, state: dict | None = None,
          history: list[dict] | None = None,
          open_positions: list[dict] | None = None,
          correlations: dict | None = None, now: datetime | None = None,
          intraday=None, decisions=None) -> dict:
    """Run all thirteen bots and return the record plus the final call."""
    opp = bot1_opportunity(bars, atr, emas)
    cat = bot2_catalyst(symbol, news, now)
    sent = bot3_sentiment(bars, atr, emas, news, symbol)
    plan = bot4_levels(symbol, bars, atr, emas, cfg, side)
    vol = opp.get("metrics", {}).get("atr_percentile", 50)
    risk = bot5_risk(symbol, plan, state, news, cat, vol,
                     open_positions, correlations)
    classic = classic_mode()
    extra = {} if classic else extra_context(symbol, bars, atr, emas, intraday,
                                             decisions, state, history, now)
    final = validate_call(bot6_final(opp, cat, sent, plan, risk, history, extra))
    bots = {"1_opportunity": opp, "2_catalyst": cat, "3_sentiment": sent,
            "4_levels": plan, "5_risk": risk, "6_final": final}
    for label, key in (("0_regime", "regime"), ("7_session", "session"),
                       ("8_liquidity", "liquidity"), ("9_roll", "roll"),
                       ("10_benchmark", "benchmark"),
                       ("11_calibration", "calibration"),
                       ("12_governor", "governor")):
        if key in extra:
            bots[label] = extra[key]
    return {"symbol": symbol, "as": CONTRACTS[symbol]["trade_as"],
            "at": (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "regime": (extra.get("regime") or {}).get("label", "classic"),
            "governor": (extra.get("governor") or {}).get("action", "classic"),
            "classic": classic, "bots": bots,
            "call": final["call"], "confidence": final["confidence"],
            "why": final["why"]}


def _live_side(opp: dict, emas) -> str:
    setup = opp.get("setup")
    if setup == "reversal":
        return "short" if opp["metrics"]["rsi"] >= 70 else "long"
    if setup in ("pullback", "continuation"):
        return "long" if opp["metrics"]["trend"] >= 0 else "short"
    return "long" if opp["metrics"]["close_pos"] >= 0.5 else "short"


def live(symbols: list[str] | None = None, use_news: bool = True) -> list[dict]:
    """Today's board for every market. One network pass, no writes to the ledger."""
    from lab import fetch_daily
    from swarm import latest

    news = latest() if use_news else {"markets": {}, "degraded": True}
    decisions = _rows("decisions.jsonl") + _rows("shadow_decisions.jsonl")
    history = [{"net": float(r.get("net_r", 0))}
               for r in _rows("ledger.jsonl") if r.get("tradeable") is not False]
    try:
        state = json.loads((DESK / "state.json").read_text())
    except Exception:  # noqa: BLE001 - a missing state file is a fresh account
        state = {}
    try:
        from desk import fetch_intraday   # lazy: desk imports this module at load
    except Exception:  # noqa: BLE001
        fetch_intraday = None
    out = []
    for symbol in symbols or list(CONFIGS):
        try:
            bars = fetch_daily(symbol)
        except Exception as err:  # noqa: BLE001
            out.append({"symbol": symbol, "error": f"feed unavailable: {err}",
                        "call": "SKIP"})
            continue
        atr = atr_series(bars)
        emas = {k: ema([b.c for b in bars], k) for k in (20, 50, 200)}
        cfg = CONFIGS[symbol][0]
        opp = bot1_opportunity(bars, atr, emas)
        side = _live_side(opp, emas)
        intraday = []
        if fetch_intraday is not None:
            try:
                intraday = fetch_intraday(symbol)
            except Exception:  # noqa: BLE001 - session bots degrade, they never fail
                intraday = []
        out.append(board(symbol, bars, atr, emas, cfg, side, news,
                         state=state, history=history, intraday=intraday,
                         decisions=decisions))
    return out


def _print(rows: list[dict]) -> None:
    for r in rows:
        print("=" * 100)
        if r.get("error"):
            print(f"  {r['symbol']}  {r['error']}")
            continue
        b = r["bots"]
        opp, cat, sent, plan, risk, final = (b["1_opportunity"], b["2_catalyst"],
                                             b["3_sentiment"], b["4_levels"],
                                             b["5_risk"], b["6_final"])
        regime = b.get("0_regime") or {}
        sess = b.get("7_session") or {}
        liq = b.get("8_liquidity") or {}
        roll = b.get("9_roll") or {}
        bench = b.get("10_benchmark") or {}
        cal = b.get("11_calibration") or {}
        gov = b.get("12_governor") or {}
        badge = ""
        if regime or gov or roll:
            badge = (f"   [{regime.get('label', '?')} · gov {gov.get('action', '?')}"
                     f" · roll {roll.get('days', '?')}d]")
        print(f"  {r['symbol']:<7} as {r['as']:<18} CALL {final['call']:<5} "
              f"{final['confidence']:>3}/100   {r['at']}{badge}")
        print("-" * 100)
        if regime:
            print(f"   BOT 0  regime       {regime.get('label', '?'):<12} {regime.get('note', '')[:68]}")
        print(f"   BOT 1  opportunity  {opp['score']:>3}/100  {opp['setup']:<12} {opp['note'][:70]}")
        print(f"   BOT 2  catalyst     {cat['verdict']:<10} {cat['note'][:70]}")
        for h in cat.get("headlines", [])[:2]:
            print(f"          [{h['age_min']:>5.0f}m {h['feed']}] {h['title'][:70]}")
        print(f"   BOT 3  sentiment    {sent['score']:>3}/100  {sent['label']:<12} {sent['note'][:70]}")
        if plan.get("ok"):
            print(f"   BOT 4  levels       {plan['side']:<5} entry {plan['entry']:,.2f}  "
                  f"stop {plan['stop']:,.2f}  target {plan['target']:,.2f}  "
                  f"({plan['rr']:.1f}:1)")
        print(f"   BOT 5  risk         {risk['action'].upper():<8} {risk['note'][:70]}")
        if sess:
            print(f"   BOT 7  session      {sess.get('where', '?'):<18} {sess.get('note', '')[:64]}")
        if liq:
            print(f"   BOT 8  liquidity    {liq.get('score', '?'):>3}/100  "
                  f"{'thin' if liq.get('thin') else 'normal':<8} {liq.get('note', '')[:62]}")
        if roll:
            print(f"   BOT 9  roll         {roll.get('status', '?'):<8} {roll.get('note', '')[:70]}")
        print(f"   BOT 6  final        {final['call']:<5} {final['confidence']:>3}/100")
        print(f"          why: {final['why'][:92]}")
        if bench:
            print(f"   BOT 10 benchmark    {bench.get('desk_total_r', 0):+.1f}R vs "
                  f"{bench.get('buy_hold_pct')}% hold  ·  BOT 11 calibration: "
                  f"{cal.get('samples', 0)} samples")
        if gov:
            print(f"   BOT 12 governor     {gov.get('action', '?'):<8} {gov.get('note', '')[:70]}")
    print("=" * 100)
    print("  Nothing here places an order. A CALL is a decision to be recorded, not a fill.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--symbols", nargs="*")
    ap.add_argument("--classic", action="store_true",
                    help="the original six bots only")
    args = ap.parse_args()
    if args.classic:
        os.environ["DESK_CLASSIC"] = "1"
    rows = live(args.symbols)
    if args.json:
        print(json.dumps(rows, indent=1))
    else:
        _print(rows)


if __name__ == "__main__":
    main()
