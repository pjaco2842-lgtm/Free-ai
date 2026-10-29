#!/usr/bin/env python3
"""The account this desk trades for — the firm's rulebook, in one file.

Why this exists
---------------
Every rail used to be a constant: a $500 daily stop, an $800 drawdown breaker, a
50% consistency cap. Those were guesses about somebody else's rulebook. LucidFlex
is not "2% a day": it is a $1,000 end-of-day trailing drawdown, no daily loss
limit, and a 40% consistency test on the evaluation. A rail stricter than the
firm's rule throws away edge; a rail looser than it throws away the account.

So the rails are read from desk/account.json, and what the bots enforce is what
the firm actually enforces.

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
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATH = HERE / "desk" / "account.json"

# Kept identical to desk/account.json so a missing or broken file degrades to the
# same rules instead of to no rules at all.
DEFAULTS: dict = {
    "firm": "Lucid Trading",
    "product": "LucidFlex",
    "phase": "evaluation",
    "start_balance": 25000,
    "profit_target": 1250,
    "max_loss": 1000,
    "drawdown": {"type": "end_of_day_trailing", "amount": 1000,
                 "lock_at_start_balance": True},
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

    Trailing means the floor follows the high-water balance up. It stops at the
    starting balance, which is the conservative assumption: if the firm trails
    further than that, this understates the room left rather than overstating it.
    """
    start = float(ACCOUNT["start_balance"])
    amount = float(ACCOUNT["max_loss"])
    floor = float(peak_eod) - amount
    if ACCOUNT["drawdown"].get("lock_at_start_balance", True):
        floor = min(floor, start)
    return max(floor, start - amount)


def buffer_now(state: dict) -> float:
    """Dollars between the current balance and the level that ends the account."""
    state = state or {}
    start = float(ACCOUNT["start_balance"])
    equity = float(state.get("equity", start))
    peak = float(state.get("peak_equity", max(equity, start)))
    return max(equity - floor_for(max(peak, equity)), 0.0)


def stops_left(state: dict, stop_usd: float) -> float:
    """How many more losses of this size the account can absorb."""
    return buffer_now(state) / stop_usd if stop_usd > 0 else float("inf")
