# The causal paper desk

Book `gc-pdlow1-anygap-05atr-tp2-obs` — 1 micro, GC=F, limit_low-1, gap:any, long only, 0.5 ATR stop, tp2 target.

> **Paper only.** The evidence behind this book is unvalidated: `RESEARCH-LOG.md` (o) showed the old fill model could count a target that traded before the dip. This runner uses the causal resolution instead, so the first 100 settled trades here are the test, not a formality.

## Next session

**BUY LIMIT 1 MGC @ 4035.60** — for the session of 2026-11-09 (levels from the completed bar 2026-11-06).

| field | value |
|---|---|
| entry (buy limit) | **4035.60** |
| condition | no gap condition |
| distance from last close | 4072.30 → -0.90% |
| stop | **3993.13** (0.5 × ATR, ATR 84.94) |
| target | **4120.54** (2.0R) |
| risk if stopped | **$425** = 42% of the $1000 buffer |
| risk cap | $300 (30% of the buffer) — **this order would NOT be sent** |
| buffer left after one stop | $575 |

If the market gaps below the level, the limit fills at the open (better price); one tick of entry and exit slippage and $1.24 per side are charged on settlement.

## Account

- balance **$24,597.18** (-402.82 of the $1,250 target, -32%)
- end-of-day floor $24,000.00 — room $597
- this leg's best day $855 = no profit to measure it against yet (limit 50%; the rule is measured on the whole account)
- status: **running**, 20 settled trades
- risk cap $300/trade (30% of the buffer): 1 signals skipped, not resized
- session lock $400: 0 orders stood down once the day had banked

## Pace against your rubric

| session | target | actual | cumulative |
|---|---:|---:|---:|
| 2026-09-16 | $500 | $+854.52 | $+854.52 |
| 2026-09-21 | $500 | $+112.52 | $+967.04 |
| 2026-09-22 | $250 | $+156.52 | $+1,123.56 |
| 2026-09-23 | — | $-96.48 | $+1,027.08 |
| 2026-09-24 | — | $-131.48 | $+895.60 |
| 2026-09-28 | — | $-475.37 | $+420.23 |
| 2026-10-01 | — | $+236.52 | $+656.75 |
| 2026-10-02 | — | $-75.48 | $+581.27 |
| 2026-10-05 | — | $+25.52 | $+606.79 |
| 2026-10-06 | — | $+362.52 | $+969.31 |
| 2026-10-07 | — | $+95.52 | $+1,064.83 |
| 2026-10-13 | — | $-12.48 | $+1,052.35 |
| 2026-10-14 | — | $-390.52 | $+661.83 |
| 2026-10-19 | — | $-78.48 | $+583.35 |
| 2026-10-20 | — | $-134.48 | $+448.87 |
| 2026-10-21 | — | $+194.52 | $+643.39 |
| 2026-10-22 | — | $-347.84 | $+295.55 |
| 2026-10-23 | — | $-293.48 | $+2.07 |
| 2026-10-29 | — | $-59.48 | $-57.41 |
| 2026-10-30 | — | $-345.41 | $-402.82 |

- best session $+854.52, average $-20.14/session
- your rubric: **keep it, no changes** (>= $500 keep, >= $200 a day keep and tweak, below that rework)
- stand-down at -$350/session: hit on 2026-09-28, 2026-10-14; no further entry that day

## Ledger

| date | entry | stop | target | risk | result | $ |
|---|---:|---:|---:|---:|---|---:|
| 2026-09-16 | 4301.60 | 4244.75 | 4415.30 | $568 | win | $+854.52 |
| 2026-09-21 | 4372.20 | 4316.46 | 4483.67 | $557 | win | $+112.52 |
| 2026-09-22 | 4360.30 | 4305.27 | 4470.36 | $550 | win | $+156.52 |
| 2026-09-23 | 4327.60 | 4274.51 | 4433.79 | $531 | loss | $-96.48 |
| 2026-09-24 | 4310.70 | 4258.26 | 4415.57 | $524 | loss | $-131.48 |
| 2026-09-28 | 4289.20 | 4242.11 | 4383.38 | $471 | loss | $-475.37 |
| 2026-10-01 | 4178.20 | 4131.25 | 4272.09 | $469 | win | $+236.52 |
| 2026-10-02 | 4169.40 | 4124.54 | 4259.11 | $449 | loss | $-75.48 |
| 2026-10-05 | 4153.80 | 4109.32 | 4242.75 | $445 | win | $+25.52 |
| 2026-10-06 | 4150.40 | 4106.21 | 4238.77 | $442 | win | $+362.52 |
| 2026-10-07 | 4130.70 | 4088.59 | 4214.92 | $421 | win | $+95.52 |
| 2026-10-13 | 4178.10 | 4138.01 | 4258.29 | $401 | loss | $-12.48 |
| 2026-10-14 | 4169.70 | 4131.10 | 4246.91 | $386 | loss | $-390.52 |
| 2026-10-19 | 4167.50 | 4131.00 | 4240.49 | $365 | loss | $-78.48 |
| 2026-10-20 | 4155.60 | 4119.72 | 4227.36 | $359 | loss | $-134.48 |
| 2026-10-21 | 4130.10 | 4095.23 | 4199.85 | $349 | win | $+194.52 |
| 2026-10-22 | 4122.30 | 4087.96 | 4190.97 | $343 | loss | $-347.84 |
| 2026-10-23 | 4036.80 | 4001.67 | 4107.06 | $351 | loss | $-293.48 |
| 2026-10-29 | 4036.90 | 4002.37 | 4105.96 | $345 | loss | $-59.48 |
| 2026-10-30 | 4016.30 | 3982.21 | 4084.49 | $341 | loss | $-345.41 |

20 trades, 40% win, $-20.14/trade. Break-even on this book is 33.3% — below that, more trades lose money.
