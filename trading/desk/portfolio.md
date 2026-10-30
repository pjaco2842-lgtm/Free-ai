# Ninety days of the desk

Generated 2026-10-30T20:26Z · 63-session windows sampled from 2023-01-01 onward · 800 runs per line · small-bankroll line starts with $350

One account is a puzzle; a portfolio of them is a business, and the business has
different limits. Lucid allows **ten accounts in total, five of them funded**, so
"open more accounts with the profits" hits a wall that has nothing to do with money.
The scarce thing is a *funded slot*, and each one pays out at most $1,000 (25K) /
$2,000 (50K) / $2,500 (100K) / $3,000 (150K) per request, at most 50% of profit, only
after five separate days of $100–$250 profit, and only five times before the account
is retired to a live review.

## What is being simulated

Every run samples a real 63-session window of trades from 2023 onward — the era whose
volatility matches today's — and runs five evaluation slots and five funded slots
through it. Evaluations pay their fee out of capital and are replaced at the reset fee
when they breach. A pass converts to a funded account at zero profit. Every funded
account requests the largest payout the rules allow the moment it qualifies, and the
90% share is banked. All accounts in a run see the same market window, which is what
copying one signal across ten accounts actually looks like.

Capital is set to five evaluation fees plus three resets, which is the minimum needed
to keep the desk staffed; the ladder line is the exception and starts from $350.

## Ninety days

| strategy | capital | stop / buffer | median net | mean net | p10 | p90 | windows positive | eval pass | funded at end | payouts |
|---|---|---|---|---|---|---|---|---|---|---|
| 25k  ES 0.75A  1 micro | $460 | 25% | -$390 | $207 | -$460 | $2,039 | 16% | 41% | 2.0 | 0.9 |
| 25k  ES 0.75A  2 micros | $460 | 51% | -$455 | $1,632 | -$460 | $6,874 | 40% | 46% | 1.6 | 1.9 |
| 50k  ES 0.75A  2 micros | $815 | 25% | -$575 | $364 | -$815 | $3,862 | 17% | 32% | 1.7 | 1.0 |
| 50k  ES 0.75A  4 micros | $815 | 51% | -$805 | $3,632 | -$815 | $17,195 | 42% | 44% | 1.4 | 2.2 |
| 50k  ES 0.50A  5 micros | $815 | 42% | -$805 | $3,530 | -$815 | $15,016 | 43% | 49% | 1.8 | 2.3 |
| 100k ES 0.75A  6 micros | $1,525 | 51% | -$1,505 | $3,353 | -$1,525 | $20,995 | 32% | 38% | 1.4 | 2.0 |
| 150k ES 0.75A  9 micros | $2,290 | 51% | -$2,261 | $3,267 | -$2,290 | $20,833 | 30% | 36% | 1.4 | 1.9 |
| 150k ES 0.50A  7 micros | $2,290 | 26% | -$1,615 | $1,504 | -$2,290 | $11,239 | 24% | 32% | 1.3 | 1.5 |
| 150k NQ 1.0A   2 micros | $2,290 | 29% | -$1,615 | -$1,486 | -$2,261 | -$1,615 | 5% | 20% | 1.1 | 0.2 |
| ladder  ES 0.75A  31% | $350 | 31% | -$325 | $263 | -$325 | $2,169 | 16% | 41% | 1.7 | 0.9 |

**The pick: 50k  ES 0.75A  4 micros** — mean $3,632 per ninety days on $815 of capital, median -$805, p10 -$815, p90 $17,195, positive in 42% of windows. Over that quarter it opens 6 accounts, passes 4 evaluations, ends with 1.4 funded and takes 2.2 payouts. In six months the same line averages $8,503.

The pick is made on the six-month mean, not the three-month one: at ninety days the
top three lines sit within each other's error bars, and choosing between them on that
noise is how a backtest gets overfitted. It is restricted to lines that pass at least
40% of their evaluations and finish a quarter in profit at least 40% of the time —
a desk you would keep funding, not a lottery ticket that happens to have a good mean.

Both big-account lines fail that second test, and it is worth saying exactly what is
being refused: the $150K at nine micros averages $14,569
over six months — the most money on the page — while losing money in 70% of ninety-day windows, and its worst tenth of
six-month windows ends down $2,290. That is
the trade the brief asks for and the one worth thinking twice about: the same edge,
carried bigger, and three times as likely to have you funding accounts out of your own
pocket for a quarter before it pays anything back.

Read the mean and the median together, because they disagree and the disagreement is
the whole story. The median window pays back **less than the fees** — you spend the
quarter passing evaluations that have not yet converted into cash — while a minority
of windows pay many multiples. That is a business with a long lead time, not a
steady drip, and it is why a ninety-day judgement flatters nothing.

## Six months, the same lines

The first quarter is mostly lead time; the second is where funded accounts start
paying more than once and the fees stop being the story. If the question is "will this
make money", this is the table that answers it, and the answers change sign.

| strategy | capital | stop / buffer | median net | mean net | p10 | p90 | windows positive | eval pass | funded at end | payouts |
|---|---|---|---|---|---|---|---|---|---|---|
| 25k  ES 0.75A  1 micro | $460 | 25% | -$455 | $2,201 | -$460 | $10,877 | 41% | 61% | 2.7 | 3.8 |
| 25k  ES 0.75A  2 micros | $460 | 51% | $1,970 | $5,086 | -$460 | $20,111 | 60% | 53% | 1.0 | 4.1 |
| 50k  ES 0.75A  2 micros | $815 | 25% | -$575 | $4,987 | -$815 | $19,995 | 46% | 56% | 2.2 | 3.3 |
| 50k  ES 0.75A  4 micros | $815 | 51% | $2,403 | $8,503 | -$815 | $30,722 | 59% | 47% | 0.9 | 3.6 |
| 50k  ES 0.50A  5 micros | $815 | 42% | $1,900 | $6,548 | -$805 | $24,016 | 56% | 55% | 0.6 | 2.1 |
| 100k ES 0.75A  6 micros | $1,525 | 51% | $3,509 | $10,551 | -$1,525 | $35,259 | 54% | 45% | 0.9 | 3.6 |
| 150k ES 0.75A  9 micros | $2,290 | 51% | $4,989 | $14,569 | -$2,290 | $65,106 | 53% | 46% | 1.2 | 4.7 |
| 150k ES 0.50A  7 micros | $2,290 | 26% | $367 | $8,315 | -$2,264 | $35,186 | 52% | 56% | 1.9 | 3.2 |
| 150k NQ 1.0A   2 micros | $2,290 | 29% | -$1,615 | $3,683 | -$2,290 | $15,831 | 42% | 47% | 2.9 | 3.0 |
| ladder  ES 0.75A  31% | $350 | 31% | -$325 | $2,274 | -$325 | $11,007 | 39% | 64% | 2.1 | 3.5 |

## Why size, not count, decides the money

A 25K account at one micro — 25% of the buffer per stop, the conservative setting the last report recommended — is the worst line on the page:
mean $207, positive in 16% of windows. It
passes (41% of attempts) and still makes nothing worth having,
because a 25K pass is $1,250 of profit, the 50%-of-profit rule caps the first request
near $625, and the floor then locks at $25,100 with a few hundred dollars of room. The
account is too small for the machinery around it.

Doubling it to two micros on the same 25K account is the single biggest improvement on
the table for the capital: mean $1,632 on $460, 
positive in 40% of windows, and it reaches the payout gate
roughly twice as fast. The risk per stop rises to about 51% of the buffer, which is
the honest price: two bad sessions end the attempt instead of four.

Up the tiers the same trade repeats — the $50K at four micros averages $3,632 a quarter, the $150K at nine micros $3,267 —
but the cost is variance rather than average: the big accounts win bigger and also
empty the wallet more often (30% of quarters in profit against
42% for the 50K). Over six months they do pull ahead
($14,569 against $8,503), which is the fair argument for
them: the same edge, carried by bigger accounts, is worth more per funded slot, and
funded slots are the thing you cannot buy more of.

## Can it be done in three days?

Three days is the firm's *minimum*, not a schedule. It needs the full target inside
three sessions with no day over 40% of the profit. At every size on this page that
essentially never happens — 1% of passes at best arrive inside three sessions, 18% within ten at the fastest line (5% at the slowest), and the median pass takes 30 sessions. Three days is set for
scalpers taking risk that would end this book; a rule that trades half the sessions
cannot finish a month of edge in a week, and trading bigger makes the target *bigger*
faster than it makes the gains bigger.

## Starting from $350

The ladder line buys the biggest account the bankroll can replace eight times over and sizes each to 31% of its buffer: mean $263, median -$325, 5 accounts opened, 1.7 funded at the end. It is the honest version of "reinvest the profits" — fees are cheap enough
that capital stops being the constraint within a quarter, and the account caps become
the ceiling instead.

## What this does not model

The sample is 2023 onward: one regime, with volatility high enough that a 0.75 ATR
stop is $250–$300. A calmer quarter passes more slowly; a violent one breaches more
accounts. Payouts are requested the instant they qualify, which no trader does
perfectly. Breaches are scored on the closing balance, not the session's worst moment.
Slippage is one tick per side and commissions are real, but a fast market fills worse.
Fees are list prices; a 30%-off checkout improves every line, most of all the 25K one.
Lucid's payout page says "50% of your account balance" in one place and "50% of
profit" in its table; this models the stricter reading, so a payout cannot be taken
until profit is at least twice the request.

`NQ break-2` at $150K (29% of the buffer per stop) appears as
a control: mean -$1,486, positive in 5% of windows.
Its edge is real and its best days are too large a share of a small pass threshold,
which is exactly why it was retired from the single-account book.

Best odds on the page, if profit is not the only thing that matters: 50k  ES 0.50A  5 micros,
positive in 43% of windows with a mean of $3,530.
