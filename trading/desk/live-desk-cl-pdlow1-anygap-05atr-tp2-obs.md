# The causal paper desk

Book `cl-pdlow1-anygap-05atr-tp2-obs` — 1 micro, CL=F, limit_low-1, gap:any, long only, 0.5 ATR stop, tp2 target.

> **Paper only.** The evidence behind this book is unvalidated: `RESEARCH-LOG.md` (o) showed the old fill model could count a target that traded before the dip. This runner uses the causal resolution instead, so the first 100 settled trades here are the test, not a formality.

## Next session

**BUY LIMIT 1 MCL @ 89.08** — for the session of 2026-11-09 (levels from the completed bar 2026-11-06).

| field | value |
|---|---|
| entry (buy limit) | **89.08** |
| condition | no gap condition |
| distance from last close | 90.82 → -1.92% |
| stop | **86.52** (0.5 × ATR, ATR 5.12) |
| target | **94.20** (2.0R) |
| risk if stopped | **$256** = 26% of the $1000 buffer |
| risk cap | $300 (30% of the buffer) — inside the cap |
| buffer left after one stop | $744 |

If the market gaps below the level, the limit fills at the open (better price); one tick of entry and exit slippage and $1.24 per side are charged on settlement.

## Account

- balance **$26,151.82** (+1,151.82 of the $1,250 target, 92%)
- end-of-day floor $25,193.67 — room $958
- this leg's best day $388 = 34% of its profit (limit 50%; the rule is measured on the whole account)
- status: **running**, 18 settled trades
- risk cap $300/trade (30% of the buffer): 0 signals skipped, not resized
- session lock $400: 0 orders stood down once the day had banked

## Pace against your rubric

| session | target | actual | cumulative |
|---|---:|---:|---:|
| 2026-09-16 | $500 | $+117.52 | $+117.52 |
| 2026-09-17 | $500 | $+89.52 | $+207.04 |
| 2026-09-21 | $250 | $-234.16 | $-27.12 |
| 2026-09-22 | — | $+32.52 | $+5.40 |
| 2026-09-23 | — | $+222.52 | $+227.92 |
| 2026-09-28 | — | $+104.52 | $+332.44 |
| 2026-09-29 | — | $-191.48 | $+140.96 |
| 2026-09-30 | — | $+159.52 | $+300.48 |
| 2026-10-02 | — | $+227.52 | $+528.00 |
| 2026-10-06 | — | $+65.52 | $+593.52 |
| 2026-10-12 | — | $+368.52 | $+962.04 |
| 2026-10-15 | — | $+387.59 | $+1,349.63 |
| 2026-10-21 | — | $-108.48 | $+1,241.15 |
| 2026-10-27 | — | $-47.48 | $+1,193.67 |
| 2026-11-02 | — | $-217.41 | $+976.26 |
| 2026-11-03 | — | $+89.52 | $+1,065.78 |
| 2026-11-04 | — | $-248.48 | $+817.30 |
| 2026-11-05 | — | $+334.52 | $+1,151.82 |

- best session $+387.59, average $+63.99/session
- your rubric: **rework it** (>= $500 keep, >= $200 a day keep and tweak, below that rework)
- stand-down at -$350/session: not hit

## Ledger

| date | entry | stop | target | risk | result | $ |
|---|---:|---:|---:|---:|---|---:|
| 2026-09-16 | 101.21 | 99.04 | 105.54 | $217 | win | $+117.52 |
| 2026-09-17 | 100.97 | 98.76 | 105.38 | $221 | win | $+89.52 |
| 2026-09-21 | 99.19 | 96.89 | 103.78 | $230 | loss | $-234.16 |
| 2026-09-22 | 94.22 | 91.80 | 99.06 | $242 | win | $+32.52 |
| 2026-09-23 | 89.89 | 87.48 | 94.72 | $241 | win | $+222.52 |
| 2026-09-28 | 91.51 | 88.94 | 96.65 | $257 | win | $+104.52 |
| 2026-09-29 | 91.25 | 88.63 | 96.49 | $262 | loss | $-191.48 |
| 2026-09-30 | 88.78 | 86.09 | 94.17 | $269 | win | $+159.52 |
| 2026-10-02 | 88.79 | 86.32 | 93.72 | $247 | win | $+227.52 |
| 2026-10-06 | 88.74 | 86.34 | 93.54 | $240 | win | $+65.52 |
| 2026-10-12 | 90.01 | 87.83 | 94.37 | $218 | win | $+368.52 |
| 2026-10-15 | 93.97 | 92.01 | 97.89 | $196 | win | $+387.59 |
| 2026-10-21 | 98.19 | 96.00 | 102.56 | $219 | loss | $-108.48 |
| 2026-10-27 | 100.33 | 98.15 | 104.69 | $218 | loss | $-47.48 |
| 2026-11-02 | 102.39 | 100.26 | 106.65 | $213 | loss | $-217.41 |
| 2026-11-03 | 95.15 | 92.82 | 99.81 | $233 | win | $+89.52 |
| 2026-11-04 | 93.59 | 91.15 | 98.47 | $244 | loss | $-248.48 |
| 2026-11-05 | 87.13 | 84.50 | 92.39 | $263 | win | $+334.52 |

18 trades, 67% win, $+63.99/trade. Break-even on this book is 33.3% — below that, more trades lose money.
