# The 26,000-test paper book

Updated 2026-10-30T22:55Z · started 2026-10-30T21:05:00Z · equity **$+203.65** across 2 closed trades

## Orders standing for the next close

| session | market | rule | side | level | distance from last close | risk/contract |
|---|---|---|---|---|---|---|
| 2026-11-02 | NQ=F | nday_break-1 1.0A tp2 both | long | 29,180.00 | +637.00 | $1,360 |
| 2026-11-02 | NQ=F | nday_break-1 1.0A tp2 both | short | 28,232.75 | -310.25 | $1,360 |
| 2026-11-02 | NQ=F | nday_fade-5 0.75A tp1 both | long | 28,232.75 | -310.25 | $1,020 |
| 2026-11-02 | NQ=F | nday_fade-5 0.75A tp1 both | short | 30,178.00 | +1,635.00 | $1,020 |

A level is a resting buy/sell stop: if the session trades through it, the trade is taken and the record shows it after the close.

**Worst case next session**: if every standing order fills and every one stops out, that is **$2,380** against the $2,000 buffer. Not hidden.

## Today (UTC)

| date | market | rule | side | entry | exit | why | $ |
|---|---|---|---|---|---|---|---|
| 2026-10-30 | NQ=F | nday_break-1 1.0A tp2 both | short | 29,111.00 | 28,543.00 | close | $+1,132.52 |
| 2026-10-30 | NQ=F | nday_fade-5 0.75A tp1 both | long | 28,987.00 | 28,524.30 | stop | $-928.87 |

## The record

- 2 trades, 1 winners (50%), net **$+203.65**
- worst drawdown $-929 against a $2,000 buffer

**By rule**

| rule | trades | win | net $ | worst DD |
|---|---|---|---|---|
| nday_break-1 1.0A tp2 both | 1 | 100% | $+1,133 | $0 |
| nday_fade-5 0.75A tp1 both | 1 | 0% | $-929 | $-929 |

## Evaluation tracker

- net **$+203.65** of the **$3,000** target (+7%)
- **$+2,203.65** of room left before the $2,000 end-of-day buffer is gone
- 1 sessions traded, best day $+203.65, worst day $+203.65
- consistency: best day is **100%** of profit (rule: ≤40%) → **fail**

| date | market | rule | side | entry | exit | why | $ |
|---|---|---|---|---|---|---|---|
| 2026-10-30 | NQ=F | nday_break-1 1.0A tp2 both | short | 29,111.00 | 28,543.00 | close | $+1,132.52 |
| 2026-10-30 | NQ=F | nday_fade-5 0.75A tp1 both | long | 28,987.00 | 28,524.30 | stop | $-928.87 |

## What size would $200 a day take?

- 2 trades over 1 sessions, $+203.65 total, $+101.82/trade, median risk $1,080/contract
- one contract at this rate: $+204/session
- $200 a day would need 1 contracts = $1,060 of risk per stop, against a $2,000 buffer
