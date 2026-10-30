# Which daily book carries the account

Generated 2026-10-30T20:15Z · $25,000 start · $24,000 opening floor, trailing the highest close and locking at $25,100 · +$1,250 target · consistency ≤ 40% · one micro contract

The 15m book is retired. This compares what is left: the current daily rule, the same
rule with a smaller stop, the buffer-safe ES challenger, and the pair of them together.
The column that decides is not net profit — it is how often the evaluation is actually
passed when the account is walked forward from *every* starting trade.

## The trade record

| book | trades | win | $/trade | net $ | worst DD | median stop | stops hit | luck pct |
|---|---|---|---|---|---|---|---|---|
| NQ break-2 1.0A tp2 | 1722 | 58% | $+40 | $+69,329 | $-3,561 | $178 | 72 | 99.4% |
| NQ break-2 0.5A tp2 | 1722 | 41% | $-23 | $-40,156 | $-40,470 | $89 | 731 | 94.6% |
| ES fade-5 0.75A tp1 | 2440 | 55% | $+18 | $+44,064 | $-2,523 | $113 | 333 | 100.0% |
| ES fade-5 0.5A tp1 | 2440 | 57% | $+15 | $+37,193 | $-1,751 | $76 | 671 | 100.0% |
| NQ 1.0A + ES 0.75A | 4162 | 56% | $+27 | $+113,393 | $-3,618 | $132 | 405 | — |

## The account: every starting trade walked forward

`pass%` reaches +$1,250 before the trailing floor. `cons%` also satisfies the 40%
consistency rule. `breach%` of the attempts that finished hit the floor.

| book | starts | pass | pass% | with consistency | breach% | trades → pass | sessions → pass |
|---|---|---|---|---|---|---|---|
| NQ break-2 1.0A tp2 | 1722 | 1503 | 87% | 68% | 13% | 66 | 66 |
| NQ break-2 0.5A tp2 | 1722 | 134 | 8% | 3% | 92% | 9 | 9 |
| ES fade-5 0.75A tp1 | 2440 | 1756 | 72% | 71% | 27% | 79 | 79 |
| ES fade-5 0.5A tp1 | 2440 | 1935 | 79% | 78% | 19% | 121 | 121 |
| NQ 1.0A + ES 0.75A | 4162 | 3710 | 89% | 73% | 11% | 108 | 85 |

## The recent era (2023 onward) — the stops the account faces now

A $1,000 stop is not a property of a rule, it is a property of the price level: NQ's
1.0 ATR stop cost about $50 in 2009 and costs about $1,000 now. Seventeen years of
median is therefore two different accounts, and the one being evaluated is this one.

| book | trades | $/trade | win | pass% | with consistency | breach% | sessions → pass |
|---|---|---|---|---|---|---|---|
| NQ break-2 1.0A tp2 | 368 | $+122 | 62% | 85% | 23% | 14% | 10 |
| NQ break-2 0.5A tp2 | 368 | $-34 | 43% | 32% | 10% | 67% | 9 |
| ES fade-5 0.75A tp1 | 525 | $+33 | 57% | 78% | 78% | 19% | 26 |
| ES fade-5 0.5A tp1 | 525 | $+33 | 60% | 81% | 80% | 13% | 36 |
| NQ 1.0A + ES 0.75A | 893 | $+70 | 59% | 88% | 35% | 11% | 13 |

## The stop is the account decision, not the expectancy

| book | $/trade, all history | $/trade, 2023 onward | risk of one bad session now | buffer absorbs |
|---|---|---|---|
| NQ break-2 1.0A tp2 | $+40 | $+122 | $1,054 | 0.9 sessions |
| NQ break-2 0.5A tp2 | $-23 | $-34 | $527 | 1.9 sessions |
| ES fade-5 0.75A tp1 | $+18 | $+33 | $309 | 3.2 sessions |
| ES fade-5 0.5A tp1 | $+15 | $+33 | $206 | 4.9 sessions |
| NQ 1.0A + ES 0.75A | $+27 | $+70 | $992 | 1.0 sessions |

NQ break-2 at 1.0 ATR has the best expectancy on the page — about $40
a trade — and today one bad session risks $1,054. That is the whole
$1,000 allowance in a single session, so the account survives only by never being
wrong once. It still clears the consistency test only 23% of the time. Halving
the stop to 0.5 ATR does not fix that — it destroys the edge instead
($-34 a trade since 2023, 41% win), which
is the useful thing about this table: the stop distance is part of the rule, not a dial.

**The consistency rule is what eliminates NQ break-2, not its edge.** Since 2023 it
passes the raw target 85% of the time and breaches the
floor in only 14% of attempts — but just 23% of those passes keep the best day under
40% of profit, because one $1,054 winner against a $1,250 target is most of
the profit by itself. A rule that passes on two big days is a rule that fails the
consistency test. The pair of books has the same problem for the same reason
(35% with consistency
against 88% without it).

**Best for this account: ES fade-5 0.5A tp1** — 80% of starting points since 2023 pass with the
consistency rule intact, $206 of risk per session, 13% of attempts breaching, and a median of 36 sessions to the target. The 0.5 ATR
variant is a close second (80% at 36 sessions): slower,
and it breaches in 13% of
attempts instead of 7%, which is the trade you are making either way.

## The limits

Daily bars cannot see the order of events inside a session: when a stop and a target are
both touched the fill code takes the stop, which is the pessimistic reading and the right
one, but the real sequence could be worse (a gap through the stop) only in ways the open
already models. Slippage is one tick per side throughout. The floor is Lucid Flex's
end-of-day trail ($1,000 under the highest close, locking at $25,100); a breach is
scored on the close, so a session that dips through the floor and closes above it is
treated as survivable, which is the optimistic reading of that rule.

The passing rate is what the rule did over its whole history, not a forecast. It says the
edge has survived seventeen years and this account's rules; it does not say the next forty
sessions will look like the average of the last four thousand, and they will not.
