#!/usr/bin/env python3
"""The account this desk trades for — the firm's rulebook, in one file.

Why this exists
---------------
Every rail used to be a constant: a $500 daily stop, an $800 drawdown breaker, a
50% consistency cap. Those were guesses about somebody else's rulebook. LucidFlex
has a $1,000 end-of-day trailing drawdown and standard 40% consistency test for
25K evaluation accounts; a daily loss limit and 50% consistency are optional.
The user's purchased customizations and intraday breach semantics are unconfirmed.
The legacy desk is paused; these helpers are not a complete account simulator.

The one thing a config cannot fix
---------------------------------
One micro ES contract risks about $209 at the desk's stop. Against a $1,000
buffer that is roughly four losses from dead, and there is no smaller contract to
size down into. The protection therefore has to come from three places instead of
size: the buffer guard (no new risk with fewer than 2.5 stops of room), one
position at a time, and selectivity. That is a real constraint of a 25K Flex
account, not a setting to tune away.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATH = HERE / "desk" / "account.json"

# Historical defaults for helpers only. Actual account customizations require
# verification; a missing/broken profile is not evidence of the purchased rules.
DEFAULTS: dict = {
    "firm": "Lucid Trading",
    "product": "LucidFlex",
    "phase": "evaluation",
    "start_balance": 25000,
    "profit_target": 1250,
    "max_loss": 1000,
    "drawdown": {"type": "end_of_day_trailing", "amount": 1000,
                 "lock_at_start_balance": False, "locked_floor": 25100},
    "daily_loss_limit": None,
    "stop_loss_required": False,
    "consistency": {"rule": 0.40, "add_on": 0.50, "applies_to": "evaluation only"},
    "desk": {"risk_per_trade_pct": 1.0, "max_open": 1, "daily_stop": 400,
             "buffer_guard_stops": 2.0, "governor_halt_fraction": 0.30,
             "governor_caution_fraction": 0.55},
}


def load(path: Path | None = None) -> dict:
    """Read the profile, one level deep, and never raise on a bad file."""
    data = json.loads(json.dumps(DEFAULTS))
    try:
        raw = json.loads((path or PATH).read_text())
    except (OSError, json.JSONDecodeError):
        return data
    for key, val in raw.items():
        if isinstance(val, dict) and isinstance(data.get(key), dict):
            data[key].update(val)
        else:
            data[key] = val
    return data


ACCOUNT = load()


def floor_for(peak_eod: float) -> float:
    """The balance that ends the account, given the end-of-day high-water mark.

    For the configured 25K evaluation, the floor follows closing balances up to
    the published $25,100 locked floor. Payout-triggered locking is not modeled.
    """
    start = float(ACCOUNT["start_balance"])
    amount = float(ACCOUNT["max_loss"])
    floor = float(peak_eod) - amount
    locked = ACCOUNT["drawdown"].get("locked_floor")
    if locked is not None:
        floor = min(floor, float(locked))
    elif ACCOUNT["drawdown"].get("lock_at_start_balance", True):
        floor = min(floor, start)
    return max(floor, start - amount)


def buffer_now(state: dict) -> float:
    """Room against the previous closing high; fail closed if it is unknown.

    Intraday equity is not an EOD high and must not be used to advance the floor.
    This does not decide whether a firm's intraday breach rule applies.
    """
    state = state or {}
    if state.get("equity") is None or state.get("peak_eod") is None:
        return 0.0
    try:
        equity = float(state["equity"])
        peak = float(state["peak_eod"])
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(equity) or not math.isfinite(peak) or peak < float(ACCOUNT["start_balance"]):
        return 0.0
    return max(equity - floor_for(peak), 0.0)


def stops_left(state: dict, stop_usd: float) -> float:
    """How many more losses of this size the account can absorb."""
    return buffer_now(state) / stop_usd if stop_usd > 0 else float("inf")
