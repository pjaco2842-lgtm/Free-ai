# Wide causal search — NQ=F

2515 sessions, 2016-11-01 to 2026-10-30. One micro ($2/pt), $3.48 round trip assumed on every trade.
Decision at bar i sees bars <= i-1; resolution is close-based; the split is in-sample (to 2022-12-31) and out-of-sample (2023-01-01 on).

**3584 configurations tested.** With that many, the best of a pure-luck search tends to reach |t| ~ 4.05, so the best t here is **4.79**. It clears the line.

**Drift:** the index moved **+161%** across the out-of-sample window, and a long trade held for that long collects it. Both dollar columns are therefore also reported as **alpha** — dollars minus what simply being positioned that way over the same sessions paid.

**Null control:** random entries through the same exit grid reached **69% win rate**, **$+222.74/trade** and **$+173.96 alpha** out-of-sample. A rule has to beat that row, not zero.

## Survives both halves (positive IS and OS, >=60% OS win)

| rule | stop | target | hold | IS n | IS win | OS n | OS win | OS $/tr | IS alpha | OS alpha | OS alpha t | tr/sess | $/sess |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| hammer | 0.75A | close | 2 | 69 | 45% | 46 | 61% | $+137.35 | $+71.54 | $+96.16 | +2.54 | 0.020 | $+1.91 |
| hammer | 0.75A | 1.5R | 2 | 69 | 45% | 46 | 61% | $+131.98 | $+69.80 | $+91.70 | +2.40 | 0.020 | $+1.82 |
| rsi2 side=long thr=5 | 1.5A | close | 5 | 172 | 57% | 183 | 60% | $+245.21 | $+60.95 | $+80.40 | +4.79 | 0.079 | $+6.36 |
| pullback n=2 | 1.5A | close | 5 | 160 | 58% | 168 | 62% | $+244.53 | $+59.16 | $+80.31 | +4.56 | 0.073 | $+5.83 |
| rsi2 side=long thr=2 | 1.5A | close | 5 | 162 | 57% | 177 | 61% | $+239.36 | $+58.39 | $+79.04 | +4.66 | 0.076 | $+6.04 |
| rsi2 side=long thr=10 | 1.5A | close | 5 | 188 | 57% | 199 | 62% | $+275.96 | $+60.36 | $+73.66 | +4.75 | 0.086 | $+6.33 |
| pullback n=3 | 1.5A | close | 5 | 59 | 53% | 68 | 62% | $+257.60 | $+88.54 | $+70.75 | +3.56 | 0.029 | $+2.08 |
| hammer | 0.75A | 1.0R | 2 | 69 | 46% | 46 | 61% | $+109.44 | $+55.72 | $+61.38 | +1.50 | 0.020 | $+1.22 |
| hammer | 1.0A | 1.5R | 2 | 69 | 46% | 46 | 61% | $+117.87 | $+50.86 | $+59.05 | +1.90 | 0.020 | $+1.17 |
| hammer | 1.0A | close | 2 | 69 | 46% | 46 | 61% | $+117.87 | $+50.95 | $+59.05 | +1.90 | 0.020 | $+1.17 |
| inside_break | 1.5A | close | 5 | 99 | 58% | 71 | 62% | $+215.30 | $+33.91 | $+53.33 | +2.87 | 0.031 | $+1.64 |
| engulf side=long | 0.75A | close | 2 | 76 | 55% | 53 | 62% | $+143.80 | $+44.20 | $+52.37 | +2.63 | 0.023 | $+1.20 |
| hammer | 1.0A | 1.0R | 2 | 69 | 46% | 46 | 61% | $+106.69 | $+46.59 | $+48.78 | +1.52 | 0.020 | $+0.97 |
| hammer | 1.5A | 1.0R | 2 | 69 | 48% | 46 | 61% | $+83.16 | $+23.37 | $+43.76 | +1.78 | 0.020 | $+0.87 |
| hammer | 1.5A | 1.5R | 2 | 69 | 48% | 46 | 61% | $+83.16 | $+23.47 | $+43.76 | +1.78 | 0.020 | $+0.87 |

## Everything at 70%+ out-of-sample win rate, ranked by alpha

| rule | stop | target | hold | IS n | IS win | OS n | OS win | OS $/tr | IS alpha | OS alpha | OS alpha t | tr/sess | $/sess |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pullback n=2 | 1.5A | 0.5R | 5 | 160 | 62% | 168 | 70% | $+55.01 | $-14.40 | $-60.30 | -2.26 | 0.073 | $-4.38 |
| inside_break | 1.0A | 0.33R | 5 | 99 | 69% | 71 | 70% | $-64.07 | $-22.87 | $-70.08 | -1.81 | 0.031 | $-2.15 |
| inside_break | 1.0A | 0.25R | 5 | 99 | 71% | 71 | 70% | $-100.01 | $-36.59 | $-84.08 | -2.10 | 0.031 | $-2.58 |
| inside_break | 1.5A | 0.33R | 5 | 99 | 70% | 71 | 70% | $-22.41 | $-42.08 | $-98.31 | -2.89 | 0.031 | $-3.02 |
| inside_break | 1.5A | 0.25R | 5 | 99 | 73% | 71 | 73% | $-57.96 | $-51.87 | $-101.47 | -2.97 | 0.031 | $-3.11 |
| pd_low n=2 gap=any | 1.5A | 0.33R | 5 | 433 | 67% | 320 | 70% | $+0.77 | $-68.71 | $-115.51 | -6.20 | 0.138 | $-15.97 |
| rsi2 side=long thr=5 | 1.5A | 0.33R | 5 | 172 | 65% | 183 | 71% | $-22.58 | $-20.99 | $-115.95 | -4.24 | 0.079 | $-9.17 |
| rsi2 side=long thr=2 | 1.5A | 0.33R | 5 | 162 | 65% | 177 | 72% | $-18.36 | $-24.07 | $-118.73 | -4.29 | 0.076 | $-9.08 |
| pd_low n=3 gap=with | 0.5A | 0.33R | 3 | 160 | 67% | 110 | 70% | $-36.25 | $-92.60 | $-119.56 | -3.18 | 0.048 | $-5.68 |
| pd_low n=3 gap=with | 0.5A | 0.25R | 5 | 160 | 71% | 110 | 70% | $-54.36 | $-95.52 | $-120.36 | -3.22 | 0.048 | $-5.72 |

### What the best surviving line implies

`hammer`, 0.75 ATR stop, close exit, 2-session hold: **$+1.91 per session at one micro, $+3.82 at two** (costs double with size, so this is close).
At $+3.82 a session, +$1,250 takes **327 sessions**.
