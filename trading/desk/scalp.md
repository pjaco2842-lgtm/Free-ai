# The scalp experiment — paper, five markets, no gate chain

Generated 2026-10-29T18:41Z · one micro contract · $1.24/side commission + 1 tick slippage per side

Every EMA cross, both directions, chosen on the first half of the sample and scored on
the second. Not evidence of an edge — evidence of what the costs do to one.

| market | tf | bars | sessions | chosen | 2nd-half trades | /day | win | avg R | net $ (worst→best) | max DD |
|---|---|---|---|---|---|---|---|---|---|---|
| ES=F | 1m | 7682 | 7 | 13/34 1.0A/2.0A 6b | 117 | 29.2 | 40% | -0.49 | $-585 → $-585 | $-604 |
| NQ=F | 1m | 7681 | 7 | 13/34 0.5A/1.5A 20b | 119 | 29.8 | 30% | -0.12 | $+64 → $+142 | $-339 |
| GC=F | 1m | 7724 | 7 | 8/21 1.0A/2.0A 6b | 176 | 44.0 | 41% | -0.14 | $-397 → $-397 | $-618 |
| CL=F | 1m | 7703 | 7 | 13/34 1.0A/2.0A 20b | 119 | 29.8 | 29% | -0.77 | $-680 → $-680 | $-730 |
| NKD=F | 1m | 5448 | 7 | 5/15 0.5A/1.5A 20b | 166 | 41.5 | 40% | -0.12 | $+590 → $+872 | $-2,548 |
| ES=F | 5m | 6046 | 27 | 13/34 0.5A/1.5A 6b | 121 | 8.6 | 29% | -0.35 | $-227 → $-177 | $-258 |
| NQ=F | 5m | 6043 | 27 | 5/15 0.5A/1.5A 20b | 237 | 16.9 | 31% | +0.10 | $+1,222 → $+1,587 | $-657 |
| GC=F | 5m | 6060 | 27 | 8/21 0.5A/1.5A 20b | 174 | 12.4 | 30% | -0.06 | $-521 → $-413 | $-828 |
| CL=F | 5m | 6058 | 27 | 5/15 1.0A/2.0A 20b | 176 | 12.6 | 36% | -0.21 | $-601 → $-531 | $-609 |
| NKD=F | 5m | 5644 | 27 | 13/34 1.0A/2.0A 20b | 106 | 8.2 | 33% | -0.16 | $-8,636 → $-8,636 | $-9,212 |
| ES=F | 15m | 4547 | 59 | 8/21 0.5A/1.5A 6b | 109 | 3.6 | 28% | -0.30 | $-310 → $-160 | $-413 |
| NQ=F | 15m | 4545 | 59 | 5/15 0.5A/1.5A 6b | 158 | 5.3 | 26% | -0.16 | $-810 → $-630 | $-2,005 |
| GC=F | 15m | 4547 | 59 | 5/15 1.0A/2.0A 20b | 157 | 5.2 | 34% | -0.10 | $-904 → $-617 | $-1,899 |
| CL=F | 15m | 4544 | 59 | 5/15 1.0A/2.0A 6b | 133 | 4.4 | 40% | -0.02 | $-247 → $-247 | $-783 |
| NKD=F | 15m | 4500 | 59 | 5/15 0.5A/1.5A 6b | 148 | 4.9 | 28% | -0.21 | $-11,796 → $-9,660 | $-15,111 |

Portfolio, second half: **2216 trades, $-23,838 to $-20,133** over ~59 sessions ($-404 to $-341 per session).

The range is the ambiguous-bar bracket: worst case assumes the stop filled first when a barheld both, best case the target. Neither is the truth; a strategy that only pays in the bestcase has not been shown to pay.
