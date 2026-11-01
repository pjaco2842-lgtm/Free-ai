# Wide causal search — ES=F

2515 sessions, 2016-11-01 to 2026-10-30. One micro ($5/pt), $4.98 round trip assumed on every trade.
Decision at bar i sees bars <= i-1; resolution is close-based; the split is in-sample (to 2022-12-31) and out-of-sample (2023-01-01 on).

**3584 configurations tested.** With that many, the best of a pure-luck search tends to reach |t| ~ 4.05, so the best t here is **4.25**. It clears the line.

**Drift:** the index moved **+98%** across the out-of-sample window, and a long trade held for that long collects it. Both dollar columns are therefore also reported as **alpha** — dollars minus what simply being positioned that way over the same sessions paid.

**Null control:** random entries through the same exit grid reached **71% win rate**, **$+95.50/trade** and **$+79.35 alpha** out-of-sample. A rule has to beat that row, not zero.

## Survives both halves (positive IS and OS, >=60% OS win)

| rule | stop | target | hold | IS n | IS win | OS n | OS win | OS $/tr | IS alpha | OS alpha | OS alpha t | tr/sess | $/sess |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pd_low n=2 gap=with | 1.5A | close | 5 | 183 | 56% | 153 | 60% | $+148.26 | $+32.94 | $+37.69 | +4.13 | 0.066 | $+2.49 |
| pd_low n=5 gap=with | 0.5A | close | 2 | 109 | 51% | 91 | 62% | $+116.14 | $+35.02 | $+32.18 | +3.18 | 0.039 | $+1.27 |
| pullback n=3 | 0.5A | close | 2 | 57 | 56% | 72 | 61% | $+114.06 | $+53.64 | $+31.38 | +3.48 | 0.031 | $+0.98 |
| pullback n=3 | 0.75A | close | 3 | 57 | 58% | 72 | 61% | $+167.80 | $+72.44 | $+29.69 | +2.91 | 0.031 | $+0.92 |
| pd_low n=3 gap=with | 1.5A | close | 5 | 155 | 54% | 125 | 62% | $+168.28 | $+34.01 | $+29.58 | +3.52 | 0.054 | $+1.60 |
| nr_break n=7 | 1.5A | close | 5 | 143 | 57% | 100 | 61% | $+59.94 | $+17.04 | $+29.20 | +2.96 | 0.043 | $+1.26 |
| nr_break n=7 | 1.5A | 1.5R | 5 | 143 | 57% | 100 | 61% | $+53.60 | $+16.48 | $+28.10 | +2.83 | 0.043 | $+1.21 |
| nr_break n=5 | 1.5A | close | 5 | 191 | 58% | 133 | 62% | $+47.68 | $+14.31 | $+24.78 | +3.20 | 0.057 | $+1.42 |
| nr_break n=5 | 1.5A | 1.5R | 5 | 191 | 58% | 133 | 62% | $+42.92 | $+13.48 | $+23.95 | +3.07 | 0.057 | $+1.38 |
| pd_low n=5 gap=with | 1.5A | close | 5 | 109 | 52% | 91 | 63% | $+206.57 | $+41.87 | $+22.98 | +2.90 | 0.039 | $+0.90 |
| pullback n=2 | 1.0A | close | 3 | 156 | 54% | 178 | 61% | $+115.15 | $+45.11 | $+22.32 | +3.63 | 0.077 | $+1.72 |
| rsi2 side=long thr=2 | 0.75A | close | 2 | 163 | 52% | 186 | 60% | $+83.03 | $+40.90 | $+18.59 | +4.25 | 0.080 | $+1.49 |
| pullback n=2 | 1.5A | close | 5 | 156 | 60% | 178 | 61% | $+143.64 | $+36.06 | $+18.56 | +2.94 | 0.077 | $+1.43 |
| nr_break n=7 | 1.5A | 1.0R | 5 | 143 | 59% | 100 | 61% | $+41.88 | $+10.50 | $+18.31 | +1.62 | 0.043 | $+0.79 |
| pullback n=2 | 0.75A | close | 2 | 156 | 53% | 178 | 61% | $+87.96 | $+42.23 | $+18.31 | +4.16 | 0.077 | $+1.41 |

## Everything at 70%+ out-of-sample win rate, ranked by alpha

| rule | stop | target | hold | IS n | IS win | OS n | OS win | OS $/tr | IS alpha | OS alpha | OS alpha t | tr/sess | $/sess |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| nr_break n=5 | 0.75A | 0.25R | 5 | 191 | 73% | 133 | 71% | $-35.23 | $-18.94 | $-35.56 | -2.14 | 0.057 | $-2.04 |
| nr_break n=7 | 0.75A | 0.25R | 5 | 143 | 73% | 100 | 74% | $-17.80 | $-25.67 | $-41.18 | -2.13 | 0.043 | $-1.78 |
| nr_break n=7 | 0.5A | 0.25R | 5 | 143 | 71% | 100 | 71% | $-23.04 | $-30.47 | $-45.72 | -2.74 | 0.043 | $-1.97 |
| pd_low n=1 gap=with | 1.5A | 0.33R | 5 | 249 | 69% | 204 | 71% | $+6.07 | $-43.86 | $-58.23 | -5.14 | 0.088 | $-5.13 |
| pullback n=3 | 0.75A | 0.75R | 5 | 57 | 63% | 72 | 71% | $+70.71 | $+10.54 | $-60.18 | -2.91 | 0.031 | $-1.87 |
| pd_low n=3 gap=with | 0.75A | 0.5R | 2 | 155 | 61% | 125 | 70% | $+16.75 | $-23.11 | $-63.13 | -4.30 | 0.054 | $-3.41 |
| pd_low n=5 gap=with | 1.5A | 0.33R | 2 | 109 | 59% | 91 | 70% | $+30.86 | $-32.41 | $-63.63 | -4.65 | 0.039 | $-2.50 |
| pd_low n=2 gap=with | 0.75A | 0.5R | 5 | 183 | 68% | 153 | 72% | $+16.10 | $-24.28 | $-63.77 | -4.05 | 0.066 | $-4.21 |
| pd_low n=1 gap=with | 1.0A | 0.33R | 5 | 249 | 71% | 204 | 73% | $-9.59 | $-34.21 | $-64.93 | -4.92 | 0.088 | $-5.72 |
| pd_low n=5 gap=with | 0.75A | 0.5R | 2 | 109 | 56% | 91 | 70% | $+23.33 | $-22.44 | $-65.35 | -3.81 | 0.039 | $-2.57 |

### What the best surviving line implies

`pd_low n=2 gap=with`, 1.5 ATR stop, close exit, 5-session hold: **$+2.49 per session at one micro, $+4.98 at two** (costs double with size, so this is close).
At $+4.98 a session, +$1,250 takes **251 sessions**.
