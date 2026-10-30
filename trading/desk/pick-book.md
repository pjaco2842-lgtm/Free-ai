# Which daily book carries the account

Generated 2026-10-30T16:22Z · $25,000 start · static $24,000 end-of-day floor · +$1,250 target · consistency ≤ 40% · one micro contract

The 15m book is retired. This compares what is left: the current daily rule, the same
rule with a smaller stop, the buffer-safe ES challenger, and the pair of them together.
The column that decides is not net profit — it is how often the evaluation is actually
passed when the account is walked forward from *every* starting trade.

## The trade record

| book | trades | win | $/trade | net $ | worst DD | median stop | stops hit | luck pct |
|---|---|---|---|---|---|---|---|---|
| NQ break-2 1.0A tp2 | 1722 | 58% | $+40 | $+69,329 | $-3,561 | $178 | 72 | 99.4% |
| NQ break-2 0.5A tp2 | 1722 | 41% | $-23 | $-40,156 | $-40,470 | $89 | 731 | 94.6% |
| ES fade-5 0.75A tp1 | 2440 | 55% | $+18 | $+44,688 | $-2,523 | $113 | 332 | 100.0% |
| ES fade-5 0.5A tp1 | 2440 | 57% | $+15 | $+37,609 | $-1,751 | $76 | 670 | 100.0% |
| NQ 1.0A + ES 0.75A | 4162 | 56% | $+27 | $+114,017 | $-3,618 | $132 | 404 | — |

## The account: every starting trade walked forward

`pass%` reaches +$1,250 before the $24,000 floor. `cons%` also satisfies the 40%
consistency rule. `breach%` of the attempts that finished hit the floor.

| book | starts | pass | pass% | with consistency | breach% | trades → pass | sessions → pass |
|---|---|---|---|---|---|---|---|
| NQ break-2 1.0A tp2 | 1722 | 1578 | 92% | 68% | 8% | 59 | 59 |
| NQ break-2 0.5A tp2 | 1722 | 154 | 9% | 3% | 91% | 10 | 10 |
| ES fade-5 0.75A tp1 | 2440 | 2106 | 86% | 83% | 13% | 84 | 84 |
| ES fade-5 0.5A tp1 | 2440 | 2129 | 87% | 86% | 11% | 118 | 118 |
| NQ 1.0A + ES 0.75A | 4162 | 3929 | 94% | 75% | 5% | 97 | 77 |

## The recent era (2023 onward) — the stops the account faces now

A $1,000 stop is not a property of a rule, it is a property of the price level: NQ's
1.0 ATR stop cost about $50 in 2009 and costs about $1,000 now. Seventeen years of
median is therefore two different accounts, and the one being evaluated is this one.

| book | trades | $/trade | win | pass% | with consistency | breach% | sessions → pass |
|---|---|---|---|---|---|---|---|
| NQ break-2 1.0A tp2 | 368 | $+122 | 62% | 92% | 23% | 8% | 10 |
| NQ break-2 0.5A tp2 | 368 | $-34 | 43% | 36% | 12% | 64% | 10 |
| ES fade-5 0.75A tp1 | 525 | $+34 | 57% | 90% | 90% | 7% | 29 |
| ES fade-5 0.5A tp1 | 525 | $+34 | 60% | 91% | 88% | 2% | 39 |
| NQ 1.0A + ES 0.75A | 893 | $+70 | 59% | 95% | 38% | 4% | 13 |

## The stop is the account decision, not the expectancy

| book | $/trade, all history | $/trade, 2023 onward | risk of one bad session now | buffer absorbs |
|---|---|---|---|
| NQ break-2 1.0A tp2 | $+40 | $+122 | $1,054 | 0.9 sessions |
| NQ break-2 0.5A tp2 | $-23 | $-34 | $527 | 1.9 sessions |
| ES fade-5 0.75A tp1 | $+18 | $+34 | $309 | 3.2 sessions |
| ES fade-5 0.5A tp1 | $+15 | $+34 | $206 | 4.9 sessions |
| NQ 1.0A + ES 0.75A | $+27 | $+70 | $992 | 1.0 sessions |

NQ break-2 at 1.0 ATR has the best expectancy on the page — about $40
a trade — and today one bad session risks $1,054. That is the whole
$1,000 allowance in a single session, so the account survives only by never being
wrong once. It still clears the consistency test only 23% of the time. Halving
the stop to 0.5 ATR does not fix that — it destroys the edge instead
($-34 a trade since 2023, 41% win), which
is the useful thing about this table: the stop distance is part of the rule, not a dial.

**The consistency rule is what eliminates NQ break-2, not its edge.** Since 2023 it
passes the raw target 92% of the time and breaches the
floor in only 8% of attempts — but just 23% of those passes keep the best day under
40% of profit, because one $1,054 winner against a $1,250 target is most of
the profit by itself. A rule that passes on two big days is a rule that fails the
consistency test. The pair of books has the same problem for the same reason
(38% with consistency
against 95% without it).

**Best for this account: ES fade-5 0.75A tp1** — 90% of starting points since 2023 pass with the
consistency rule intact, $309 of risk per session, 7% of attempts breaching, and a median of 29 sessions to the target. The 0.5 ATR
variant is a close second (88% at 39 sessions): slower,
and it breaches in 2% of
attempts instead of 7%, which is the trade you are making either way.

## The limits

Daily bars cannot see the order of events inside a session: when a stop and a target are
both touched the fill code takes the stop, which is the pessimistic reading and the right
one, but the real sequence could be worse (a gap through the stop) only in ways the open
already models. Slippage is one tick per side throughout. The floor is treated as static
end-of-day, which is how Lucid Flex is described; a trailing intraday floor would fail
more attempts than this shows.

The passing rate is what the rule did over its whole history, not a forecast. It says the
edge has survived seventeen years and this account's rules; it does not say the next forty
sessions will look like the average of the last four thousand, and they will not.
