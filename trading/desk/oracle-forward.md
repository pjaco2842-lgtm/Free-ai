# The 26,000-test paper book

Updated 2026-10-29T22:29Z · started 2026-10-29T22:15:31Z · equity **$+66.52** across 1 closed trades

## Orders standing for the next close

| session | market | rule | side | level | distance from last close | risk/contract |
|---|---|---|---|---|---|---|
| 2026-10-30 | NQ=F | nday_break-1 1.0A tp2 both | long | 29,180.00 | +62.50 | $1,234 |
| 2026-10-30 | NQ=F | nday_break-1 1.0A tp2 both | short | 29,112.50 | -5.00 | $1,234 |
| 2026-10-30 | NQ=F | nr_break-2 1.0A tp2 both | long | 29,180.00 | +62.50 | $1,234 |
| 2026-10-30 | NQ=F | nr_break-2 1.0A tp2 both | short | 29,112.50 | -5.00 | $1,234 |

A level is a resting buy/sell stop: if the session trades through it, the trade is taken and the record shows it after the close.

**Worst case next session**: if every standing order fills and every one stops out, that is **$2,467** against the $1,000 buffer. Not hidden.

## Today (UTC)

No trade closed today. These rules take at most one per market per session, so a blank day is the design.

## The record

- 1 trades, 1 winners (100%), net **$+66.52**
- worst drawdown $0 against a $1,000 buffer

**By rule**

| rule | trades | win | net $ | worst DD |
|---|---|---|---|---|
| nday_break-1 1.0A tp2 both | 1 | 100% | $+67 | $0 |

## Evaluation tracker

- net **$+66.52** of the **$1,250** target (+5%)
- **$+1,066.52** of room left before the $1,000 end-of-day buffer is gone
- 1 sessions traded, best day $+66.52, worst day $+66.52
- consistency: best day is **100%** of profit (rule: ≤40%) → **fail**

| date | market | rule | side | entry | exit | why | $ |
|---|---|---|---|---|---|---|---|
| 2026-10-29 | NQ=F | nday_break-1 1.0A tp2 both | short | 29,180.00 | 29,145.00 | close | $+66.52 |

## What size would $200 a day take?

- 1 trades over 1 sessions, $+66.52 total, $+66.52/trade, median risk $1,155/contract
- one contract at this rate: $+67/session
- $200 a day would need 3 contracts = $3,471 of risk per stop, against a $1,000 buffer
