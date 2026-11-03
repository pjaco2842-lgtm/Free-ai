# The causal paper desk

Book `es-pdlow1-anygap-05atr-tp2` — 1 micro, ES=F, limit_low-1, gap:any, long only, 0.5 ATR stop, tp2 target.

> **Paper only.** The evidence behind this book is unvalidated: `RESEARCH-LOG.md` (o) showed the old fill model could count a target that traded before the dip. This runner uses the causal resolution instead, so the first 100 settled trades here are the test, not a formality.

## Next session

**BUY LIMIT 1 MES @ 7606.75** — for the session of 2026-11-04 (levels from the completed bar 2026-11-03).

| field | value |
|---|---|
| entry (buy limit) | **7606.75** |
| condition | no gap condition |
| distance from last close | 7617.50 → -0.14% |
| stop | **7559.37** (0.5 × ATR, ATR 94.77) |
| target | **7701.52** (2.0R) |
| risk if stopped | **$237** = 24% of the $1000 buffer |
| buffer left after one stop | $763 |

If the market gaps below the level, the limit fills at the open (better price); one tick of entry and exit slippage and $1.24 per side are charged on settlement.

## Account

- balance **$24,504.80** (-495.20 of the $1,250 target, -40%)
- end-of-day floor $24,000.00 — room $505
- largest day $245 = 0% of profit (limit 40%)
- status: **running**, 17 settled trades

## Pace against your rubric

| session | target | actual | cumulative |
|---|---:|---:|---:|
| 2026-09-16 | $500 | $-106.23 | $-106.23 |
| 2026-09-23 | $500 | $-194.98 | $-301.21 |
| 2026-09-24 | $250 | $+36.27 | $-264.94 |
| 2026-09-28 | — | $-13.73 | $-278.67 |
| 2026-09-29 | — | $+25.02 | $-253.65 |
| 2026-09-30 | — | $+11.27 | $-242.38 |
| 2026-10-01 | — | $+87.52 | $-154.86 |
| 2026-10-07 | — | $+113.77 | $-41.09 |
| 2026-10-08 | — | $-2.48 | $-43.57 |
| 2026-10-13 | — | $+42.52 | $-1.05 |
| 2026-10-14 | — | $-177.17 | $-178.22 |
| 2026-10-15 | — | $+245.02 | $+66.80 |
| 2026-10-16 | — | $-69.98 | $-3.18 |
| 2026-10-22 | — | $-204.13 | $-207.31 |
| 2026-10-23 | — | $-89.98 | $-297.29 |
| 2026-10-29 | — | $+15.02 | $-282.27 |
| 2026-10-30 | — | $-212.93 | $-495.20 |

- best session $+245.02, average $-29.13/session
- your rubric: **rework it** (>= $500 keep, >= $200 a day keep and tweak, below that rework)
- stand-down at -$350/session: not hit

## Ledger

| date | entry | stop | target | risk | result | $ |
|---|---:|---:|---:|---:|---|---:|
| 2026-09-16 | 7576.75 | 7542.71 | 7644.84 | $170 | loss | $-106.23 |
| 2026-09-23 | 7810.50 | 7769.77 | 7891.96 | $204 | loss | $-194.98 |
| 2026-09-24 | 7758.75 | 7717.60 | 7841.05 | $206 | win | $+36.27 |
| 2026-09-28 | 7748.50 | 7707.91 | 7829.69 | $203 | loss | $-13.73 |
| 2026-09-29 | 7726.00 | 7684.64 | 7808.72 | $207 | win | $+25.02 |
| 2026-09-30 | 7712.25 | 7671.03 | 7794.69 | $206 | win | $+11.27 |
| 2026-10-01 | 7705.50 | 7664.43 | 7787.64 | $205 | win | $+87.52 |
| 2026-10-07 | 7829.00 | 7787.71 | 7911.58 | $206 | win | $+113.77 |
| 2026-10-08 | 7815.75 | 7775.68 | 7895.89 | $200 | loss | $-2.48 |
| 2026-10-13 | 7846.25 | 7809.85 | 7919.05 | $182 | win | $+42.52 |
| 2026-10-14 | 7834.50 | 7800.06 | 7903.38 | $172 | loss | $-177.17 |
| 2026-10-15 | 7741.00 | 7704.33 | 7814.34 | $183 | win | $+245.02 |
| 2026-10-16 | 7717.25 | 7679.93 | 7791.89 | $187 | loss | $-69.98 |
| 2026-10-22 | 7751.00 | 7711.17 | 7830.66 | $199 | loss | $-204.13 |
| 2026-10-23 | 7676.75 | 7635.62 | 7759.02 | $206 | loss | $-89.98 |
| 2026-10-29 | 7750.25 | 7709.36 | 7832.04 | $204 | win | $+15.02 |
| 2026-10-30 | 7709.25 | 7667.66 | 7792.43 | $208 | loss | $-212.93 |

17 trades, 47% win, $-29.13/trade. Break-even on this book is 33.3% — below that, more trades lose money.
