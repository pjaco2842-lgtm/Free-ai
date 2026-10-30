# Was the 15-minute breakout ever there?

Generated 2026-10-30T16:07Z · 1000 coin-flip runs per test · one micro contract, $1.24 commission per side plus one tick of slippage per side

The paper book is losing about $6.65 a trade on GC and CL at 15 minutes. That is either
an edge in a bad stretch or no edge at all. Random timing with the same stop, target,
holding limit, session filter, trade frequency and costs answers it.

## First finding: the desk is not trading the rule that was tested

`paper_aggressive.step()` never implements the `cool` parameter. It re-enters on the
next bar after an exit, so the desk effectively runs cool 1b however the parameters are
set. The sweep scored cool 6b. Same entries, more of them — and each extra trade pays
costs for a signal that has not been shown to carry any.

| market | sweep rule (cool 6b) | same rule, cool 1b | paper desk | halted |
|---|---|---|---|---|
| GC=F | 61 trades, $-929.78 | 74 trades, $-1,210.09 | 38 trades, $-1,005.37 | yes |
| CL=F | 63 trades, $+5.55 | 82 trades, $-544.22 | 82 trades, $-544.23 | no |

The desk column can also be *shorter* than the rule: once equity passes the $1,000
buffer the desk halts and stops taking entries, so a longer replay of it is not a
longer record of the rule. GC halts here.

## GC=F — breakout on 15m, the rule the desk trades

59 sessions, 4534 bars, median risk $94, win rate 22%.

| | at the desk's cadence (cool 1b) | the rule as tested (cool 6b) |
|---|---|---|
| trades | 74 | 61 |
| net | $-1,210.09 | $-929.78 |
| per trade | $-16.35 | $-15.24 |
| win rate | 22% | 21% |
| avg R | -0.20 | -0.22 |

Before costs the desk's version made $-878.57; commissions and one tick each way took $331.52 — 27% of the loss.

Coin flip — random entry bar, random side, same stop, target, hold, session
filter, frequency and costs, 1000 runs:

| | value |
|---|---|
| random timing, mean | $-3.62/trade |
| random timing, win rate | 26% |
| random timing, 10th–90th pct | $-33.81 to $+28.18 |
| the rule | $-16.35/trade |
| percentile | 32nd |
| p-value | 0.68 |

**NO EDGE** — the rule sits inside the range random entries produce.

## CL=F — breakout on 15m, the rule the desk trades

59 sessions, 4531 bars, median risk $45, win rate 27%.

| | at the desk's cadence (cool 1b) | the rule as tested (cool 6b) |
|---|---|---|
| trades | 82 | 63 |
| net | $-544.22 | $+5.55 |
| per trade | $-6.64 | $+0.09 |
| win rate | 27% | 32% |
| avg R | -0.07 | +0.07 |

Before costs the desk's version made $-176.86; commissions and one tick each way took $367.36 — 68% of the loss.

Coin flip — random entry bar, random side, same stop, target, hold, session
filter, frequency and costs, 1000 runs:

| | value |
|---|---|
| random timing, mean | $+2.57/trade |
| random timing, win rate | 30% |
| random timing, 10th–90th pct | $-12.16 to $+16.52 |
| the rule | $-6.64/trade |
| percentile | 21st |
| p-value | 0.79 |

**NO EDGE** — the rule sits inside the range random entries produce.

## The whole 15m space, chosen on the first half and scored on the second

48 configs per market: 6 signal families x 2 variants x 4 exit brackets. Indicators
are a continuous series and every split is a filter on trade timestamps, so the two
halves are scored by the same run.

| market | configs clearing the floor | positive out of sample | median | best | worst |
|---|---|---|---|---|---|
| GC=F | 15 of 48 | 6 (40%) | $-453 | $+670 | $-2,000 |

**GC=F** — the sweep's own choice was **confluence** 1.0A/3.0A 48b: $+790 in training, **$+670** out of sample on 71 trades.
| CL=F | 10 of 48 | 1 (10%) | $-538 | $+143 | $-1,262 |

**CL=F** — the sweep's own choice was **breakout** 1.0A/3.0A 48b: $+1,014 in training, **$-1,262** out of sample on 86 trades.

## Walk-forward: would a re-sweep have picked something that worked?

Cut the last k sessions out of the sample, re-pick by training total R exactly as the
sweep does, then score the sessions that were removed. This is what pinning the rule
and trading it forward actually amounts to.

| market | held out | picked | train | that pick on the held-out sessions |
|---|---|---|---|---|
| GC=F | 1 | confluence 1.0/3.0A 48b | $+1,281 | $+179 on 1 trades |
| GC=F | 2 | confluence 1.0/3.0A 48b | $+1,448 | $-520 on 5 trades |
| GC=F | 3 | breakout 1.0/3.0A 48b | $+1,057 | $-285 on 13 trades |
| GC=F | 5 | breakout 1.0/3.0A 48b | $+934 | $-162 on 19 trades |
| GC=F | 8 | confluence 1.0/3.0A 48b | $+904 | $+556 on 17 trades |

**GC=F** — 2 different rules picked across 5 cuts; 2 of 5 made money trading what was picked (total $-230 over 55 trades).
| CL=F | 1 | confluence 1.0/3.0A 48b | $+654 | $-11 on 3 trades |
| CL=F | 2 | breakout 1.5/3.0A 48b | $+982 | $+23 on 3 trades |
| CL=F | 3 | breakout 1.5/3.0A 48b | $+799 | $+206 on 5 trades |
| CL=F | 5 | breakout 1.5/3.0A 48b | $+909 | $+96 on 10 trades |
| CL=F | 8 | confluence 1.0/3.0A 48b | $+675 | $-32 on 25 trades |

**CL=F** — 2 different rules picked across 5 cuts; 3 of 5 made money trading what was picked (total $+283 over 46 trades).

## Best case: cherry-pick the winner and coin-flip it

The sweep picked the best of 48 configs, which by itself guarantees a good-looking
number. So take the most favourable config in the sample — hindsight, not a rule — and
ask whether even that beats random entries with the same risk.

**GC=F** — confluence 1.0A/3.0A 48b: $+10.21/trade over 143 trades. Random timing with the same risk and frequency: $-5.87/trade (10th–90th pct $-28.85 to $+18.84). p = 0.18 → **no edge**.

**CL=F** — confluence 1.0A/2.0A 24b: $-1.45/trade over 137 trades. Random timing with the same risk and frequency: $+0.03/trade (10th–90th pct $-8.80 to $+9.03). p = 0.57 → **no edge**.

## A bug in the harness that produced the pinned rule

`aggressive.sweep_market()` scores the second half with `run(bars[cut:], S, ...)` while
`S` was built on the full series. `run` indexes `S[i]` and `bars[i]` together, so every
indicator the test half reads belongs to the *training* half — offset by `cut` bars. The
test column in `aggressive.md` is not measuring what it says it measures:

| market | breakout 1.0/3.0/48, harness test half | same config, correct split |
|---|---|---|
| GC=F | $+590 on 56 trades | $-2,000 on 78 trades |
| CL=F | $-1,490 on 66 trades | $-1,166 on 74 trades |

The pinning decision itself used the *training* half, which is aligned and unaffected.
What is unreliable is the out-of-sample column that was read as evidence the panel had
been validated. It had not.

## The answer

Neither market's rule is distinguishable from random entries. GC sits at p = 0.68 and CL at p = 0.79 — well inside the spread that random timing with the same stop, target and costs produces. Neither is in the tail.

The desk's CL figure of $-6.64/trade reproduces the $-6.65/trade in the replay almost exactly, which is a useful check on the arithmetic: these tests are measuring the same trades the paper book is making.

Costs do most of the damage. On CL the commissions and slippage are $367 against a net of $-544: before them the book is $-177 over 82 trades, which is not a loss worth arguing about either way. On GC the rule is worse than that, but still not by enough to separate it from luck (p = 0.68).

So: **the edge was never demonstrated, and the 15m book has been paying costs to trade a coin flip.** The two things that made GC/CL look worth trading do not survive a check —
the pick was the best of 48 tries, and the out-of-sample column that was read as validation was misaligned.

## What this test cannot see

59 sessions is a short sample. The random-entry spread runs $-34 to $+28 per trade on GC and $-12 to $+17 on CL, so an edge smaller than about $15-30 a trade would be invisible here. That cuts both ways: this does not prove the rule is worthless, only that nothing observed so far supports it, and the burden of proof is on the rule.

Two details of the method worth knowing. The null lands slightly fewer trades than the rule (about 54 against 74 on GC) because random entries collide with positions already open, so the comparison is per trade rather than per session. And the null ignores the desk's `MAX_OPEN = 2` limit, which can suppress an entry in one market while a position is open in the other — an account constraint, not something that changes whether the signal carries information.
