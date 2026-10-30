# Ninety days of the desk

Generated 2026-10-30T20:53Z · 63-session windows sampled from 2023-01-01 onward · 600 runs per line · small-bankroll line starts with $350

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
| 25k  ES 0.75A  1 micro | $460 | 25% | -$325 | $205 | -$460 | $2,043 | 17% | 41% | 2.0 | 0.9 |
| 25k  ES 0.75A  2 micros | $460 | 51% | -$455 | $1,801 | -$460 | $7,702 | 40% | 47% | 1.7 | 2.2 |
| 50k  ES 0.75A  2 micros | $815 | 25% | -$575 | $386 | -$815 | $3,867 | 16% | 35% | 1.8 | 0.9 |
| 50k  ES 0.75A  4 micros | $815 | 51% | -$805 | $3,458 | -$815 | $17,195 | 38% | 42% | 1.5 | 2.1 |
| 50k  ES 0.50A  5 micros | $815 | 42% | -$805 | $3,338 | -$815 | $14,476 | 42% | 48% | 1.5 | 1.8 |
| 100k ES 0.75A  6 micros | $1,525 | 51% | -$1,505 | $3,364 | -$1,525 | $20,995 | 32% | 37% | 1.4 | 2.1 |
| 150k ES 0.75A  9 micros | $2,290 | 51% | -$2,261 | $4,337 | -$2,290 | $24,739 | 32% | 39% | 1.4 | 2.1 |
| 150k ES 0.50A  7 micros | $2,290 | 26% | -$1,615 | $928 | -$2,290 | $10,070 | 21% | 31% | 1.2 | 1.2 |
| 150k NQ 1.0A   2 micros | $2,290 | 29% | -$1,615 | -$1,329 | -$2,261 | -$1,615 | 6% | 20% | 1.1 | 0.3 |
| 50k  NQ trio 1 micro | $815 | 58% | $4,250 | $6,834 | -$805 | $18,246 | 71% | 69% | 3.4 | 5.5 |
| 100k NQ trio 1 micro | $1,525 | 39% | -$1,075 | $2,080 | -$1,505 | $9,339 | 33% | 52% | 3.0 | 2.2 |
| 150k NQ trio 1 micro | $2,290 | 26% | -$1,615 | -$458 | -$2,261 | $2,635 | 14% | 28% | 1.6 | 0.9 |
| 150k NQ trio 2 micros | $2,290 | 51% | $3,775 | $8,080 | -$2,290 | $26,433 | 61% | 60% | 3.5 | 4.5 |
| ladder  ES 0.75A  31% | $350 | 31% | -$325 | $302 | -$325 | $2,169 | 16% | 40% | 1.6 | 0.9 |

**The pick: 150k NQ trio 2 micros** — mean $8,080 per ninety days on $2,290 of capital, median $3,775, p10 -$2,290, p90 $26,433, positive in 61% of windows. Over that quarter it opens 7 accounts, passes 5 evaluations, ends with 3.5 funded and takes 4.5 payouts. In six months the same line averages $34,640.

The pick is made on the six-month mean, not the three-month one: at ninety days the
top three lines sit within each other's error bars, and choosing between them on that
noise is how a backtest gets overfitted. It is restricted to lines that pass at least
40% of their evaluations and finish a quarter in profit at least 40% of the time —
a desk you would keep funding, not a lottery ticket that happens to have a good mean.

The caveat is the entry price, not the odds. The same book at $50K and one micro a rule
averages $19,169 over six months — about half — on $815 of capital
instead of $2,290, and puts 58% of a $2,000 buffer at
risk in an ordinary session instead of 51% of $4,500. If $2,290 is not sitting there,
that line is the same edge a quarter of the size, and the ordering does not change: the
trio beats every single-rule line in the table at both horizons.

Read the mean and the median together, because they disagree, and which one you
believe decides whether this is a business or a lottery ticket. On every single-rule
line the median quarter pays back **less than the fees** — the quarter is spent passing
evaluations that have not converted into cash yet — while a minority of windows pay
many multiples. On the trio the median quarter is positive, which is the whole reason
it is the pick: it is the only book here that is expected to pay in an ordinary tape
and not only in a good one.

## Six months, the same lines

The first quarter is mostly lead time; the second is where funded accounts start
paying more than once and the fees stop being the story. If the question is "will this
make money", this is the table that answers it, and the answers change sign.

| strategy | capital | stop / buffer | median net | mean net | p10 | p90 | windows positive | eval pass | funded at end | payouts |
|---|---|---|---|---|---|---|---|---|---|---|
| 25k  ES 0.75A  1 micro | $460 | 25% | -$455 | $2,080 | -$460 | $8,609 | 39% | 61% | 2.7 | 3.6 |
| 25k  ES 0.75A  2 micros | $460 | 51% | $1,236 | $3,681 | -$460 | $11,877 | 53% | 48% | 0.7 | 2.8 |
| 50k  ES 0.75A  2 micros | $815 | 25% | -$575 | $4,612 | -$815 | $19,096 | 44% | 54% | 1.9 | 3.0 |
| 50k  ES 0.75A  4 micros | $815 | 51% | $3,277 | $10,453 | -$815 | $38,646 | 61% | 52% | 1.2 | 4.9 |
| 50k  ES 0.50A  5 micros | $815 | 42% | $1,635 | $6,590 | -$815 | $22,433 | 56% | 49% | 0.6 | 2.1 |
| 100k ES 0.75A  6 micros | $1,525 | 51% | $4,422 | $11,466 | -$1,525 | $47,121 | 55% | 46% | 1.2 | 4.4 |
| 150k ES 0.75A  9 micros | $2,290 | 51% | $5,810 | $17,063 | -$2,290 | $65,239 | 59% | 48% | 1.3 | 5.1 |
| 150k ES 0.50A  7 micros | $2,290 | 26% | -$1,615 | $8,789 | -$2,261 | $35,937 | 47% | 56% | 2.0 | 3.2 |
| 150k NQ 1.0A   2 micros | $2,290 | 29% | -$1,615 | $3,931 | -$2,261 | $15,831 | 48% | 51% | 3.1 | 3.0 |
| 50k  NQ trio 1 micro | $815 | 58% | $21,999 | $19,169 | -$805 | $34,810 | 86% | 81% | 2.8 | 11.9 |
| 100k NQ trio 1 micro | $1,525 | 39% | $15,551 | $17,146 | $1,651 | $33,480 | 95% | 80% | 3.5 | 10.7 |
| 150k NQ trio 1 micro | $2,290 | 26% | $5,018 | $11,045 | -$2,261 | $29,771 | 88% | 72% | 3.9 | 6.6 |
| 150k NQ trio 2 micros | $2,290 | 51% | $38,339 | $34,640 | $4,018 | $58,680 | 96% | 85% | 3.5 | 14.4 |
| ladder  ES 0.75A  31% | $350 | 31% | -$325 | $1,958 | -$325 | $8,739 | 38% | 64% | 2.2 | 3.2 |

## The book that was on the desk on 29 October

Three NQ rules at one micro each — the narrow-range breakout, the prior-day breakout
and the five-day fade. Its replay over the last 40 sessions made $12,598, and that
number is real but it is not what the book does. Over every 40-session window since
2023 the same book has a median of $4,588, a best of $14,167 and a worst of
-$4,647, and the window that was traded sits in the 98th percentile of them.

Which is the argument for keeping it anyway, and why it is the desk's book again: the
median window is **positive** — $4,588 per 40 sessions at one micro a rule — where
the ES fade's median 40-session window is only $602. It was a lucky tape rather than a
lucky rule (each of the three legs is in its own 90th percentile over that window), but
the book earns its keep in an ordinary tape too, and that is what the table measures.

At $50K with one micro a rule it passes 69% of its evaluations, ends a quarter
with 3.4 funded and takes 5.5 payouts, for a mean of
$6,834, a median of $4,250 and 71% of quarters in profit — the
best median on the page: the trio's lines are the only ones whose median quarter is
positive at all. It is 58% of the buffer at risk in an ordinary session and 88% if all
three legs stop on the same day, which is why it belongs on a $50K and not on the $25K
it was being scored against — at $1,158 of median risk a 25K's $1,000 allowance is gone
before the first good week arrives — and why the pick above runs it on a $150K, where
the same book at two micros a rule still has a $4,500 allowance to be wrong inside.

## Why size, not count, decides the money

A 25K account at one micro — 25% of the buffer per stop, the conservative setting the last report recommended — is the worst line on the page:
mean $205, positive in 17% of windows. It
passes (41% of attempts) and still makes nothing worth having,
because a 25K pass is $1,250 of profit, the 50%-of-profit rule caps the first request
near $625, and the floor then locks at $25,100 with a few hundred dollars of room. The
account is too small for the machinery around it.

Doubling it to two micros on the same 25K account is the single biggest improvement on
the table for the capital: mean $1,801 on $460, 
positive in 40% of windows, and it reaches the payout gate
roughly twice as fast. The risk per stop rises to about 51% of the buffer, which is
the honest price: two bad sessions end the attempt instead of four.

Up the tiers the same trade repeats — the $50K at four micros averages $3,458 a quarter, the $150K at nine micros $4,337 —
but the cost is variance rather than average: the big accounts win bigger and also
empty the wallet more often (32% of quarters in profit against
38% for the 50K). Over six months they do pull ahead
($17,063 against $10,453), which is the fair argument for
them: the same edge, carried by bigger accounts, is worth more per funded slot, and
funded slots are the thing you cannot buy more of.

## Can it be done in three days?

Three days is the firm's *minimum*, not a schedule. It needs the full target inside
three sessions with no day over 40% of the profit. At every size on this page that
essentially never happens — 1% of passes at best arrive inside three sessions and 23% within ten, and the pick's median pass takes 33 sessions. Three days is set for
scalpers taking risk that would end this book; a rule that trades half the sessions
cannot finish a month of edge in a week, and trading bigger makes the target *bigger*
faster than it makes the gains bigger.

## Starting from $350

The ladder line buys the biggest account the bankroll can replace eight times over and sizes each to 31% of its buffer: mean $302, median -$325, 5 accounts opened, 1.6 funded at the end. It is the honest version of "reinvest the profits" — fees are cheap enough
that capital stops being the constraint within a quarter, and the account caps become
the ceiling instead.

## What this does not model

The sample is 2023 onward: one regime, with volatility high enough that a 0.75 ATR
stop is $250–$300. A calmer quarter passes more slowly; a violent one breaches more
accounts. Payouts are requested the instant they qualify, which no trader does
perfectly. Breaches are scored on the closing balance, not the session's worst moment.
Slippage is one tick per side and commissions are real, but a fast market fills worse.
The three legs are summed as one P&L. In a single account two of them can be on
opposite sides in the same session, which most brokers read as a hedge rather than as
two positions; net exposure is what is modelled, and net exposure is what such an
account would be judged on.
Fees are list prices; a 30%-off checkout improves every line, most of all the 25K one.
Lucid's payout page says "50% of your account balance" in one place and "50% of
profit" in its table; this models the stricter reading, so a payout cannot be taken
until profit is at least twice the request.

`NQ break-2` on its own at $150K and two micros (29% of the buffer a
stop) appears as a control: mean -$1,329, positive in 6% of windows.
The rule with the best expectancy on the page cannot carry a desk by itself, because
its best days are too large a share of a small pass threshold; inside the trio the other
two rules supply the ordinary days that dilute them.

Best odds on the page, if profit is not the only thing that matters: 50k  NQ trio 1 micro,
positive in 71% of windows with a mean of $6,834.
