# The 26,000-strategy test

Generated 2026-10-29T20:28Z · 28,350 configurations per market · one micro contract

Train ≤ 2019 · test 2020-2024 · recent 2025 onward.

Fill model: a stop at a derived level fills at the level, or at the open when the session gapped through it; stop intraday from the previous session's ATR; exit at the close or a fixed R target; $1.24/side plus one tick of slippage per side. If a session would fill both a long and a short order, the day is skipped — the daily bar cannot say which filled first.

## Gates

| gate | rule | why |
|---|---|---|
| unseen years | positive in train AND test | two good years are not an edge |
| sample | ≥100 train trades, ≥60 test trades | a handful of trades is noise |
| plateau | ≥4 of 6 parameter neighbours positive | 40 but not 39 is a coincidence |
| regime | 2025 onward not negative | old edges go flat |
| luck | beats the 95th percentile of 500 random fills on the same days, same side, same stop | a coin flip with different rules is not a coin flip |

## Survivors

| market | family | n | stop | exit | dir | gap | trend | dow | train $ | test $ | trades | win | luck pct | plateau | 2025+ $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NQ=F | prevclose_break | None | 1.0A | tp2 | both | any | no | all | $+18,934 | $+59,874 | 153 | 93% | 100 | 100% | $+33,256 |
| NQ=F | prevclose_break | None | 1.5A | tp1 | both | any | no | all | $+19,042 | $+59,618 | 153 | 93% | 100 | 100% | $+31,759 |
| NQ=F | prevclose_break | None | 0.75A | tp2 | both | any | no | all | $+19,018 | $+59,066 | 153 | 93% | 100 | 100% | $+31,239 |
| NQ=F | prevclose_break | None | 1.5A | tp2 | both | any | no | all | $+19,145 | $+59,056 | 153 | 93% | 100 | 100% | $+33,698 |
| NQ=F | prevclose_break | None | 1.0A | close | both | any | no | all | $+19,123 | $+58,657 | 153 | 93% | 100 | 100% | $+33,580 |
| NQ=F | prevclose_break | None | 1.5A | close | both | any | no | all | $+19,104 | $+58,657 | 153 | 93% | 100 | 100% | $+33,580 |
| NQ=F | prevclose_break | None | 0.75A | close | both | any | no | all | $+19,080 | $+58,105 | 153 | 93% | 100 | 100% | $+33,060 |
| NQ=F | prevclose_break | None | 0.5A | close | both | any | no | all | $+18,945 | $+57,917 | 153 | 92% | 100 | 100% | $+33,318 |
| NQ=F | prevclose_break | None | 1.0A | tp1 | both | any | no | all | $+18,380 | $+53,726 | 153 | 93% | 100 | 100% | $+30,168 |
| NQ=F | prevclose_break | None | 0.25A | close | both | any | no | all | $+16,526 | $+53,190 | 153 | 86% | 100 | 100% | $+30,504 |
| NQ=F | prevclose_break | None | 0.5A | tp2 | both | any | no | all | $+18,203 | $+52,987 | 153 | 92% | 100 | 100% | $+29,906 |
| NQ=F | prevclose_break | None | 0.75A | tp1 | both | any | no | all | $+16,863 | $+48,658 | 153 | 93% | 100 | 100% | $+26,049 |
| NQ=F | nday_break | 1 | 1.0A | tp2 | both | any | no | all | $+13,151 | $+45,481 | 969 | 56% | 98 | 75% | $+29,279 |
| NQ=F | nr_break | 1 | 1.0A | tp2 | both | any | no | all | $+13,151 | $+45,481 | 969 | 56% | 96 | 100% | $+29,279 |
| NQ=F | nday_break | 1 | 1.0A | close | both | any | no | all | $+13,465 | $+42,657 | 969 | 56% | 96 | 75% | $+29,385 |

## What the whole population says

All 56,700 configurations, including the losers — otherwise this is just a list of winners. `positive` is the share with a positive test result.

**Exit style**

| value | configs | positive | median test $ |
|---|---|---|---|
| tp2 | 18900 | 32% | $-422 |
| close | 18900 | 30% | $-467 |
| tp1 | 18900 | 30% | $-575 |

**Stop distance**

| value | configs | positive | median test $ |
|---|---|---|---|
| 1.5 | 11340 | 41% | $-39 |
| 1.0 | 11340 | 40% | $-110 |
| 0.75 | 11340 | 33% | $-379 |
| 0.5 | 11340 | 27% | $-728 |
| 0.25 | 11340 | 13% | $-1,650 |

**Gap alignment**

| value | configs | positive | median test $ |
|---|---|---|---|
| with | 18900 | 30% | $-325 |
| against | 18900 | 30% | $-340 |
| any | 18900 | 32% | $-1,005 |

**Trend filter**

| value | configs | positive | median test $ |
|---|---|---|---|
| on | 28350 | 32% | $-360 |
| off | 28350 | 30% | $-667 |

**Day of week**

| value | configs | positive | median test $ |
|---|---|---|---|
| fri | 18900 | 32% | $-272 |
| mon | 18900 | 35% | $-281 |
| all | 18900 | 26% | $-2,044 |

**Family**

| value | configs | positive | median test $ |
|---|---|---|---|
| gap_cont | 8100 | 47% | $+0 |
| nday_fade | 8100 | 42% | $-192 |
| vol_expand_break | 1620 | 31% | $-305 |
| inside_break | 1620 | 34% | $-309 |
| prevclose_break | 1620 | 47% | $-316 |
| trendday_fade | 1620 | 5% | $-489 |
| trendday_cont | 1620 | 22% | $-533 |
| nr_break | 8100 | 33% | $-579 |
| ma_pull | 8100 | 29% | $-602 |
| gap_fade | 8100 | 22% | $-782 |
| nday_break | 8100 | 14% | $-3,298 |

## Year by year for the book

| market | rule | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NQ=F | prevclose_break 1.0A tp2 both | $+556 (12) | $+590 (14) | $+1,445 (22) | $+778 (18) | $+1,371 (37) | $+1,436 (25) | $+2,389 (26) | $+915 (13) | $+1,039 (17) | $+3,921 (22) | $+4,496 (40) | $+14,464 (39) | $+7,382 (21) | $+11,761 (27) | $+10,122 (31) | $+16,146 (35) | $+16,373 (33) | $+16,883 (25) |
| NQ=F | prevclose_break 1.5A tp1 both | $+551 (12) | $+611 (14) | $+1,381 (22) | $+832 (18) | $+1,374 (37) | $+1,454 (25) | $+2,294 (26) | $+940 (13) | $+1,004 (17) | $+3,910 (22) | $+4,692 (40) | $+14,491 (39) | $+7,103 (21) | $+11,799 (27) | $+10,465 (31) | $+15,759 (35) | $+15,855 (33) | $+15,904 (25) |
| NQ=F | prevclose_break 0.75A tp2 both | $+551 (12) | $+639 (14) | $+1,381 (22) | $+832 (18) | $+1,322 (37) | $+1,454 (25) | $+2,294 (26) | $+940 (13) | $+1,004 (17) | $+3,910 (22) | $+4,692 (40) | $+13,939 (39) | $+7,103 (21) | $+11,799 (27) | $+10,465 (31) | $+15,759 (35) | $+15,617 (33) | $+15,622 (25) |

## Replay check

The vectorised sweep and the scalar replay the paper trader uses must agree.

| market | sweep | scalar replay | match |
|---|---|---|---|
| NQ=F | $+112,064 | $+112,064 | yes |
| NQ=F | $+110,420 | $+110,420 | yes |
| NQ=F | $+109,324 | $+109,324 | yes |

3,465 configurations were positive in both halves out of 56,700 tested. With this many trials, some win by chance; the plateau and luck gates exist to throw those out, and the number that survives them is the honest answer to "how many real edges are in here".
