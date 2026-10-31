# The wide sweep

> **RETRACTED AS VALIDATION — audit 2026-10-31:** This historical report uses
> entry/exit ordering and random-fill assumptions that can produce impossible or
> biased results; account timing and consistency calculations are also incorrect.
> Its selection, pass rates, survivor claims and comparisons are not reliable.
> See `trading/RESEARCH-LOG.md` (audit) and `trading/desk/audit-search.md`.

Generated 2026-10-31T04:50Z · **57,456 configurations per market · 287,280 in total** · one micro contract · five markets

Markets: ES=F (MES, $5/pt), NQ=F (MNQ, $2/pt), GC=F (MGC, $10/pt), CL=F (MCL, $100/pt), NKD=F (NKD, $5/pt). Data 2009 → today, daily bars from Yahoo.

`parity OK — 2440 trades identical to the live replay` — the scalar replay that the paper trader uses reproduces the older replay trade-for-trade, so this sweep is measuring the same fills the desk trades.

## The space, exactly

| axis | values |
|---|---|
| rule families | 18: nday_break, nday_fade, nr_break, streak_break, inside_break, outside_break, vol_expand_break, gap_cont, gap_fade, trendday_cont, trendday_fade, ma_pull, prevclose_break, prevclose_fade, mon_gap_fade, pin_break, body_cont, model |
| lookbacks | [1, 2, 3, 5, 7, 10, 20] (per family, where it takes one) |
| rule variants | 38 (lookback × family) |
| stops | 0.25 ATR, 0.5 ATR, 0.75 ATR, 1.0 ATR, 1.5 ATR, 2.0 ATR, 2.5 ATR |
| exits | close, tp05 (0.5R), tp1 (1.0R), tp2 (2.0R) |
| filters | gap ['any', 'with', 'against'] × day ['all', 'mon', 'fri'] × 50-day trend ['off', 'on'] × direction ['both', 'long', 'short'] = 54 |
| per market | 38 × 7 × 4 × 54 = **57,456** |
| in total | **287,280** |

## Gates, and how many made it through each

| gate | rule | survivors |
|---|---|---|
| start | — | 287,280 |
| unseen years | positive in 2009-2019 **and** 2020-2024, ≥150 train and ≥100 test trades | 9,629 |
| plateau | ≥4 of 6 parameter neighbours positive out of sample | 289 |
| regime | 2025-2026 not negative | 289 |
| luck | beats the 95th percentile of 500 random fills on the same days, same side, same stop, same exit | 289 |
| sample | ≥100 trades across all history | 89 |

At 120 candidates per market through the expensive gates, **289** survived. Pure chance at a 95th-percentile luck gate would let about **30** through. That is above chance, which is a reason to test forward, not a proof.

## The book the sweep chose

Ranked by **how often the $25,000 evaluation reaches +$1,250 inside three sessions with the 40% consistency rule intact**, not by net profit.

| market | rule | stop | exit | trades | win | $/trade | pass% | with consistency | ≤3 sessions | ≤5 | breached | median sessions | risk/session |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ES=F | nday_fade-1 | 1.0A | tp05 | 204 | 80% | $+95 | 91% | 84% | 0% | 5% | 3% | 14 | $413 |

**Book, 2023-01-01 onward** (the era whose prices this account faces): 204 trades, 80% win, $+94.58/trade, worst drawdown $-1,086. Walked from all 204 starting trades: **pass 91%**, **with consistency 84%**, **inside 3 sessions 0.0%**, inside 5 5%, inside 10 21%, inside 15 57%, breached 3%, median 14 sessions to the target, median consistency 16%.

Full history (2009 onward), for reference: pass 98%, with consistency 96%, median 37 sessions, breach 1%. The older half of that history was traded at a fifth of today's index prices, so it is the 2023-01-01+ row above that describes this account.

## The three-session question, answered with the numbers

$1,250 in three sessions is $417 a session, and one micro has to do it. Of the book's own history, the target was reached inside three sessions from **0.0%** of starting points with the consistency rule intact, and the floor was lost from **3%** of attempts that finished.

That is the honest trade: three sessions is a sprint that has to be paid for with risk, and on a $1,000 buffer the payment is the account. Read the row above as odds, not as a target to be aimed at.

## What the whole population says (losers included)

**family**

| value | configs | positive out of sample | median test $ |
|---|---|---|---|
| gap_cont | 7,560 | 30% | $+0 |
| trendday_fade | 7,560 | 8% | $+0 |
| model | 7,560 | 0% | $+0 |
| nday_fade | 52,920 | 47% | $-92 |
| mon_gap_fade | 7,560 | 23% | $-113 |
| vol_expand_break | 7,560 | 40% | $-169 |
| inside_break | 7,560 | 43% | $-185 |
| outside_break | 7,560 | 29% | $-358 |
| nr_break | 52,920 | 39% | $-361 |
| body_cont | 7,560 | 33% | $-364 |
| trendday_cont | 7,560 | 31% | $-399 |
| streak_break | 22,680 | 31% | $-558 |
| ma_pull | 7,560 | 28% | $-857 |
| pin_break | 7,560 | 24% | $-1,055 |
| gap_fade | 7,560 | 15% | $-1,507 |
| prevclose_break | 7,560 | 32% | $-1,870 |
| prevclose_fade | 7,560 | 26% | $-2,350 |
| nday_break | 52,920 | 23% | $-2,569 |

**stop**

| value | configs | positive out of sample | median test $ |
|---|---|---|---|
| 2.0 | 41,040 | 44% | $+0 |
| 2.5 | 41,040 | 44% | $-0 |
| 1.5 | 41,040 | 43% | $-29 |
| 1.0 | 41,040 | 37% | $-279 |
| 0.75 | 41,040 | 29% | $-645 |
| 0.5 | 41,040 | 20% | $-1,359 |
| 0.25 | 41,040 | 7% | $-2,490 |

**exit**

| value | configs | positive out of sample | median test $ |
|---|---|---|---|
| tp1 | 71,820 | 33% | $-445 |
| tp05 | 71,820 | 34% | $-450 |
| tp2 | 71,820 | 32% | $-470 |
| close | 71,820 | 30% | $-544 |

**gap**

| value | configs | positive out of sample | median test $ |
|---|---|---|---|
| against | 95,760 | 33% | $-299 |
| with | 95,760 | 32% | $-411 |
| any | 95,760 | 31% | $-848 |

**dow**

| value | configs | positive out of sample | median test $ |
|---|---|---|---|
| fri | 95,760 | 34% | $-267 |
| mon | 95,760 | 35% | $-284 |
| all | 95,760 | 28% | $-1,629 |

**trend**

| value | configs | positive out of sample | median test $ |
|---|---|---|---|
| on | 143,640 | 32% | $-378 |
| off | 143,640 | 33% | $-613 |

**dir**

| value | configs | positive out of sample | median test $ |
|---|---|---|---|
| long | 95,760 | 36% | $-248 |
| both | 95,760 | 35% | $-599 |
| short | 95,760 | 25% | $-647 |

## Top of the pile, whatever the book took

| market | rule | trades | win | $/trade | pass% | cons% | ≤3 | luck | plateau | 2025+ $ |
|---|---|---|---|---|---|---|---|---|---|---|
| ES=F | nday_fade-1 1.0A tp05 gapwith long | 204 | 80% | $+95 | 91% | 84% | 0% | 100 | 100% | $+9,878 |
| ES=F | nday_fade-2 1.0A tp05 long | 329 | 78% | $+76 | 90% | 90% | 0% | 100 | 83% | $+15,264 |
| ES=F | nday_fade-3 1.0A tp05 long | 268 | 78% | $+74 | 85% | 85% | 0% | 100 | 83% | $+12,643 |
| ES=F | nday_fade-5 1.0A tp05 gapwith | 267 | 70% | $+50 | 82% | 80% | 0% | 100 | 83% | $+7,148 |
| ES=F | nday_fade-1 1.0A tp05 long | 443 | 75% | $+65 | 88% | 87% | 0% | 100 | 80% | $+17,093 |
| ES=F | nday_fade-1 1.0A tp05 trend | 432 | 73% | $+71 | 95% | 92% | 0% | 100 | 80% | $+19,350 |
| ES=F | nday_fade-2 0.75A tp1 long | 329 | 61% | $+52 | 75% | 75% | 1% | 100 | 100% | $+8,186 |
| ES=F | nday_fade-3 1.0A tp05 gapwith | 322 | 70% | $+49 | 88% | 85% | 0% | 100 | 83% | $+7,999 |
| ES=F | nday_fade-2 1.0A tp05 gapwith | 360 | 68% | $+46 | 81% | 79% | 0% | 100 | 83% | $+8,578 |
| ES=F | nday_fade-7 1.0A tp05 | 460 | 70% | $+50 | 85% | 85% | 0% | 100 | 83% | $+14,954 |
| ES=F | nday_fade-5 1.0A tp05 | 525 | 70% | $+53 | 88% | 87% | 0% | 100 | 83% | $+18,122 |
| ES=F | nday_fade-3 1.0A tp05 | 636 | 69% | $+50 | 81% | 81% | 0% | 100 | 83% | $+20,739 |
| ES=F | nday_fade-7 1.0A tp05 gapwith | 231 | 71% | $+47 | 90% | 87% | 0% | 100 | 83% | $+5,043 |
| ES=F | nday_fade-10 1.0A tp05 | 397 | 69% | $+44 | 80% | 79% | 0% | 100 | 83% | $+9,938 |
| ES=F | nday_fade-2 1.0A tp05 | 703 | 66% | $+40 | 83% | 82% | 0% | 100 | 83% | $+19,043 |

## What this cannot see

Daily bars cannot order the events inside a session. When the stop and the target are both touched the fill code takes the stop, which is the pessimistic reading and the right one, but the true sequence could only be worse in ways the open already models. Slippage is one tick per side. A session that fills both a long and a short order is skipped unless the open already says which side, because the bar cannot say which filled first — taking only the good half of those days is exactly the look-ahead that once produced a 93% win rate on the prior-close rule.

The luck gate is a 95th-percentile threshold, so it rejects 95% of strategies *with no edge* and still lets through 5%. With this many trials, one survivor is not evidence; a survivor that also trades well forward is.

Contract sizes matter more than win rates here: ES=F one ATR = $422, NQ=F one ATR = $1,009, GC=F one ATR = $1,074, CL=F one ATR = $413, NKD=F one ATR = $7,712 at today's volatility. NKD is a $5/point contract on an index that moves hundreds of points a day — at 25K only its smallest stops are even reachable.
