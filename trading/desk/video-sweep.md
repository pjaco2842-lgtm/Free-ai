# The 26,000-strategy video, tested properly on daily bars

**151,305 configurations scored** across 5 contracts. Exit is always the session close ("no TP, hold to close"); the stop is resolved on the close, which flatters tight stops and is why every stop is printed beside its score. Costs: commission plus one tick of slippage each side.

Multiple-testing line for 151,305 tries: **t > 4.88**. Anything below it is the best of a coin-flipping crowd, not an edge.

| sym | family | lb | gap | trend | post | day | stop | tp | n | win | $/trade | alpha | t |
|---|---|---:|---|---|---|---|---:|---|---:|---:|---:|---:|---:|
| NKD=F | prior_high_break | 5 | with | up | any | Wed | 2.5 ATR | close | 46 | 63% | $+804.59 | +863.35 | +2.32 |
| NKD=F | prior_high_break | 5 | with | up | any | Wed | 2.5 ATR | 1.0 | 46 | 63% | $+804.59 | +863.35 | +2.32 |
| NKD=F | prior_high_break | 5 | with | up | any | Wed | 2.5 ATR | 2.0 | 46 | 63% | $+804.59 | +863.35 | +2.32 |
| NKD=F | prior_high_break | 5 | with | up | clean | Wed | 2.5 ATR | close | 46 | 63% | $+804.59 | +863.35 | +2.32 |
| NKD=F | prior_high_break | 5 | with | up | clean | Wed | 2.5 ATR | 1.0 | 46 | 63% | $+804.59 | +863.35 | +2.32 |
| NKD=F | prior_high_break | 5 | with | up | clean | Wed | 2.5 ATR | 2.0 | 46 | 63% | $+804.59 | +863.35 | +2.32 |
| NKD=F | prior_high_break | 5 | with | up | any | Wed | 2.0 ATR | close | 46 | 63% | $+804.59 | +860.39 | +2.31 |
| NKD=F | prior_high_break | 5 | with | up | any | Wed | 2.0 ATR | 2.0 | 46 | 63% | $+804.59 | +860.39 | +2.31 |
| NKD=F | prior_high_break | 5 | with | up | clean | Wed | 2.0 ATR | close | 46 | 63% | $+804.59 | +860.39 | +2.31 |
| NKD=F | prior_high_break | 5 | with | up | clean | Wed | 2.0 ATR | 2.0 | 46 | 63% | $+804.59 | +860.39 | +2.31 |
| NKD=F | prior_high_break | 5 | with | up | any | Wed | 1.5 ATR | close | 46 | 63% | $+804.59 | +847.87 | +2.27 |
| NKD=F | prior_high_break | 5 | with | up | any | Wed | 1.5 ATR | 2.0 | 46 | 63% | $+804.59 | +847.87 | +2.27 |

## Verdict

- configurations with positive alpha: **63,142 of 151,305** (41.7%)
- configurations clearing the multiple-testing line: **0**

**Nothing survived.** Every positive-alpha configuration sits below the multiple-testing line, which is exactly what the video says happens to popular strategies when they meet 16 years of data and a matched null: the best of many tries is the best of many coin flips.

## The video's four claims, scored

- **claim 1 breakout + hold to close**: best alpha +863.35 (NKD=F, 2.5 ATR stop, 46 trades, 63% win, t +2.32) — does not clear the line
- **claim 2 gap direction**: best alpha +431.41 (NKD=F, 0.5 ATR stop, 31 trades, 45% win, t +0.82) — does not clear the line
- **claim 3 fade after a trend day**: best alpha -95.11 (GC=F, 0.5 ATR stop, 40 trades, 0% win, t -6.30) — does not clear the line
- **claim 4 Monday gap fade**: best alpha +74.29 (CL=F, 2.5 ATR stop, 34 trades, 53% win, t +1.67) — does not clear the line

