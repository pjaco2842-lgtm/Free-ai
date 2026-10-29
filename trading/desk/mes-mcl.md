# MES and MCL — can $200 a day fit a $1,000 buffer?

Generated 2026-10-29T20:05Z · one micro contract · $1.24/side + 1 tick slippage per side

Same aggressive sweep as `aggressive.md` (six signal families, four exits, chosen on
the first half of the sample, scored on the second half it never saw). The difference
is that risk per stop is measured, because on this account that is the binding limit.

## The chosen rule, and what one stop costs

| market | tf | rule | test trades | /day | win | median risk/stop | net $ | $/session | max DD |
|---|---|---|---|---|---|---|---|---|---|
| ES=F | 15m | breakout | 91 | 3.0 | 40% | $22 | $+71 | $+2 | $-280 |
| CL=F | 15m | breakout | 66 | 2.2 | 30% | $36 | $+305 | $+10 | $-816 |
| ES=F | 5m | confluence | 86 | 6.1 | 29% | $22 | $-849 | $-61 | $-1,009 |
| CL=F | 5m | trama_cross | 76 | 5.4 | 24% | $20 | $-386 | $-28 | $-496 |

With the US-session filter the paper rule uses (13:00-20:00 UTC):

| market | tf | rule | trades | $/session (US hours only) |
|---|---|---|---|---|
| ES=F | 15m | breakout | 32 | $-2 |
| CL=F | 15m | breakout | 28 | $+6 |
| ES=F | 5m | confluence | 26 | $-26 |
| CL=F | 5m | trama_cross | 30 | $-14 |

## What $200 and $500 a day would need

| market | tf | rule | $/session | risk/stop | contracts for $200 | risk at that size | stops until the buffer is gone |
|---|---|---|---|---|---|---|---|
| ES=F | 15m | breakout | $+2 | $22 | 84.0 | $1,823 | 0.55 |
| CL=F | 15m | breakout | $+10 | $36 | 19.7 | $712 | 1.40 |
| ES=F | 5m | confluence | $-61 | $22 | — | — | — |
| CL=F | 5m | trama_cross | $-28 | $20 | — | — | — |

## The largest size the buffer can carry

A five-stop run is ordinary at a 30-40% win rate. This is the size that keeps five
stops inside $1,000, and what that size earns at the measured rate.

| market | tf | rule | risk/stop | max contracts | $/day at that size | five stops |
|---|---|---|---|---|---|---|
| ES=F | 15m | breakout | $22 | 9 | +21 | $976 |
| CL=F | 15m | breakout | $36 | 5 | +51 | $905 |
| ES=F | 5m | confluence | $22 | 9 | -546 | $994 |
| CL=F | 5m | trama_cross | $20 | 9 | -248 | $906 |

## The whole population, not just the pick

| market | tf | strategy | configs | positive out of sample | median $/session | median risk | median trades/day |
|---|---|---|---|---|---|---|---|
| ES=F | 15m | trama_cross | 4 | 75% | $+10 | $25 | 1.8 |
| ES=F | 5m | rsi_pull | 8 | 62% | $+5 | $16 | 2.8 |
| CL=F | 15m | trama_cross | 4 | 75% | $+5 | $34 | 1.5 |
| CL=F | 15m | rsi_rev | 2 | 50% | $-2 | $34 | 1.2 |
| ES=F | 5m | breakout | 8 | 38% | $-2 | $16 | 8.3 |
| ES=F | 15m | breakout | 8 | 25% | $-6 | $30 | 2.2 |
| CL=F | 15m | mom_align | 4 | 25% | $-7 | $34 | 1.6 |
| CL=F | 15m | rsi_pull | 4 | 0% | $-8 | $32 | 1.7 |
| ES=F | 15m | mom_align | 7 | 29% | $-10 | $27 | 1.5 |
| CL=F | 15m | breakout | 8 | 12% | $-10 | $36 | 2.1 |
| ES=F | 15m | rsi_pull | 4 | 0% | $-11 | $26 | 1.5 |
| CL=F | 15m | confluence | 8 | 0% | $-11 | $32 | 2.2 |
| CL=F | 5m | breakout | 8 | 12% | $-13 | $20 | 7.4 |
| CL=F | 5m | rsi_rev | 8 | 12% | $-14 | $20 | 2.5 |
| ES=F | 15m | confluence | 8 | 38% | $-15 | $27 | 2.3 |
| ES=F | 5m | trama_cross | 8 | 0% | $-17 | $16 | 4.3 |
| ES=F | 5m | mom_align | 8 | 0% | $-19 | $15 | 4.0 |
| CL=F | 5m | confluence | 8 | 0% | $-22 | $19 | 6.4 |
| CL=F | 5m | trama_cross | 8 | 0% | $-24 | $21 | 4.0 |
| CL=F | 5m | mom_align | 8 | 0% | $-26 | $19 | 4.0 |
| ES=F | 15m | rsi_rev | 3 | 0% | $-41 | $36 | 1.4 |
| ES=F | 5m | rsi_rev | 8 | 0% | $-42 | $18 | 2.4 |
| CL=F | 5m | rsi_pull | 8 | 0% | $-46 | $18 | 3.0 |
| ES=F | 5m | confluence | 8 | 0% | $-55 | $15 | 6.8 |

Chosen on `train`, measured on `test` (second half). `stop_first` throughout:
when a bar held both stop and target, the stop was assumed to fill.
