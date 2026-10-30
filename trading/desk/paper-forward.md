# Paper forward record — CLOSED

> **Retired 2026-10-30.** The 15-minute GC/CL book is closed. Its workflow
> (`.github/workflows/paper.yml`) is deleted and no further trades will be recorded here.
> The record below is kept exactly as it stands — a closed book is not a deleted one, and
> the losers stay on the page.
>
> Why: re-tested against random entries with the identical stop, target, hold limit,
> session filter, frequency and costs, it cannot be told apart from a coin flip — GC sits
> at the 32nd percentile of 1000 random runs (p = 0.68), CL at the 21st (p = 0.79). Two
> defects also turned up: `step()` never implemented the `cool` parameter, so the desk ran
> 82 trades on CL where the tested rule takes 63, and GC halted at the $1,000 buffer, so
> its record was truncated as well as off-rule. Full working: `retest-intraday.md`.
>
> The account is carried by the daily book in `oracle-forward.md`.

Updated 2026-10-30T15:34Z · started 2026-10-29T19:27:59Z · equity $+368.40 (2 closed trades)

## Right now

| market | side | opened | entry | stop | target | bars held |
|---|---|---|---|---|---|---|
| GC=F | short | 2026-10-30 14:00 | 3,929.00 | 3,939.55 | 3,897.35 | 3 |

**GC=F** 15m breakout: close 3,920.70, RSI 24, TRAMA 3,975.73, ATR 13.44, last signal 5 bars ago

**CL=F** 15m breakout: close 103.86, RSI 47, TRAMA 102.10, ATR 0.45, no signal in the last 60 bars

## Today (UTC)

| time | market | side | entry | exit | why | $ |
|---|---|---|---|---|---|---|
| 2026-10-30 01:30 | CL=F | long | 102.76 | 103.90 | target | $+109.52 |
| 2026-10-30 13:45 | GC=F | short | 3,954.20 | 3,927.86 | target | $+258.88 |

Day total **$+368.40** across 2 trades.

## The record so far

- 2 trades, 2 winners (100%), net **$+368.40**
- $+184.20 per trade, median risk $63
- worst drawdown $0, 1 sessions
- longs 1 ($+110), shorts 1 ($+259)

| when | market | side | entry | exit | why | held | $ |
|---|---|---|---|---|---|---|---|
| 2026-10-30 01:30 | CL=F | long | 102.76 | 103.90 | target | 18 | $+109.52 |
| 2026-10-30 13:45 | GC=F | short | 3,954.20 | 3,927.86 | target | 2 | $+258.88 |

## What size would this take?

| contracts | $/day at the measured rate | one stop, all contracts | buffer needed |
|---|---|---|---|
| 1 | $+368 | $63 | $189 |
| 2 | $+737 | $126 | $377 |
| 5 | $+1,842 | $314 | $943 |
| 10 | $+3,684 | $629 | $1,887 |

To make $200 a day at this rate you would need **1 contracts**, about $34 of risk per stop — 0.0x the entire $1,000 buffer.
To make $500 a day: **1 contracts**.

The rate above is measured, not projected. It moves every time the record moves.
