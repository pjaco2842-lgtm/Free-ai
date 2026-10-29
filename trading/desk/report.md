# The desk — forward record

Updated 2026-10-29T12:35:34Z · equity $25,000 · 0 forward signals · 4 shadow signals

## Forward record

Starts the day the desk first ran and is never back-filled. This is the only section that proves anything.

No completed signals yet.

## Shadow replay (recent sessions, not forward)

The same rules and the same agents, replayed over the last sixty days so there is something to read today. Useful for finding bugs and for judging the fills. It is **not** evidence — those sessions already happened.

| set | trades | win (95% interval) | avg R | total R | USD |
|---|---|---|---|---|---|
| all recorded | 4 | 50% (15–85%) | +1.03 | +4.13 | $-142 |
| sized (tradeable) | 2 | 50% (9–91%) | -0.42 | -0.85 | $-142 |

Fills: 4 trades resolved on fifteen-minute bars, 3 ended on a stop or target rather than the clock — those are the fills a daily backtest can only approximate.

1 of them closed outside US cash hours (avg +0.17R) — the twenty-three hour market fills trades the daytime chart never shows.

| date | market | rule | side | entry | exit | why | R | USD |
|---|---|---|---|---|---|---|---|---|
| 2026-09-11 | CL=F | fade_trend_day | short | 103.32 | 102.94 | time | +0.17 | $+25 |
| 2026-10-21 | CL=F | fade_trend_day | long | 99.25 | 97.06 | stop | -1.02 | $-167 |
| 2026-09-18 | NQ=F | close_extreme | long | 29,762.75 | 30,957.02 | target | +5.99 | $+0 |
| 2026-10-16 | NQ=F | close_extreme | long | 30,170.75 | 29,940.91 | stop | -1.01 | $-0 |

## Are the agents adding anything?

| | decisions | avg outcome R | USD |
|---|---|---|---|
| chair said PASS | 4 | +1.03 | $-142 |

Why the chair passed:

- win rate not better than a coin flip — 4x
- skeptic veto — 2x
- only 1/3 context agents agree — 2x
- 2/3 context agents disagree — 2x
- one contract's stop does not fit the risk budget — 2x

## What this record cannot tell you

Twenty trades is not a result. The backtest expectation for the tradeable
rules is +0.55R to +0.62R per trade; anything within about ±0.4R of that
after twenty trades is still noise. The number to act on is the one that
survives a hundred.
