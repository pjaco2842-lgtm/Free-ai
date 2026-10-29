# The 26,000-strategy test

Generated 2026-10-29T22:28Z · 28,350 configurations per market · one micro contract

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
| NQ=F | nday_break | 1 | 1.0A | tp2 | both | any | no | all | $+11,023 | $+41,451 | 979 | 56% | 96 | 75% | $+23,105 |
| NQ=F | nr_break | 1 | 1.0A | tp2 | both | any | no | all | $+11,023 | $+41,451 | 979 | 56% | 95 | 100% | $+23,105 |
| NQ=F | nday_fade | 5 | 0.75A | tp1 | both | any | no | all | $+14,499 | $+37,650 | 703 | 56% | 100 | 83% | $+20,752 |
| NQ=F | nday_fade | 5 | 0.5A | tp1 | both | any | no | all | $+8,134 | $+31,389 | 703 | 58% | 100 | 67% | $+19,045 |
| NQ=F | nr_break | 2 | 1.0A | tp2 | both | any | no | all | $+13,977 | $+31,247 | 490 | 58% | 100 | 100% | $+24,001 |
| NQ=F | nday_fade | 1 | 0.75A | tp1 | long | any | no | all | $+11,372 | $+31,093 | 561 | 58% | 100 | 80% | $+14,518 |
| NQ=F | nr_break | 2 | 1.0A | close | both | any | no | all | $+13,967 | $+29,927 | 490 | 58% | 99 | 100% | $+24,430 |
| NQ=F | nday_break | 1 | 1.0A | tp2 | both | with | no | all | $+8,619 | $+29,281 | 530 | 59% | 96 | 75% | $+21,644 |
| NQ=F | nr_break | 1 | 1.0A | tp2 | both | with | no | all | $+8,619 | $+29,281 | 530 | 59% | 95 | 100% | $+21,644 |
| NQ=F | nday_fade | 1 | 0.5A | tp1 | both | any | yes | all | $+5,720 | $+28,506 | 554 | 59% | 100 | 80% | $+6,476 |
| NQ=F | nr_break | 2 | 1.0A | tp1 | both | any | no | all | $+13,732 | $+28,220 | 490 | 58% | 95 | 100% | $+22,254 |
| NQ=F | nday_fade | 2 | 0.75A | tp1 | long | any | no | all | $+13,328 | $+28,121 | 421 | 58% | 100 | 83% | $+18,180 |
| NQ=F | nday_fade | 1 | 0.5A | tp1 | long | any | no | all | $+4,662 | $+27,810 | 561 | 59% | 100 | 80% | $+5,407 |
| NQ=F | nday_fade | 10 | 0.75A | tp1 | both | any | no | all | $+11,207 | $+27,401 | 538 | 55% | 100 | 83% | $+17,642 |
| NQ=F | nday_fade | 1 | 0.75A | tp1 | both | any | yes | all | $+11,401 | $+26,089 | 554 | 56% | 100 | 80% | $+5,202 |

## Buffer-safe challenger — win rate first

Same sweep, but only configs whose median stop is ≤ $320 — so a normal losing run fits inside the $1,000 buffer — ranked by out-of-sample win rate instead of net profit.

| market | family | n | stop | exit | dir | trades | win | net $ | median risk/stop |
|---|---|---|---|---|---|---|---|---|---|
| ES=F | nday_fade | 5 | 0.75A | tp1 | both | 711 | 56% | $+23,021 | $318 |

## What the whole population says

All 56,700 configurations, including the losers — otherwise this is just a list of winners. `positive` is the share with a positive test result.

**Exit style**

| value | configs | positive | median test $ |
|---|---|---|---|
| tp2 | 18900 | 32% | $-436 |
| close | 18900 | 30% | $-477 |
| tp1 | 18900 | 30% | $-595 |

**Stop distance**

| value | configs | positive | median test $ |
|---|---|---|---|
| 1.5 | 11340 | 41% | $-48 |
| 1.0 | 11340 | 40% | $-123 |
| 0.75 | 11340 | 33% | $-401 |
| 0.5 | 11340 | 27% | $-758 |
| 0.25 | 11340 | 12% | $-1,665 |

**Gap alignment**

| value | configs | positive | median test $ |
|---|---|---|---|
| with | 18900 | 30% | $-330 |
| against | 18900 | 29% | $-356 |
| any | 18900 | 32% | $-1,017 |

**Trend filter**

| value | configs | positive | median test $ |
|---|---|---|---|
| on | 28350 | 32% | $-360 |
| off | 28350 | 29% | $-695 |

**Day of week**

| value | configs | positive | median test $ |
|---|---|---|---|
| fri | 18900 | 32% | $-281 |
| mon | 18900 | 34% | $-294 |
| all | 18900 | 25% | $-2,082 |

**Family**

| value | configs | positive | median test $ |
|---|---|---|---|
| gap_cont | 8100 | 47% | $+0 |
| nday_fade | 8100 | 43% | $-190 |
| vol_expand_break | 1620 | 31% | $-305 |
| inside_break | 1620 | 34% | $-318 |
| trendday_fade | 1620 | 5% | $-489 |
| trendday_cont | 1620 | 22% | $-533 |
| nr_break | 8100 | 32% | $-594 |
| ma_pull | 8100 | 29% | $-602 |
| gap_fade | 8100 | 22% | $-782 |
| prevclose_break | 1620 | 39% | $-1,186 |
| nday_break | 8100 | 14% | $-3,309 |

## Year by year for the book

| market | rule | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NQ=F | nday_break-1 1.0A tp2 both | $+57 (171) | $-593 (201) | $+1,557 (198) | $+710 (191) | $+48 (192) | $+1,134 (182) | $+1,578 (204) | $-404 (183) | $-515 (191) | $+4,059 (195) | $+3,392 (190) | $-1,747 (196) | $+587 (206) | $+16,929 (192) | $+11,760 (194) | $+13,923 (191) | $+10,904 (187) | $+12,201 (167) |
| NQ=F | nr_break-2 1.0A tp2 both | $+485 (85) | $+1 (107) | $+1,794 (99) | $+761 (90) | $+328 (97) | $+1,231 (91) | $+764 (102) | $+38 (87) | $+308 (100) | $+4,339 (101) | $+3,927 (99) | $+290 (104) | $+504 (109) | $+9,575 (83) | $+6,293 (97) | $+14,585 (97) | $+13,468 (97) | $+10,533 (77) |

## Replay check

The vectorised sweep and the scalar replay the paper trader uses must agree.

| market | sweep | scalar replay | match |
|---|---|---|---|
| NQ=F | $+75,580 | $+75,580 | yes |
| NQ=F | $+69,225 | $+69,225 | yes |

3,489 configurations were positive in both halves out of 56,700 tested. With this many trials, some win by chance; the plateau and luck gates exist to throw those out, and the number that survives them is the honest answer to "how many real edges are in here".
