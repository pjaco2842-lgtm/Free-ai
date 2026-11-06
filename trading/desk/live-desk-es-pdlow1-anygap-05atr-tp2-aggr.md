# The causal paper desk

Book `es-pdlow1-anygap-05atr-tp2-aggr` — 2 micro, ES=F, limit_low-1, gap:any, long only, 0.5 ATR stop, tp2 target.

> **Paper only.** The evidence behind this book is unvalidated: `RESEARCH-LOG.md` (o) showed the old fill model could count a target that traded before the dip. This runner uses the causal resolution instead, so the first 100 settled trades here are the test, not a formality.

## Next session

**BUY LIMIT 2 MES @ 7322.25** — for the session of 2026-11-09 (levels from the completed bar 2026-11-06).

| field | value |
|---|---|
| entry (buy limit) | **7322.25** |
| condition | no gap condition |
| distance from last close | 7390.00 → -0.92% |
| stop | **7258.26** (0.5 × ATR, ATR 127.98) |
| target | **7450.23** (2.0R) |
| risk if stopped | **$640** = 64% of the $1000 buffer |
| buffer left after one stop | $360 |

If the market gaps below the level, the limit fills at the open (better price); one tick of entry and exit slippage and $1.24 per side are charged on settlement.

## Account

- balance **$24,661.34** (-338.66 of the $1,250 target, -27%)
- end-of-day floor $24,215.59 — room $446
- largest day $956 = 0% of profit (limit 40%)
- status: **running**, 20 settled trades

## Pace against your rubric

| session | target | actual | cumulative |
|---|---:|---:|---:|
| 2026-09-16 | $500 | $-212.46 | $-212.46 |
| 2026-09-23 | $500 | $-389.96 | $-602.42 |
| 2026-09-24 | $250 | $+72.54 | $-529.88 |
| 2026-09-28 | — | $-27.46 | $-557.34 |
| 2026-09-29 | — | $+50.04 | $-507.30 |
| 2026-09-30 | — | $+22.54 | $-484.76 |
| 2026-10-01 | — | $+175.04 | $-309.72 |
| 2026-10-07 | — | $+227.54 | $-82.18 |
| 2026-10-08 | — | $-4.96 | $-87.14 |
| 2026-10-13 | — | $+85.04 | $-2.10 |
| 2026-10-14 | — | $-354.33 | $-356.43 |
| 2026-10-15 | — | $+490.04 | $+133.61 |
| 2026-10-16 | — | $-139.96 | $-6.35 |
| 2026-10-22 | — | $-408.26 | $-414.61 |
| 2026-10-23 | — | $-179.96 | $-594.57 |
| 2026-10-29 | — | $+30.04 | $-564.53 |
| 2026-10-30 | — | $-425.85 | $-990.38 |
| 2026-11-03 | — | $+250.04 | $-740.34 |
| 2026-11-04 | — | $+955.93 | $+215.59 |
| 2026-11-05 | — | $-554.25 | $-338.66 |

- best session $+955.93, average $-16.93/session
- your rubric: **keep it, no changes** (>= $500 keep, >= $200 a day keep and tweak, below that rework)
- stand-down at -$700/session: not hit

## Ledger

| date | entry | stop | target | risk | result | $ |
|---|---:|---:|---:|---:|---|---:|
| 2026-09-16 | 7576.75 | 7542.71 | 7644.84 | $340 | loss | $-212.46 |
| 2026-09-23 | 7810.50 | 7769.77 | 7891.96 | $407 | loss | $-389.96 |
| 2026-09-24 | 7758.75 | 7717.60 | 7841.05 | $411 | win | $+72.54 |
| 2026-09-28 | 7748.50 | 7707.91 | 7829.69 | $406 | loss | $-27.46 |
| 2026-09-29 | 7726.00 | 7684.64 | 7808.72 | $414 | win | $+50.04 |
| 2026-09-30 | 7712.25 | 7671.03 | 7794.69 | $412 | win | $+22.54 |
| 2026-10-01 | 7705.50 | 7664.43 | 7787.64 | $411 | win | $+175.04 |
| 2026-10-07 | 7829.00 | 7787.71 | 7911.58 | $413 | win | $+227.54 |
| 2026-10-08 | 7815.75 | 7775.68 | 7895.89 | $401 | loss | $-4.96 |
| 2026-10-13 | 7846.25 | 7809.85 | 7919.05 | $364 | win | $+85.04 |
| 2026-10-14 | 7834.50 | 7800.06 | 7903.38 | $344 | loss | $-354.33 |
| 2026-10-15 | 7741.00 | 7704.33 | 7814.34 | $367 | win | $+490.04 |
| 2026-10-16 | 7717.25 | 7679.93 | 7791.89 | $373 | loss | $-139.96 |
| 2026-10-22 | 7751.00 | 7711.17 | 7830.66 | $398 | loss | $-408.26 |
| 2026-10-23 | 7676.75 | 7635.62 | 7759.02 | $411 | loss | $-179.96 |
| 2026-10-29 | 7750.25 | 7709.36 | 7832.04 | $409 | win | $+30.04 |
| 2026-10-30 | 7709.25 | 7667.66 | 7792.43 | $416 | loss | $-425.85 |
| 2026-11-03 | 7570.75 | 7520.28 | 7671.70 | $505 | win | $+250.04 |
| 2026-11-04 | 7546.00 | 7497.71 | 7642.59 | $483 | win | $+955.93 |
| 2026-11-05 | 7490.00 | 7435.57 | 7598.86 | $544 | loss | $-554.25 |

20 trades, 50% win, $-16.93/trade. Break-even on this book is 33.3% — below that, more trades lose money.
