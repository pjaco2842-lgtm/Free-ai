# Three-session evaluation window on the live book

Rule: prior-session-low buy limit, any gap, 0.5 ATR stop, 2R target, one trade maximum per
session, close-only resolution. Every rolling 3-session window of the 2,494-session ES sample
(2016-11-01 to 2026-10-30). Windows overlap, so the counts are not independent draws.

| window | n | mean | median | p05 | p25 | p75 | p95 | ends negative | >=$500 | >=$1,250 | worst | best |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 micro, all sessions | 2492 | $+31 | $+0 | $-229 | $-30 | $+89 | $+348 | 31.6% | 2.25% | 0.04% | $-995 | $+1377 |
| 2 micros, all sessions | 2492 | $+61 | $+0 | $-457 | $-60 | $+178 | $+695 | 31.6% | 9.03% | 0.96% | $-1990 | $+2753 |
| 1 micro, 2023+ | 962 | $+45 | $+0 | $-253 | $-72 | $+143 | $+429 | 34.5% | 3.95% | 0.10% | $-995 | $+1377 |
| 2 micros, 2023+ | 962 | $+89 | $+0 | $-507 | $-145 | $+285 | $+858 | 34.5% | 14.66% | 1.98% | $-1990 | $+2753 |

Worst single session at one micro: $-544. Three sessions cannot breach the
$1,000 floor unless every one of them is at its measured worst or worse, so the binding risk
in a 3-day window is not the floor — it is finishing red and walking away thinking the rule failed.

