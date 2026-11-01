# 73,296 configurations, and what survived them

**73,296 configurations** scored on causal fills (a decision uses bars before the session, resolution is close-based for limits, stop-first for stop entries), at one micro with costs inside every dollar.

| gate | configs |
|---|---:|
| tested | 73,296 |
| positive in both halves (pre-2023 and 2023+) | 10,723 |
| …and affordable: one stop <= $400 | 2,338 |
| …and beat random entries at p<=0.10 (top 300 only) | **294** |

Multiple-testing line for this many attempts: **t = 4.73**. A t-stat below that is what luck alone is expected to produce somewhere in a sweep this wide.

### Survivors: positive both halves, affordable, beat a coin flip (the multiple-testing line for 73,296 attempts is t = 4.73)

| sym | rule | gap/trend/day | bracket | OS trades | OS $/trade | $/session | t | risk $ | null $/trade | p |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| NQ=F | limit_low_long:3 | any/trend/mon | 0.25 ATR tp4 | 46 | +237.85 | +6.08 | +4.42 | $340 | +35.11 | 0.00 |
| NQ=F | limit_low_long:1 | against/trend/mon | 0.25 ATR tp4 | 42 | +237.03 | +6.77 | +3.72 | $340 | +35.77 | 0.00 |
| NQ=F | limit_low_long:2 | any/trend/mon | 0.25 ATR tp4 | 55 | +236.80 | +7.22 | +4.79 | $340 | +35.82 | 0.00 |
| NQ=F | limit_low_long:3 | any/trend/mon | 0.25 ATR tp3 | 46 | +211.24 | +5.36 | +4.43 | $340 | +26.79 | 0.00 |
| NQ=F | limit_low_long:2 | any/trend/mon | 0.25 ATR tp3 | 55 | +207.28 | +6.27 | +4.84 | $340 | +28.16 | 0.00 |
| NQ=F | limit_low_long:1 | against/trend/mon | 0.25 ATR tp3 | 42 | +204.17 | +5.82 | +3.64 | $340 | +26.66 | 0.00 |
| NQ=F | limit_low_long:1 | against/trend/mon | 0.25 ATR close | 42 | +183.39 | +3.50 | +2.34 | $340 | +64.00 | 0.00 |
| NQ=F | limit_low_long:3 | any/trend/mon | 0.25 ATR tp25 | 46 | +183.21 | +4.66 | +4.37 | $340 | +19.98 | 0.00 |
| NQ=F | limit_low_long:2 | any/trend/mon | 0.25 ATR tp25 | 55 | +179.50 | +5.42 | +4.82 | $340 | +21.53 | 0.00 |
| NQ=F | limit_low_long:1 | any/trend/mon | 0.25 ATR tp4 | 67 | +177.69 | +8.04 | +4.13 | $340 | +35.04 | 0.00 |
| NQ=F | nday_break_long:3 | with/trend/mon | 0.25 ATR close | 40 | +177.12 | +4.26 | +2.69 | $340 | +64.29 | 0.00 |
| NQ=F | nday_break_long:2 | with/trend/mon | 0.25 ATR close | 45 | +172.71 | +4.80 | +2.88 | $340 | +66.98 | 0.00 |
| NQ=F | limit_low_long:1 | against/trend/mon | 0.25 ATR tp25 | 42 | +171.42 | +4.93 | +3.48 | $340 | +19.88 | 0.00 |
| NQ=F | gap_fade_long:1 | against/trend/mon | 0.25 ATR close | 86 | +168.52 | +6.72 | +3.05 | $340 | +63.64 | 0.00 |
| NQ=F | gap_fade_long:1 | any/trend/mon | 0.25 ATR close | 88 | +165.03 | +6.62 | +3.04 | $340 | +63.23 | 0.00 |

### Best affordable by out-of-sample dollars per trade, before the luck gate

| sym | rule | gap/trend/day | bracket | OS trades | OS $/trade | $/session | t | risk $ | null $/trade | p |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| NQ=F | limit_low_long:3 | any/trend/mon | 0.25 ATR tp4 | 46 | +237.85 | +6.08 | +4.42 | $340 | +35.11 | 0.00 |
| NQ=F | limit_low_long:1 | against/trend/mon | 0.25 ATR tp4 | 42 | +237.03 | +6.77 | +3.72 | $340 | +35.77 | 0.00 |
| NQ=F | limit_low_long:2 | any/trend/mon | 0.25 ATR tp4 | 55 | +236.80 | +7.22 | +4.79 | $340 | +35.82 | 0.00 |
| NQ=F | limit_low_long:3 | any/trend/mon | 0.25 ATR tp3 | 46 | +211.24 | +5.36 | +4.43 | $340 | +26.79 | 0.00 |
| NQ=F | limit_low_long:2 | any/trend/mon | 0.25 ATR tp3 | 55 | +207.28 | +6.27 | +4.84 | $340 | +28.16 | 0.00 |
| NQ=F | limit_low_long:1 | against/trend/mon | 0.25 ATR tp3 | 42 | +204.17 | +5.82 | +3.64 | $340 | +26.66 | 0.00 |
| NQ=F | limit_low_long:1 | against/trend/mon | 0.25 ATR close | 42 | +183.39 | +3.50 | +2.34 | $340 | +64.00 | 0.00 |
| NQ=F | limit_low_long:3 | any/trend/mon | 0.25 ATR tp25 | 46 | +183.21 | +4.66 | +4.37 | $340 | +19.98 | 0.00 |
| NQ=F | limit_low_long:2 | any/trend/mon | 0.25 ATR tp25 | 55 | +179.50 | +5.42 | +4.82 | $340 | +21.53 | 0.00 |
| NQ=F | limit_low_long:1 | any/trend/mon | 0.25 ATR tp4 | 67 | +177.69 | +8.04 | +4.13 | $340 | +35.04 | 0.00 |

### The worst affordable configs, so the table is a population and not a brochure

| sym | rule | gap/trend/day | bracket | OS trades | OS $/trade | $/session | t | risk $ | null $/trade | p |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| ES=F | limit_high_short:21 | any/trend/tue | 0.5 ATR tp15 | 41 | +0.00 | +0.32 | +0.00 | $236 | — | — |
| ES=F | nday_break_long:34 | any/trend/fri | 0.25 ATR close | 43 | +0.06 | +0.49 | +0.00 | $118 | — | — |
| ES=F | nday_break_long:34 | any/trend/fri | 0.5 ATR close | 43 | +0.06 | +0.49 | +0.00 | $236 | — | — |

