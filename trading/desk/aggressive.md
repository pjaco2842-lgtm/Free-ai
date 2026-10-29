# The aggressive engine — RSI, TRAMA, EMA, ~one trade an hour

Generated 2026-10-29T19:11Z · one micro contract · $1.24/side + 1 tick slippage per side

Every combination is chosen on the first half of the sample with a frequency floor, then
measured on the second half, which it never saw. The bracket is the ambiguous-bar test:
worst case assumes the stop filled first when a bar held both, best case the target.

## Out of sample, by signal family

| strategy | markets | trades | per session | win | avg R | net $ (worst) | net $ (best) | worst DD |
|---|---|---|---|---|---|---|---|---|
| trama_cross | 1 | 77 | 5.5 | 23% | -0.31 | $-412 | $-412 | $-496 |
| mom_align | 1 | 56 | 4.0 | 29% | -0.33 | $-601 | $-501 | $-601 |
| confluence | 3 | 300 | 10.0 | 27% | -0.22 | $-3,219 | $-2,639 | $-1,958 |
| breakout | 5 | 452 | 15.1 | 35% | -0.04 | $-4,252 | $+1,130 | $-9,222 |

## The chosen rule per market

| market | tf | rule | exits | 2nd-half trades | /day | net $ worst→best | max DD |
|---|---|---|---|---|---|---|---|
| ES=F | 5m | confluence | 1.5A/3.0A 48b | 87 | 6.2 | $-828 → $-779 | $-1,010 |
| NQ=F | 5m | confluence | 1.0A/3.0A 48b | 119 | 8.5 | $-1,740 → $-1,209 | $-1,958 |
| GC=F | 5m | mom_align | 0.75A/1.5A 24b | 56 | 4.0 | $-601 → $-501 | $-601 |
| CL=F | 5m | trama_cross | 1.0A/3.0A 48b | 77 | 5.5 | $-412 → $-412 | $-496 |
| NKD=F | 5m | breakout | 1.0A/2.0A 24b | 114 | 8.8 | $-1,565 → $+680 | $-4,491 |
| ES=F | 15m | breakout | 0.75A/1.5A 24b | 75 | 2.5 | $-93 → $+5 | $-447 |
| NQ=F | 15m | confluence | 0.75A/1.5A 24b | 94 | 3.1 | $-651 → $-651 | $-1,128 |
| GC=F | 15m | breakout | 1.0A/3.0A 48b | 67 | 2.2 | $+484 → $+766 | $-1,201 |
| CL=F | 15m | breakout | 1.0A/3.0A 48b | 72 | 2.4 | $-10 → $-10 | $-738 |
| NKD=F | 15m | breakout | 0.75A/1.5A 24b | 124 | 4.1 | $-3,067 → $-311 | $-9,222 |

## Portfolio, second half

NKD is left out on purpose: it moves $25 a tick, so one tick of slippage is a fifth of a
typical stop and its dollar figures swamp the other four markets.

| timeframe | markets | trades | per session | trades/hour | $/session worst→best |
|---|---|---|---|---|---|
| 15m | 4 | 308 | 10.3 | 0.45 | $-9 → $+4 |
| 5m | 4 | 339 | 24.2 | 1.05 | $-256 → $-207 |

## Improvement loop — session and volatility filters

`hours` trades only 13:00-20:00 UTC. `vol` requires ATR to sit between 0.7x and
1.6x its own 60-bar median, so it skips dead tape and panics alike.

| market | tf | rule | base $/session | US hours | vol band | both |
|---|---|---|---|---|---|---|
| ES=F | 15m | breakout | $-3 | $-3 | $-4 | $-1 |
| NQ=F | 15m | confluence | $-22 | $-30 | $-21 | $-13 |
| GC=F | 15m | breakout | $+16 | $+37 | $+6 | $+19 |
| CL=F | 15m | breakout | $-0 | $+16 | $-16 | $+11 |

## Robustness — every candidate config, not just the picked one

One positive config proves nothing when many were tried. This is the whole population.

| strategy | tf | configs | positive out of sample | median $/session | median trades/day |
|---|---|---|---|---|---|
| trama_cross | 15m | 2 | 100% | $+17 | 2.4 |
| rsi_pull | 5m | 20 | 55% | $+1 | 4.3 |
| breakout | 15m | 20 | 40% | $-4 | 2.9 |
| breakout | 5m | 40 | 42% | $-4 | 7.9 |
| trama_cross | 5m | 37 | 24% | $-12 | 4.3 |
| confluence | 15m | 14 | 14% | $-19 | 2.8 |
| mom_align | 5m | 40 | 18% | $-26 | 4.1 |
| rsi_rev | 5m | 20 | 10% | $-41 | 3.4 |
| confluence | 5m | 40 | 12% | $-51 | 6.5 |

Headline (15m, NKD excluded): **308 trades, $-271 to $+109** over ~30 sessions — 0.45 trades per hour, $-9 to $+4 per session.
