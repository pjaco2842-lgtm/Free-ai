# Research log

Every idea that gets tested, with its parameters and what happened. Never edited to
look better afterwards; new entries go at the top. The count at the bottom is the
point: most ideas die, and forgetting how many died is how you fool yourself.

Rules for an entry: date, idea in one line, exact parameters, in-sample result,
out-of-sample result, coin-flip p-value, verdict.

---

## 2026-10-26 (e) — small accounts: micros make it tradeable, they do not make it compound

**CORRECTION (same day).** The first version of this entry scaled every symbol by
1/10 for "micro" sizing. That was wrong in both directions: `MARKETS` already
holds MNQ/MYM point values for NQ/YM, so those were shrunk twice, and ZS needed the
real MZS spec (500 bu, 0.5-cent tick) rather than a blind price cut. `--micro` now
converts only ZS, and the account also enforces one planned-risk budget per *day*
rather than one per trade. Every number below is from the corrected code.

**Idea.** Size the three survivors for a $2,500 account.

**Parameters.** `target.py --equity 2500 --risk 0.02 --micro` — 2% planned risk per
day, whole contracts, 20-contract daily cap (a prop-firm style limit).

**Result.** 65 trades over 16.3 years, **final $2,457** — a small loss, −0.1%/yr,
12.2% max drawdown, eight breaches of −10%. 153 signals skipped: at $50 of daily
risk, one MZS or MNQ stop often does not fit. The target is never reached from any
sampled start date.

**Why this is worse than the earlier $4,339 figure.** That number came from the
double-scaled NQ/YM values plus a per-*trade* risk budget. Fixing the contract map
and moving to a per-day budget removes the extra contracts that were manufacturing
position size the account could not actually carry.

**Verdict.** On $2,500 this portfolio is not a growth engine; it is roughly
break-even before the market teaches you anything. The 10.5x target needs a
different instrument or a different account, not a bigger risk setting.

---

## 2026-10-26 (f) — Lucid 25K evaluation: the constraints are the problem, not the profit target

**Idea.** The user's live goal is a Lucid 25K evaluation: +$1,250 with a 50%
consistency rule, then a funded account. The profit target is small; the survival
rules are not. Test the three rules against them.

**Rules used (official Lucid help center, read 2026-10-26).**
- 25K evaluation: profit target **$1,250**, max loss limit **$1,000**, max size
  **2 minis / 20 micros**, EOD trailing drawdown on Pro/Flex (initial trail balance
  **$26,100**, locked MLL **$25,100**). Daily loss limit: none on Pro 25K, $600 on
  the front page config, optional on Daily/Flex.
- Consistency = **largest single-day profit / account profit**. At a $1,250 target,
  50% means **$625** (Lucid's published cushion example is $650, and it explicitly
  says that is not a fixed allowance). Pro uses 40% for *funded* payouts, not for
  the pass; Daily offers 40% standard or 50% as a paid add-on.

**Method.** `target.py` now replays the Lucid constraints from every historical
signal date: fresh $25,000, EOD trailing floor, largest-day/gross-profit
consistency, 20-contract daily cap, and a planned daily risk budget.

| planned daily risk | starts that pass profit+consistency without breach | breach before pass | median days to pass |
|---|---|---|---|
| 0.5% | 2 / 207 (1.0%) | 0 (205 unfinished) | 3,928 |
| **1.0%** | **39 / 207 (18.8%)** | **114** | **603** |
| 2.0% | 53 / 207 (25.6%) | 145 | 301 |

**Reading it.** More risk buys a slightly higher pass rate and a much higher
failure rate. At 1% daily risk you pass about one start in five, fail more than
half, and the median pass takes ~20 months of trading days. At 2% the pass rate
edges to 26% while 70% breach the $1,000 limit.

**Caveats — this is not an official simulator.** Daily bars only, so intraday
drawdown, intraday trailing breaches, commissions on the evaluation's own fills,
and Lucid's exact cushion arithmetic are all approximated. Treat the percentages
as an order of magnitude, not a promise.

**One-week horizon — the question that matters for "pass in a week".**
`--horizon-days 5` limits every replay to a five-trading-day attempt:

| planned daily risk | pass both gates in 5 days | breached $1,000 first |
|---|---|---|
| 2% | 5 / 207 (2.4%) | 57 |
| 3% | 6 / 207 (2.9%) | 108 |
| 5% | 5 / 207 (2.4%) | 132 |

Tripling the risk does not raise the pass rate; it roughly doubles the failure rate.
And the reason is frequency, not size: the portfolio fires **12.4 signals a year**,
the **median gap between signal days is 18 days**, the longest is 193, and only
**19% of seven-day windows contain even one signal**. In 81% of weeks there is
nothing to size. Aggression cannot manufacture a trade that does not exist.

**Verdict.** The three rules do not solve the evaluation; they occasionally survive
it. A 20% pass rate per attempt also means most attempts are re-buys, so the
evaluation fee is a real cost of this plan. If a one-week pass is the requirement,
the work is **more signals** (new rules / additional markets with their own luck
screens), not higher risk per trade.

---

## 2026-10-26 (d) — the sweep that found a bug, and the three rules that survived it

**The bug first, because it invalidates (c).** In `simulate()`, the loop variable holding
`entry` (`"same_open"` / `"next_open"`) was overwritten with the fill price on the first
trade. Every subsequent trade in a run therefore fell through to the `next_open` branch
and entered a day late. Any rule whose signal *is* the open — `open_break`,
`fade_trend_day`, `continue_trend_day`, `monday_gap_fade`, `nr_break`, `inside_day` — was
silently handicapped from its second trade onward. The same shadowing bug existed in the
coin-flip sampler. Both fixed by reading the flag once into `same_open` and using a
separate price variable.

Impact: the six-market sweep went from **4 of 51** rule/market pairs positive in both
directions to **11 of 51**. Everything reported before this entry is superseded.

**The sweep.** 22 symbols × 9 rules = **198 combinations** on daily bars 2009-2026, micro
contract costs (commission + 1 tick each side), each rule validated **both ways**:
parameters chosen on 2010-2020 then measured on 2020-2026, *and* chosen on 2020-2026 then
measured on 2010-2020. Survivors then had to beat 500 random-entry versions of themselves
with the same stop and the same number of trades in *both* halves.

Universe: NQ, ES, YM, RTY, GC, CL, ZN, ZB, 6E, SI, HG, NG, ZC, ZS, BTC-USD, ETH-USD,
QQQ, SPY, IWM, GLD, TLT.

| Gate | Survived |
|---|---|
| positive in both directions of time | **24 of 198** |
| …and beat 500 random versions in both halves (p<0.05 each) | **3** |
| …and affordable at $25k with whole contracts | **2** (soybeans needs $535 of risk per contract) |

With 198 shots, expected false positives at p<0.05 in both halves is about 0.5, so 3 is
roughly six times chance — encouraging, not proof.

### The three that cleared everything

| Symbol | Rule | Params | Fwd test | Bwd test | coin flip p (fwd/bwd) | Trades |
|---|---|---|---|---|---|---|
| NQ=F | fade after trend day | trend 1.5 ATR, stop 0.5 ATR | +6.27R | +9.11R | **0.042 / 0.008** | 9 / 10 |
| YM=F | fade after trend day | trend 1.5 ATR, stop 0.5 ATR | +8.70R | +6.88R | **0.022 / 0.038** | 20 / 15 |
| ZS=F | NR7 breakout at the open | lookback 7, stop 0.5 ATR | +16.21R | +21.21R | **0.032 / 0.004** | 85 / 66 |

Rule description, precisely: `fade_trend_day` = if yesterday's range ≥ 1.5 × ATR14, fade
today's open (short after an up-trend day, long after a down-trend day), stop 0.5 ATR
from the fill, exit at today's close. `nr_break` = if the last 7 sessions form the
narrowest range of the last 7, buy a break above the previous day's high / sell a break
below its low at the open, stop 0.5 ATR, exit at the close. No target on either.

### What nearly passed, and why it is not in the portfolio

- **ES inside_day** +13.41R / +6.50R, p 0.006 / **0.080** — strong but misses the luck gate
  in one half. Inside day + 6.5R forward is tempting; it is one gate short.
- **ZC open_break** +1.71R / +21.33R, p 0.074 / 0.000 — the corn edge is entirely in the
  first half. That is a regime, not an edge.
- **BTC continue_trend_day** p 0.002 / 0.146 — 11 forward trades. Too few to say anything.
- **NG fade_trend_day** p 0.338 / 0.002 — the mirror problem.

### Parameter neighbours (full-history R, same stop)

    NQ fade_trend_day   1.2=+12.2R   1.5=+15.4R   2.0=-4.0R
    YM fade_trend_day   1.2=+15.6R   1.5= +3.7R   2.0=-5.4R
    ZS nr_break         5  =+28.4R   7  =+26.5R   10 =+37.4R

NQ and soybeans are stable across neighbouring settings. **YM is the weak one**: the 1.5
setting that passed is its *second-best* neighbour, and 2.0 loses money. A rule that only
works at one setting is a coincidence, so YM comes with a downgrade — kept for trade
frequency, at reduced size, flagged as the first thing to cut.

### Sizing: the constraint nobody mentions

At $25,000, risking 1% ($250) per trade, **one contract often does not fit**:

| Instrument | Average risk per contract | Fits in 1% ($250)? |
|---|---|---|
| MNQ | $216 (but 150 pts × $2 at recent vol = $300) | sometimes |
| MYM | $110 | yes |
| ZS (soybeans) | $535 | **no** — 172 of 181 signals skipped |

So the honest account experiment (`trading/target.py`, whole contracts, one position per
symbol at a time) looks like this:

| Risk/trade | Trades taken | Skipped | Final | Max DD | Median months to +5% | −10% breaches |
|---|---|---|---|---|---|---|
| 1% | 42 | 176 | $27,183 | $1,130 (4.5%) | 15.2 | 0 |
| 2% | 163 | 55 | $43,387 | $4,783 (19.1%) | **10.8** | 3 |
| 3% | 206 | 12 | $70,254 | $11,884 (47.5%) | 5.9 | — |

Read the middle row as the real answer and the bottom row as the warning: 3% turns +5%
into a five-month job and a 47% drawdown, which is exactly how the accounts in the video
died. Median time to **+$1,250 is about 11 months at 2% risk**, with a 19% worst
peak-to-trough along the way, and with the edge **halved** (`--haircut 0.5`) it stretches
to 20 months and still gets there.

### Correlation

    NQ fade  vs YM fade   r = +0.39
    NQ fade  vs ZS nr_break   r = +0.04
    YM fade  vs ZS nr_break   r = +0.05

NQ and YM are correlated (same asset class, same idea) — they are one bet with two
receipts, not diversification. The soybeans rule is genuinely independent, which is why
it is worth keeping despite being unaffordable in a $25k account today.

**Verdict.** Three rules cleared every gate. Two are tradeable at this account size, both
from the same family on correlated indices, which means the account's real risk is
concentrated in one idea. Median 11 months to +5% at 2% risk with a 19% drawdown is a real
plan and not a money printer. Forward testing started 2026-10-26 (`trading/forward.py`).

**Next, in order of expected value.** (1) Find an affordable, uncorrelated rule — soybeans
has the statistics but not the price of admission; the ETF/crypto universe (fractional
sizing) or a soybean *mini* would unlock it. (2) Test `inside_day` on ES with more
coin-flip draws, since it missed the luck gate by 0.03 in one half with a +13R result.
(3) Re-run the sweep on intraday bars once paid 1-minute data exists — every rule here is
daily because free intraday history is 60 days.

---

## 2026-10-26 (b) — the video's three claims: open breakout, hold to close, fade the trend day

**Idea under test.** The two videos make specific, checkable claims. Tested on daily
bars 2010-2026 with `trading/breakout.py` — enter at the open, stop 1 ATR, **hold to
the close, no target**, micro-contract costs included (commission + 1 tick each side):

1. Break out of yesterday's range at the open → hold to the close.
2. After a day whose range exceeds 1.5 ATR, a breakout **in the trend's direction** is
   worth nothing, while a breakout **against** it is the strongest trade.
3. It only works on the Nasdaq.

| Market | Rule | In-sample | Out-of-sample | Verdict |
|---|---|---|---|---|
| NQ | open breakout | 106 tr, 50.9%, **−6.06R** | 110 tr, 50.0%, **+1.17R** | No edge (p 0.30) |
| ES | open breakout | 114 tr, 40.4%, −8.45R | 115 tr, 48.7%, +6.05R | Failed in-sample |
| GC | open breakout | 949 tr, 34.9%, −49.18R | 107 tr, 55.1%, +7.97R | Failed in-sample |
| CL | open breakout | 114 tr, 46.5%, −8.03R | 104 tr, 39.4%, −9.14R | Dead |
| RTY | open breakout | 24 tr, 45.8%, −0.74R | 93 tr, 44.1%, **−12.23R** | Dead |
| **NQ** | **fade after trend day** | 10 tr, 50.0%, **+5.14R** | 9 tr, 77.8%, **+2.82R** | **Both windows positive**, p 0.077 |
| ES | fade after trend day | 10 tr, 50.0%, +3.89R | 10 tr, 60.0%, +0.52R | Weakly positive, p 0.29 |
| GC | fade after trend day | 44 tr, 40.9%, +1.77R | 10 tr, 40.0%, **−1.86R** | Failed |
| CL | fade after trend day | 11 tr, 45.5%, −1.37R | 13 tr, 46.2%, −0.81R | Dead |
| NQ | **continue after trend day** | 10 tr, 50.0%, +0.22R | 9 tr, 11.1%, **−3.97R** | **Dead**, p 0.99 |

**What it means.** Claim 2 and claim 3 reproduced: after a big day, the continuation
breakout is worthless (p 0.993, 1st percentile — random did better than it), and the
fade only holds on the Nasdaq, exactly as claimed. Claim 1 as stated — any open
breakout, held to the close — does **not** work: it loses or breaks even on four of
five markets.

**The one candidate, stressed.** Fade-after-trend-day on NQ, across the parameter grid
(trend threshold × stop):

| trend threshold | stop 0.5 ATR | stop 1.0 ATR | stop 1.5 ATR |
|---|---|---|---|
| 1.2 ATR | IS +6.28R / OOS +5.94R | +3.53 / +3.67 | +2.75 / +2.99 |
| 1.5 ATR | +9.11 / +6.27 | +5.14 / +2.82 | +2.95 / +2.98 |
| 2.0 ATR | −2.07 / −1.98 | +0.12 / −0.80 | −0.25 / +0.64 |

Six of six combinations at 1.2 and 1.5 are positive in **both** windows — that is not
one lucky cell. The 2.0 row collapses to 2-3 trades, which is noise, not evidence.

**Coin flip, 1000 random runs, best setting (1.2 ATR / 0.5 ATR stop):**

| | Trades | Net R | Win rate | p-value | Percentile |
|---|---|---|---|---|---|
| In-sample | 16 | +6.28R | 37.5% | 0.082 | 92nd |
| Out-of-sample | 26 | +5.94R | 46.2% | 0.102 | 90th |

**Verdict: the best candidate found so far, and still not proven.** Positive in both
windows, robust to parameters, beat 90-92% of random entries — but p is 0.08-0.10, not
under 0.05, because 42 trades is not enough to separate skill from luck. That is a
forward-test candidate, not a funded strategy. It would need roughly a year of live
paper trades (one or two a month) before the number means anything.

**In dollars, starting at $25,000 with 2 micro contracts** (`--equity 25000 --contracts 2`):

| | Trades | Final | Return | Max drawdown | Worst single |
|---|---|---|---|---|---|
2010-2026 | 42 | **$31,720** | +26.9% | $3,672 (11.0%) | −$1,230 |
IS 2010-2020 | 16 | $25,508 | +2.0% | $853 (3.3%) | −$294 |
OOS 2020-2026 | 26 | $31,212 | +24.8% | $3,672 (11.2%) | −$1,230 |

Average risk per trade: **$496** (2.0% of the starting balance). Longest losing run: 4
trades, **−$2,635**.

Year by year (this is the part that matters):

```
2011    1     -70      2018    1    -126      2023    2  -1,022
2012    2    +178      2019    5      -9      2024    2    +594
2013    1     -93      2020    6  +4,394      2025    6    -510
2014    1    -146      2021    2  +1,621      2026    3    +954
2015    3     +30      2022    5    +180
2016    2    +745
```

**Read that again: +$4,394 of the +$6,720 total came from 2020 alone.** Ten years of
2010-2019 produced +$508 combined. The rule is positive in R in both windows, so it is
not purely a 2020 artefact — but the dollar result is one violent year plus interest,
because a 0.5 ATR stop on 2022 volatility risks four times what the same stop risked
in 2013. Same rule, same 2 micros, wildly different dollars.

**What that means for a 25k account:**

| Sizing | Final | Max DD | Longest losing run | Prop-firm safe? |
|---|---|---|---|---|
2 micros | $31,720 | $3,672 (11.0%) | −$2,635 | **No** — most 25k evals trail $1,500 |
1 micro | ~$28,360 | ~$1,836 (7.3%) | ~−$1,317 | Marginal |

A personal cash account can hold 2 micros through an 11% drawdown. A 25k prop
evaluation cannot: a −$2,635 streak breaches the trailing limit before the edge has a
chance to show up. That is the same trap the video described — right strategy, wrong size.

**Cost model note.** The first run of this test was wrong: it charged MNQ commissions
against crude oil's 1000-barrel point value, turning a 0.05R cost into 1.5R and
inventing a disaster on CL and GC. Per-market contract specs are now explicit in
`MARKETS`. If a result ever looks absurd, check the cost arithmetic first.

**Next.** Forward-test the fade on NQ (one signal or two a month, so it needs patience),
and meanwhile test the second half of the videos' finding — the *first move of the day
without a hard pullback* — which needs intraday data and therefore a data source beyond
the ~60 days Yahoo will serve.

---

## 2026-10-26 — structure + premium/discount continuation, 5 futures

**Idea.** Trade a break of the last N-bar swing only when price is outside a
premium/discount band around the session midpoint; stop at k×ATR, target at m×R,
hold at most 20 bars. One parameter set per symbol, chosen on 2010-2020 only, then
the 2020-2026 door opened exactly once.

| Symbol | Params (struct/band/sl/tp) | In-sample | Out-of-sample | Coin-flip | Verdict |
|---|---|---|---|---|---|
| NQ=F | 30 / 5.0 / 1.0 / 2.0 | 24 tr, 50.0%, **+12.00R** | 9 tr, 33.3%, **+0.00R** | p **0.527** (beat 47%) | **Dead.** No edge, and it stops working out of sample |
| ES=F | 30 / 0.0 / 2.0 / 1.5 | 24 tr, 58.3%, +7.51R | 23 tr, 30.4%, **−6.00R** | not run (already negative OOS) | **Dead.** Degraded from profit to loss |
| GC=F | 80 / 0.0 / 1.0 / 2.0 | 71 tr, 40.8%, +10.43R | 35 tr, 28.6%, **−8.47R** | not run (already negative OOS) | **Dead.** Same pattern |
| CL=F | 80 / 10.0 / 2.0 / 3.0 | 37 tr, 56.8%, +9.51R | 27 tr, 48.1%, **+6.59R** | p **0.197** (beat 80%) | **Held, but no edge.** Random entries matched it |
| NKD=F | 80 / 5.0 / 1.0 / 2.0 | 56 tr, 46.4%, +21.11R | 32 tr, 43.8%, **+10.66R** | p **0.080** (beat 92%) | **Closest to real.** Still above the 0.05 bar — promising, unproven |

**What this says.** Two of five rules survived the out-of-sample door; neither beat
random entry at p < 0.05. The one you care about, NQ, went from +12R to zero.

**Note on NQ.** Those nine out-of-sample trades are one to three months of a
single-symbol daily series. That is not enough data to prove an edge *or* to disprove
one — it is enough to say "do not fund this."

**Paper trading, 5-minute NQZ2026, 400-bar replay (2026-10-23 → 10-26):**
5 trades, 40% wins, **+0.80R**, equity $25,000 → $25,071. One short carried the whole
sample (+1.96R); without it the desk is down. Too small to mean anything.

**Next idea, not yet tested.** The video's own finding was that breakouts early in
the session, held to the close with a tight stop and *no* target, beat everything
else on NQ specifically. That is a different shape (intraday, no TP, news-open
filter) and it should be tested on its own, on 2010-2020, before anything else.

---

## 2026-10-26 (g) — the five December contracts, and what a coin-flip win rate is worth

**Question.** Can the desk trade NQZ2026, ESZ2026, GCZ2026, CLZ2026 and NKDZ2026, and
can it be made to win "a coin flip" while earning the most money?

**Method.** `trading/edge.py` crosses 9 entry rules x 2 parameter sets x 4 stops x 6
targets x 5 max-holds on each of the five front-month feeds — 9,288 eligible settings —
and scores every one on both halves of history. Then it does the thing that matters:
it chooses a setting using ONE half and scores the half it never saw, once in each
direction. Finally it replays the five as one $25,000 book against the real $1,250
target with EOD trailing drawdown and the 50% consistency rule.

**Result 1 — win rate is cheap, expectancy is not.** 2,942 of 9,288 settings won at
least 50% of the time. Only 499 of those (17%) made money in both halves. The highest
win rate found anywhere was 92.9%, on ES `inside_day` 1.5/0.5/10, averaging +0.21R over
42 trades in seventeen years: a target one third of the stop wins often and pays little.

**Result 2 — one setting does both.** ES `inside_day`, 0.5 ATR stop / 1.0 ATR target /
5-bar hold: **58.1% win, +0.62R average, +26.7R over 43 trades, positive both halves
(+14.1R early, +12.6R late), coin-flip p < 0.01.** This is the follow-up the previous
entry's "test ES inside_day harder" item asked for, and it passed.

**Result 3 — the blind selection test.** Chosen on 2009-2019, scored on 2020-2026:
ES fade +9.3R, CL fade +4.0R, NKD continue-trend +13.4R; NQ -4.4R and GC -16.6R failed.
NKD `continue_trend_day` 0.5/3.0/5 was selected **identically from both directions**,
the strongest single result in the study.

**Result 4 — the number that overrides the rest.** With settings frozen on the early
half and the account run only on 2020-2026: **38 trades, final $24,603 from $25,000,
-0.2%/yr, 51 signals skipped** because one contract's stop did not fit the budget. The
+8.4%/yr available from full-history settings is hindsight. Out of sample the book does
not compound, which repeats what entry (e) found on the $2,500 account.

**Result 5 — affordability is the binding constraint, not accuracy.** Typical stop on
one contract at $25,000: MES $199, MCL $218 (both fit a 1% / $250 budget); MNQ $478 and
MGC $490 do not; **NKD $3,946 = 15.8% of the account.** The best-measured signal in the
study cannot be traded at this size. The flat equity curve is a sizing problem wearing
a statistics costume.

**Result 6 — $1,250 in one week.** Replaying every historical week: 3.0% of starts pass
at 1% daily risk; 4.9% at 2%, with 35% breaching the $1,000 limit first. The basket
produces ~37 signals a year, so a week contains ~0.7 of a signal. More risk does not
create trades — this repeats entry (f) with a wider market set.

**What changed in the codebase.** `trading/edge.py` (the sweep + blind test + account
replay), `trading/basket.py` (live forward paper ledger using only the settings that
survived, with resting-order output for phone execution), `trading/START-HERE.md`
(beginner walkthrough), `trading/edge.json` (full results).

**Honest verdict.** The five-contract basket is better than the old three-market desk on
every measure — more signals, higher win rate available, one genuinely robust rule — but
at $25,000 it still does not compound out of sample. Do not quote +8.4%/yr; quote
-0.2%/yr and treat the forward ledger as the only remaining evidence.

---

## How to read this file

- A positive in-sample number means nothing on its own. It is the cost of admission.
- A positive **out-of-sample** number is interesting.
- A positive out-of-sample number that **beats random entry** at p < 0.05 is the only
  thing that earns paper money, and paper money is the only thing that earns real money.

## Tally

Ideas tested: **9** rule families, 3 specific video claims, across **22 markets** — 198
rule/market combinations, plus ~600 parameter variants within them, plus **9,288
exit combinations** on the five December contracts (entry 2026-10-26 (g)).
Survived both directions of time: **24 of 198**.
Beat 500 random-entry versions in both halves at p<0.05: **3** (NQ fade, YM fade, ZS NR7).
Affordable at $25,000 with whole contracts: **2**.
Cleared every gate: **3 statistics, 2 practical**.

Earlier entries in this file (2010-2020 single-split results) were produced with a bug
that entered open-based rules a day late; see the 2026-10-26 (d) entry. Their *direction*
holds, their magnitudes do not. Nothing before that entry should be quoted as a number.

## 2026-10-29 (h) — six bots, 300 readers, and four bugs that changed numbers

**Why this entry exists:** the previous entries measured signals. This one measures
a *pipeline* — where the signal is scored, read against verified news, planned,
risk-gated, executed and rendered — and records what broke while building it.

**Built.** `bots.py` (six bots, BOT 5 final / BOT 2 delay-only / BOT 3 no veto),
`swarm.py` (300 readers over 20 public feeds), `research_engine.py` (spec + the eight
refusals + improvement loop), `execution.py` (order lifecycle, risk gate, kill
switch), `montecarlo.py` (10k block bootstrap), `dashboard.py` (static page, CSP).
`DESK.md` documents all of it.

**Measured.**
- Swarm, live: 2,595 item checks, 16/20 feeds reachable, 23 fresh + 37 context kept,
  1,265 stale / 45 duplicate / **5 future-dated** / 5 undated rejected.
- Research engine: CL `fade_trend_day` 0.5/3.0/2 → +0.548R all history, **+0.336R
  after 2020, p=0.128, t=0.64 → REJECT**. A profitable-looking rule correctly
  refused at twelve out-of-sample trades.
- Execution, 45 sessions: 3 orders, 3 closed, 18 transitions, +1.41R. Three trades
  prove plumbing, not edge.
- 10,000 replays, **honest set** (ES fade + CL fade, i.e. the rules that never saw
  the data they are judged on): mean +0.196R, **74.9%** reach +$1,250 before a fixed
  −$1,000, 24.8% breach, median 36 trades, 95th-percentile drawdown $1,815.
- Same file without `--honest`, 41 trades: 98.0%. That is hindsight and the flag
  exists to name it.

**Corrections to earlier work, none of which changes a published verdict:**
1. Swarm dedupe was global rather than per market, so a story about both the S&P and
   the Nasdaq only counted once. Now keyed `market:hash`.
2. The first Monte Carlo returned 99.8% because it bootstrapped the same trades that
   selected the parameters. Default is now the holdout window; `--all` restores the
   hindsight run with a warning.
3. Execution counted "orders already sent today" across nineteen years, rejecting
   511 historical trades against a one-day cap. Scoped to recent sessions, per
   simulated date.
4. Execution reported 15–106 ticks of "slippage" by comparing the 18:00 Globex open
   with the 09:30 print. A paper fill deals where it is told; slippage is an
   assumption (one tick per side, inside every R), not a measurement. Stated, not
   faked.

**The finding that matters for the prop firm:** one MES win at a 6:1 bracket pays
~$967. Lucid's 50% consistency rule caps a best day at $625 on a $1,250 target, so
a single full win voids the pass *even when the target is reached*. Either the
target must be ≥ 2× the win (~$1,934), or the exit must be partial (~$480–$625) and
the reduced bracket (~2.5:1) re-backtested. Until then the $1,250 evaluation is
arithmetically incompatible with this bracket, and the trailing drawdown (18.8%
pass rate, 114/207 breaches) is the stricter constraint anyway.

## 2026-10-29 (i) — the desk grows to thirteen bots, and gets an audit trail

**Why:** six bots covered one trade. They did not cover the market the trade lives
in, the hour it is taken, the liquidity it is dealt into, the contract it is quoted
against, whether the whole desk should be allowed to trade at all, or whether any of
the bots have been right. Seven more bots and an analytics pass close that gap.

**Added.** `0 regime`, `7 session`, `8 liquidity`, `9 roll`, `10 benchmark`,
`11 calibration`, `12 governor` in `bots.py`; `trading/analytics.py`; call history in
`desk/calls.jsonl`; analytics and dashboard sections; workflow step.

**Authority is now explicit and ordered.** BOT 2 delays a session, BOT 5 rejects a
trade, BOT 9 refuses new risk within three days of a roll, BOT 12 halts every market.
BOT 6 may not override any of them, and `validate_call()` still fails malformed
output to SKIP.

**First 13-bot board (2026-10-29).** ES: regime `drift` (50/200 gap +4.3 ATR,
20-bar slope +0.7 ATR, ATR 44th percentile), opportunity 35 (pullback at the 20 EMA),
liquidity 97/100, session overnight 13:27Z, roll in 41.4 days, governor `run`,
risk approve 1 MES at $207, final **WAIT 52**. CL: **WAIT 16**, regime `drift`.

**Analytics, first run.** 0 forward trades, 4 shadow decisions, 5 logged calls — so
every table prints "no data yet" and says so rather than inventing a win rate. The
calibration joins calls to outcomes as trades settle; under ten pairs it refuses.

**Method note.** The regime classifier is three measurements the market supplies
itself — volatility percentile, 50/200 separation in ATRs, 20-day range against the
60-day — not a fitted model. That keeps it inspectable, and it means a wrong regime
call can be traced to a number rather than to an opinion.

## 2026-10-30 (j) — the 15m book is retired, and the account changes hands

**Why:** the intraday book was losing about $6.65 a trade. Re-tested against random
entries with the identical stop, target, hold limit, session filter, frequency and
costs, it cannot be told apart from a coin flip — GC at the 32nd percentile of 1000
random runs (p = 0.68), CL at the 21st (p = 0.79). Two defects sat underneath that:
`paper_aggressive.step()` never implemented the `cool` parameter, so the desk took 82
trades on CL where the tested rule takes 63, and GC halted at the $1,000 buffer, so
its record was truncated as well as off-rule. `retest-intraday.md`, commit `377c1d7`.

**Removed.** `.github/workflows/paper.yml`. The ledger and both pages stay exactly as
they were; a closed book is not a deleted one.

**Promoted.** `trading/pick_book.py` scores every remaining daily candidate on the
account's own rules — $25,000, a static $24,000 floor, +$1,250 to pass, 40%
consistency — from *every* starting trade rather than from one flattering window.

**The result that decided it.** NQ `nr_break-2` 1.0A has the best expectancy on the
page (+$122 a trade since 2023) and it fails the consistency rule: one stop is now
$1,054, which is the entire buffer, and one such winner against a $1,250 target is most
of the profit. It keeps the best day under 40% only **23%** of the time. Halving the
stop to 0.5A destroys the edge instead of rescuing it (−$34 a trade, 41% win), which is
the useful proof that stop distance is part of a rule, not a dial on it. Pairing the
two books fails the same way for the same reason (38% with consistency against 95%
without).

**Chosen.** ES `nday_fade-5` 0.75A tp1: 90% of starting points since 2023 pass with the
consistency rule intact, $309 of risk per session (three stops to the floor), 7% of
attempts breach, median 29 sessions to the target. Book replaced in
`desk/oracle-book.json`; the forward record starts with the next session because
2026-10-30 was already most of the way through when the book changed.

**Re-tested on the live path.** `python3 trading/paper_oracle.py --replay 40` on the new
book: 15 trades, 60% win, **+$1,142.28**, worst drawdown −$637, best day 27% of profit.
That is 91% of the target in 40 sessions, and unlike the +$4,530 the old book showed on
the same window, it is not one big day doing the work. `desk/pick-book.md`.

## 2026-10-30 (k) — the floor was wrong, and the desk is a portfolio

**Correction, and it matters.** Lucid Flex does not run a static $24,000 floor. Its own
drawdown rule page puts the max loss limit $1,000 under the **highest closing balance**
and stops moving it once it reaches $25,100 — an end-of-day *trail*. Every pass rate in
entry (j) was measured on the static line, so every one of them was too generous.
`pick_book.account()` now walks the trailing floor. The same book, measured again:
ES `nday_fade-5` 0.75A **78%** of starting points since 2023 pass with consistency
(was 90%), **19%** breach (was 7%), median 26 sessions. The 0.5A variant is now *better*
on both counts — 80%, 13%, 36 sessions — and only gives up speed. The conclusion
survives (the ES fade carries the account, NQ `nr_break-2` still cannot clear 40%
consistency at 23%) but the cushion I claimed for it did not exist.

**The question changed.** "Which rule passes one evaluation" is not the business. The
business is ten accounts, five of them funded, fees recycled, some accounts dying, and
payouts taken whenever the rules allow. `trading/portfolio.py` simulates that: real
63-session windows from 2023 onward, five evaluation slots plus five funded slots, the
trailing floor, 40% consistency in evaluation only, and the actual payout gate — five
separate days at $100/$150/$200/$250 profit, a $500 minimum, at most 50% of profit,
capped at $1,000/$2,000/$2,500/$3,000, 90% to the trader, five payouts per account.

**What decides the money is the account size, not the rule.** A 25K pass is $1,250 of
profit, so the 50%-of-profit rule caps the first request near $625 and the floor then
locks at $25,100 with a few hundred dollars of room. At one micro the whole desk returns
a mean of **+$207** over ninety days, positive in **16%** of windows — the conservative
setting from entry (j) is the worst line on the page. The same 25K account at two micros
is worth **+$1,632** (40% positive) for the same $460 of capital.

**The pick.** $50K accounts at four micros: **+$3,632** mean per ninety days on **$815**
of capital, median −$805, p90 +$17,195, positive in **42%** of quarters, opening ~6
accounts and passing ~4. Over six months the same line averages **+$8,503** with a
median of **+$2,403** and 59% of windows in profit. That last pair is the honest shape
of this: at ninety days the median window has not yet paid back its fees, and at six
months it has.

**Most money, if that is the only criterion.** $150K at nine micros: **+$14,569** mean
over six months (median +$4,989), but positive in only **30%** of ninety-day windows and
a worst tenth of six-month windows at −$2,290, which is the whole fee budget. It is the
same edge carried bigger, and
refused here because a desk that loses money in seven quarters out of ten is a desk you
stop funding before it gets to the good one.

**Three days is not a thing this rule does.** Lucid's three-day minimum needs the whole
target inside three sessions; **0%** of passes at any size on this page arrive that fast,
18% arrive within ten sessions at the fastest line, and the median is 30 sessions.
Bigger size raises the dollars at both ends of the clock, not the speed.

**Not modelled.** Intraday breach (a session that trades through the floor and closes
above it is scored as survivable), partial fills beyond one tick of slippage, promotions
that cut fees, and the looser reading of the payout page — it says "50% of your balance"
in one place and "50% of profit" in its table, and the stricter reading is used
throughout. `desk/portfolio.md`, `desk/portfolio.json`.

## 2026-10-30 (l) — going back to the trio, and what the good window was worth

**The request.** The 29 October table — narrow-range breakout + prior-day breakout + five-day
fade, 65 trades, +$13,273 in forty sessions — was the best thing the desk has ever printed,
and the ask was to go back to it and take the most profit available as fast as possible.
Rather than argue about it, the trio is now a portfolio line in `portfolio.py`, run over
every 63- and 126-session window since 2023 like everything else.

**It wins, and not because of that window.** The trio at one micro a rule averages $127.50 a
session. Its 40-session windows have a **median of +$4,588**, a best of $14,167 and a worst of
−$4,647, and the window that was traded — $12,598 when rebuilt from the same three rules —
sits in the **98th percentile**. So the table was a hot tape, not a hot rule: each of the
three legs is individually in its own 90th percentile over it. It still beats everything else
tested, because the ES fade's median 40-session window is $602 and the trio's is $4,588. The
edge is in the ordinary window, which is the only kind you can plan for.

**The money.** At $50K with one micro a rule: mean **+$6,834** per quarter, median **+$4,250**,
positive in **71%** of quarters, 5.5 payouts — the only line on the page whose median quarter
is positive. At $150K with two micros a rule: mean **+$8,080** a quarter and **+$34,640** over
six months with **96%** of six-month windows positive. That is the pick if the question is
literally "most profit", and it costs $2,290 of fees to staff rather than $815.

**The cost, stated where it cannot be missed.** The trio risks $1,158 in an ordinary session
and $1,769 if all three legs stop on one day. Against a 25K's $1,000 that is not a book, it is
a coin flip; the $50K is the smallest account that holds it and even there a three-leg stop is
88% of the buffer. `desk/account.json` is now a **50K** and `paper_oracle.py` reads the buffer
and target from it instead of hard-coding a 25K — the old constants would have scored the new
book against the wrong account. The forward page's own worst-case line, printed rather than
buried: **$2,159 against a $2,000 buffer** if every standing order fills and stops.

**Desk state.** `desk/oracle-book.json` is the three NQ legs; the ledger is reset with
`last = {"NQ=F": "2026-10-30"}` so the forward record starts with the next session, as it did
when the 15m book was retired. The rebuilt 40-session replay is $12,598 against the $13,274
that was posted — one fewer `nr_break` trade and revised bars — so treat those two figures as
the same number to within $700, not to the cent.

**Three days.** Still no. 1% of passes at best arrive inside three sessions, 23% within ten,
and the pick's median pass is 33 sessions. The trio is the fastest book tested and it is not
fast enough to be a three-day plan.

**Assumptions that carry the six-month numbers.** Payouts are requested at the maximum the
rules allow the moment an account qualifies; the floor locks at start + $100 after a payout,
which is what makes a funded account nearly risk-free once it has paid; breaches are scored on
the close, not on the session's worst moment; windows overlap, so 600 runs are worth far fewer
than 600 independent trials. If the payout rule is stricter than modelled, the funded half of
these numbers shrinks and the evaluation half does not.

## 2026-10-31 (m) — the 25K answer is ES, and the Oracle rule is dead

**The ask.** Back to a 25K for now, paper only until 13 November, and find the rule set with
the highest chance of passing — `prevclose_break` ("Oracle"), 2.0 and 2.5 ATR stops, `nr_break-2`,
two-rule and three-rule books, whoever wins. Explicitly: drawdown is not the constraint, pass
rate is, and an account that blows after banking cushion is acceptable.

**The grid.** `atr_grid.py` — 144 lines, four rules × six stops (0.5 to 2.5 ATR) × three exits ×
ES and NQ at one micro, trade record from 2023. Each line is then walked through the actual
evaluation — $25,000, +$1,250 target, $1,000 end-of-day trailing floor locking at $25,100, 40%
consistency — from *every* starting trade, and books of two and three rules are built from the
lines that survive, with overlapping trade shapes excluded.

**The stop question, answered.** Win rate does rise with the stop — 43% at 0.5 ATR, 54% at 1.0 —
and then it flattens (52% at 1.5, 2.0 and 2.5), while the share of trades stopped out falls from
39% to 0%. Pass rate follows the opposite of the intuition: 25% at 0.5 ATR, 52% at 1.0, 57% at
1.5-2.0, and no better beyond. A wider stop buys win rate by making each loss bigger, and on a
$1,000 buffer that trade is roughly one-for-one, so it buys no extra chance of passing.

**`prevclose_break` is dead at every stop.** 944 ES trades since 2023: 47-48% win, **-$7 to -$16
a trade**, 14-36% pass, 65-90% breach. On NQ it is 50% win and about +$5 a trade with a $1,440
stop. The 93% win rate it showed once was the sample artefact already suspected — it only
survives if you drop the sessions where both orders fill, which is exactly the look-ahead that
made it look perfect. It is out at 0.5, 0.75, 1.0, 1.5, 2.0 and 2.5 ATR.

**NQ cannot pass a 25K, for a boring reason.** One micro of NQ at a 1.0 ATR stop risks $1,054 —
the whole buffer — and at 2.0 ATR it risks $2,108. NQ `nr-break-2` at 2.0 ATR reaches the target
90% of the time and satisfies the consistency rule 23% of the time, because a single $2,000 day
is more than 40% of a $1,250 target. The rule is fine; the account is too small for the contract.

**The winner.** MES, two rules, one micro each: `nday_fade-5 0.5A tp1` + `nr_break-2 1.0A tp1`.
896 trades since 2023, 59% win, +$36 a trade, and **88% of starting trades pass with the
consistency rule intact** — against 80% for the best single leg — with **7% breaching**, a median
session risk of $405, and a median of 26 sessions to the target. Both legs stopping on one day
costs about $618, so the buffer holds two bad sessions rather than one.

**Desk state.** `desk/account.json` back to a 25K with the plan recorded in it: when the 25K has
banked cushion, either fund it to +$2,000 or buy a 50K, because 50K is the smallest account that
holds the 2.0-2.5 ATR stops and the NQ lines at two micros. `desk/oracle-book.json` is the two ES
legs, the ledger is reset to 30 October, and the 40-session replay is **34 trades,
$+1,149, 59% win, worst drawdown $-510** — half the buffer — with the best day
$280 at 24% of profit, inside the 40% rule. The forward page's worst
case for the next session is one order and one stop: **$236 against $1,000**.

**What the replay does not promise.** $1,149 over forty sessions is $29 a
session and the target needs $1,250, so this book passes in about five weeks of sessions, not five
days. That is the price of the 88% pass rate, and it is the right trade for a 25K: the fast books
exist, and they are the ones that breach.

## 2026-10-31T04:45Z — wide sweep: 287,280 configurations across five markets

- space: 57,456/market (38 rule variants x 7 stops x 4 exits x 54 filters)
- gates: unseen years, plateau, 2025 regime, 500-run luck (same days/side/stop/exit), ≥100 trades
- 9,629 positive in both halves, 289 through every gate (chance would pass ~30)
- book: ES=F nday_fade-3 1.0A tp05 long
- book account: pass 89%, with consistency 89%, ≤3 sessions 0%, breach 10%, median 43 sessions

## 2026-10-31T04:47Z — wide sweep: 287,280 configurations across five markets

- space: 57,456/market (38 rule variants x 7 stops x 4 exits x 54 filters)
- gates: unseen years, plateau, 2025 regime, 500-run luck (same days/side/stop/exit), ≥100 trades
- 9,629 positive in both halves, 289 through every gate (chance would pass ~30)
- book: ES=F nday_fade-1 1.0A tp05 gapwith long
- book account: pass 91%, with consistency 84%, ≤3 sessions 0%, breach 3%, median 14 sessions

## 2026-10-31T04:48Z — wide sweep: 287,280 configurations across five markets

- space: 57,456/market (38 rule variants x 7 stops x 4 exits x 54 filters)
- gates: unseen years, plateau, 2025 regime, 500-run luck (same days/side/stop/exit), ≥100 trades
- 9,629 positive in both halves, 289 through every gate (chance would pass ~30)
- book: ES=F nday_fade-7 1.5A tp05 long
- book account: pass 92%, with consistency 92%, ≤3 sessions 0%, breach 5%, median 12 sessions

## 2026-10-31T04:50Z — wide sweep: 287,280 configurations across five markets

- space: 57,456/market (38 rule variants x 7 stops x 4 exits x 54 filters)
- gates: unseen years, plateau, 2025 regime, 500-run luck (same days/side/stop/exit), ≥100 trades
- 9,629 positive in both halves, 289 through every gate (chance would pass ~30)
- book: ES=F nday_fade-1 1.0A tp05 gapwith long
- book account: pass 91%, with consistency 84%, ≤3 sessions 0%, breach 3%, median 14 sessions

## 2026-10-31 (n) — the wide sweep picked one ES rule, and three sessions is not on the table

**Idea.** The video's protocol, applied properly: 287,280 configurations (57,456 in each of
ES, NQ, GC, CL, NKD), four gates, then scored on the 25K evaluation from every starting
trade. The user's new objective was speed — $1,250 inside three sessions — with a higher
win rate.

**What survived.** 9,629 configs were positive in both halves; 289 cleared plateau, the
2025 regime and a 500-run random-fill luck test, against ~30 that chance alone would let
through at a 95th percentile. Every survivor in the stored top 60 is `nday_fade`. No
`prevclose_break` ("Oracle"), no gap rule, no inside/outside day, no MA pullback, no pin
bar, no strong-body continuation and no walk-forward ridge model made it. The Oracle is
dead in this data at every stop, again: ES 47-48% win and -$7 to -$16 a trade.

**The book.** ES, long only: buy a stop at the prior day's low, only when the session
opens above the prior close, 1.0 ATR stop, take 0.5R. 820 trades since 2009, **77.7%
win, $49/trade**, worst drawdown $1,086, positive in **all 18 calendar years**. 2023
onward: 204 trades, **80.4% win, $95/trade**. As a 25K walked from all 204 recent
starting points: **91% pass, 84% with the consistency rule intact, 3% breach, median 14
sessions**, $413 of risk in a median session. Full history is 98%/96% at a median of 37
sessions, but that half was traded at a fifth of today's prices.

**The three-session answer.** 0 of 204 starting points reached +$1,250 within three
sessions with the consistency rule intact. 5.4% inside five, 21% inside ten, 57% inside
fifteen. $417 a session for three sessions straight is roughly 1.3R a day at a 60% win
rate, every day; nothing that cleared the gates does that.

**Rejected on evidence, not taste.** The fastest-looking lines in the whole sweep were NKD
`nday_fade` variants (5-6% of starts inside three sessions), but at today's volatility a
1.0 ATR NKD stop is **$5,600-8,700** — six to eight times the buffer. Their good pass rate
came from 2009-2020 attempts made when the index was a fifth of today's level: the stop's
dollar size is a property of the price level, not of the rule. Same trap for NQ: 1.0 ATR
is $1,043 at one micro, so every NQ line fails the $500 session-risk cap that keeps two
bad sessions inside the $1,000 buffer.

**Verdict.** The desk trades this rule from 2026-11-02, paper, one micro. It is faster
(median 14 sessions vs 26) and wins more often (80% vs 59%) than the pair it replaces, at
roughly the same pass rate. It is long-only ES dip-buying, so part of its edge is the
market's own drift and it will look worse in a year that goes down; the 2022 test window
(+$6,218 over 75 trades) is the one that says the rule itself survives a bad tape, not the
drift. Three sessions is a lottery with a $1,000 ticket, and no honest sweep makes it
otherwise.

**Count.** Configurations tested this phase: 287,280. Strategies traded forward: 1.

## 2026-10-31 (o) — independent audit and 30,000 open-entry candidates

**Scope and correction.** This is a focused audit of the current wide sweep, paper
runner, account walk, input sources and major claims, not a line-by-line validation
of every older script. Historic claims in entries (m), (n), the generated wide-sweep
reports, earlier backtests sharing these mechanisms, and the handoff are not proof.
Retain them as a historical record. Their numeric results need independent
recomputation before use. In particular the 77.7% / 80.4% win rates, 84% consistent
pass, 14-session median, +$538.94 replay, and claimed 289 versus 30 chance comparison
must not be relied on. The 0/204 figure cannot establish that a 3-day pass is impossible.

**Concrete findings.**
1. `mine26k.day_trade` / `leg_pnl` evaluate session-wide highs/lows against a target
   after a level entry without knowing if the high/low preceded entry. The claimed
   long buy stop at a prior low is actually modeled as a downward-touch long entry:
   a standard buy stop below market is not that instruction. Test
   `test_legacy_claims_target_even_if_target_precedes_dip_entry` constructs a
   possible price path proving the discrepancy. Even stop-first ties do not fix it.
2. `luck_test` draws a fill using the completed session's range and applies the whole
   session to it, including extremes from before that hypothetical fill. It conditions
   on realized trade days and side. Its reported 100th percentile and the 5%/30
   chance calculation are not a valid multiple-testing-corrected null; choices are
   correlated, preselected on test data, and the null is not exchangeable.
3. The sweep ranks candidates on 2020–2024 outcomes before its other gates; that
   period and 2025+ were repeatedly inspected. They are not untouched holdouts. Only
   the first 120 per market were evaluated by expensive gates; 289 is not a census
   of all candidates. The list of top 60 does not prove all 289 share a family.
4. The original `model_pred` filtered NaN labels, not NaN features, before regression.
   A training matrix with missing features could propagate NaNs into predictions;
   reported failure of the ridge model does not establish that learning models fail.
   The training mask has since been fixed and tested; the old sweep remains invalid.
5. `walk` counts days with trades, not all trading sessions; stops at the first target
   even if consistency fails instead of continuing; updates its trailing high on
   individual legs, not after the session; and lacks intraday equity-floor checks.
   `rolling` uses overlapping starts, mixes unfinished starts into pass denominators,
   and uses a different denominator for breach. Percentages are not independent
   probabilities. `paper_oracle` stops only at initial loss and its displayed room
   ignores a trailing floor. Its settlement cutoff is fixed UTC and not verified for
   DST/holidays. The repository contains a scheduled GitHub Actions workflow for the
   paper runner, but its current enabled status and execution are not established
   from the repository files.
6. The data are Yahoo continuous `=F` proxies, not actual December 2026 contract
   histories or guaranteed tradable prices; sessions, rolls, market liquidity, open
   fills, historical micro availability and fees need verification. The previous
   one-size $1.24 per side assumption is not Lucid's published product-specific
   commission. Spreads, gaps, queue, partial fills and intraday margin/breaches need
   additional treatment. One-tick slippage is an assumption, not a guarantee.

**Action.** Preserved the forward state: 0 trades and $0.00; did not overwrite or
invent fills. Withdrew the stale November 2 order, paused `paper_oracle.py` and the
book-overwriting legacy `mine26k.py` command. No new candidate installed because no
valid improvement was demonstrated. Both pause intentionally without modifying state.
The pause takes effect in this workspace only until committed and pushed; the
remote may still run the old workflow. Workflow existence does not guarantee a run.

**New research.** `audit_search.py` / `desk/audit-search.md`: 30,000 configurations
(6,000 per ES, NQ, GC, CL, NKD) based on 12 prior-bar patterns × five thresholds ×
two comparisons × two sides × five stops × five exits. These are configurations,
not all independent or necessarily distinct strategies. Choose one rule per market
on 2009–2019 only; evaluate the fixed choices on the reused 2020–2024 and 2025+ data.
Bracket outcomes use open entries, stop-first ties, product-specific published
commissions and tick rounding; random-side 500-run Monte Carlo uses the same selected
pre-open days, stops and costs. No multiple-testing claim. Input hashes and full
results are in the report; the exact data snapshots were not retained, so later
Yahoo revisions can prevent reproduction of the hashes. This is exploratory, not
untouched out-of-sample validation, and does not implement a tradeable open execution.
The five frozen test-period random-side p-values are ES .475, NQ .202, GC .611,
CL .645, NKD .226; none beat 5%. Three of five have negative 2020–2024 average
returns. No candidate is validated or installed. The close-only account walk is
sensitivity only, with unfinished and overlapping starts visible; it does not model
intraday breach or price gaps and is not a reliable pass probability.

**Rules check.** Lucid's official 25K Flex page lists $1,250 target, $1,000 max loss,
40% standard consistency (50% paid add-on), 2 minis or 20 micros. Its drawdown page
states lock at $25,100 once the initial trail balance $26,100 is exceeded. It says
reaching the max loss limit breaches, but whether unrealized intraday equity triggers
it is not clear from the official text reviewed: confirm in writing with Lucid.
DLL can be customized; do not assume it is off for this user's account. Source:
https://support.lucidtrading.com/en/articles/12945790-lucidflex-evaluation-account
https://support.lucidtrading.com/en/articles/12945815-lucidflex-drawdown
https://support.lucidtrading.com/en/articles/12945805-lucidflex-consistency-percentage
https://support.lucidtrading.com/en/articles/16226050-lucidflex-customization
https://support.lucidtrading.com/en/articles/11508978-approved-products-and-commissions

**Tests.** `python3 -m unittest discover -s trading -p test_audit_search.py -v` tests
stop priority, pre-open feature causality, session counting, consistency continuation,
previous-close trailing floor, and a counterexample to the old fill model. Compile
checks on affected Python files; intentional command guards verified separately.
The first ad hoc trailing-floor fixture incorrectly expected a $650 loss after a
$600 gain to breach a $1,000 trail; corrected to a $1,050 loss and reran the test.
A genuinely new final holdout, executable specific-contract intraday data, reliable
account and risk logic, and a new forward paper ledger remain necessary before
promoting a strategy. No promise of profitability or three-session success.

## 2026-10-31 (p) — safety pause, rule corrections and outstanding blockers

Both `.github/workflows/oracle.yml` and the distinct hourly `desk.yml` contain a
job-level `if: ${{ false }}` pause. The latter also stops its board, analytics,
dashboard and automated commits. Scheduled events may still appear as skipped;
this is not a GitHub account-level disable and does not cancel already-running jobs.
Neither workflow nor a guard can retroactively cancel real broker orders; this
repository does not establish whether any external order was ever submitted.
Direct `paper_oracle` stepping/watch, desk cycle/board and execution replay now
refuse to run; the original forward/oracle and order ledgers were not rewritten.
Other legacy scripts and reports have not all been audited; do not treat them as
validated or run them to make trade decisions. The old book is marked unvalidated.

The official $25,100 locked floor is reflected in `account.py` and account.json;
`buffer_now` refuses to infer the prior EOD high from today's equity or an
intraday peak, returning zero if either balance or closing high-water is missing.
Existing state does not contain `peak_eod` and has not been silently backfilled.
A $25,100 lock on a 25K profile is not a generalized rule for other accounts.
Account-specific DLL and intraday unrealized-loss breach remain unconfirmed.
The old bot/desk/execution modules incorrectly tried to convert null optional
rails to floats; they now handle absent settings without inventing a DLL or daily
stop. These changes alone do not validate their risk engines. Fixed the
walk-forward ridge's missing/non-finite feature mask; this is not a finding of an
edge and does not rehabilitate the old strategy sweep.

Data-source research: Databento documents exchange-wide CME/NYMEX/COMEX futures
history and dated-contract symbology, including 1-minute bars, at
https://databento.com/docs/datasets/glbx-mdp3 and
https://databento.com/docs/conventions/symbology. Confirm individual NKD coverage,
license and exact costs before acquiring data. An actual December 2026 contract
cannot have a 17-year tradable history; historical studies need older expiry
contracts and an explicitly defined, point-in-time roll process. No vendor was
integrated, no account created and no data purchased. The available Yahoo daily
proxies are insufficient to validate the earlier intraday level-entry strategy.

The simulator is **not repaired or re-enabled**: reliable dated-contract intraday
history, gap and ambiguous-bar treatment, session boundaries, actual firm-specific
rules and truly independent validation remain prerequisites. Fixing all historic
research or guaranteeing a profitable three-day strategy cannot be asserted. Keep
paper-only and preserve the plan to consider a $2,000 cushion or 50K only after
the 25K has banked its cushion.

## 2026-10-31 (q) — what the account permits, and why three days is arithmetic

**Request.** The owner asked for the highest-win-rate book, explicitly accepting the
occasional blown account, and named `prevclose_break`, 2.0-2.5 ATR stops, `nr_break-2`
and two/three-rule books. Those are settled questions (§4, entries (m) and (n)) and are
not re-run here. What was missing was not another sweep but the arithmetic of the
constraint, since every one of those answers is bounded by the $1,000 buffer and the
40% consistency rule rather than by the signal.

**Data blocker, stated plainly.** A causal re-test exists (`trading/edge_causal.py`,
`--selftest` passes) but has **not run**: this workspace cannot reach daily bars.
Yahoo returns HTTP 429 for every window (1y and 20y, both hosts, chunked or not);
WSJ and MarketWatch download endpoints return 401; stooq serves a JavaScript challenge.
No vendor key is configured. The loader caches to `trading/.cache/<sym>.json`; the
first run with data access fills it, and `--csv` accepts any date,open,high,low,close
file. So: **no new backtest numbers this entry.** Anything quoted below is arithmetic
or the retracted record, labelled as such.

**Entry ordering, fixed in code.** For a buy limit below the market (the only legal
reading of "buy the prior-day low" when the open is above it) the engine books a stop
only if the CLOSE is through the stop, a target only if the CLOSE is beyond it, else
exits at the close — a close is always after the entry, so neither can be counted
early. The old high/low comparison is kept as `legacy` purely to measure the bias. Buy
stops above the market (valid orders) keep stop-first ties. A fixture asserts that a
target which trades before the dip is not a win.

**What arithmetic says** (`trading/feasibility.py`, `desk/feasibility.md`; MES, ATR 70
pts, $350 risk at 1.0 ATR, $4.98 round-trip):
- break-even win rate for 0.5R is **67.6%**; for 0.2R it is **84.5%**, and a 0.2R book
  is still negative at an 85% win rate. Max win rate and positive expectancy pull in
  opposite directions; this is the same finding as `edge.py` in §3.
- $417/session at 0.5R and a 78% win rate needs ~8 micros: $2,800 of simultaneous risk
  against a $1,000 buffer.
- 20,000 simulated 25K walks per line, consistency enforced at the moment of passing:
  78% win, 0.5R, 1 micro → 77% pass, **0% within 3**, 13.8% within 10, 23% breach,
  median 14 sessions. 2 micros → 82% pass, 18% breach, median 9. 6 micros → 6.9%
  within 3, 23% breach.
- the 40% rule caps a passing day at $500 = 2.4 wins at 1 micro 0.5R, so a 3-session
  pass needs >=2.1 wins a day with no losing day.
- 2.0 and 2.5 ATR stops cost $700 and $875 on one micro — 70-88% of the entire risk
  budget. They are not available on a 25K at any win rate; on a 50K they are 35-44%.

**Verdict.** Three sessions is a size problem, not a strategy problem, and the size
that solves it is the size that ends the evaluation. The current book is positive only
because of the 78% win rate (break-even 67.6%), which is the exact number the audit
retracted — so the causal run is the gate, not an optional extra. Honest expectation
for 2-13 November on one micro: the rule fires ~0.21 sessions in 5, so ~2 trades,
roughly +$100 to +$200 if the win rate holds, with about a 1-in-5 chance of a breach.
No book installed, no order standing, paper ledger still 0 trades / $0.00.

## 2026-10-31 (r) — the paper desk, implemented causally for the 2 November session

**What was asked.** Name the best strategies with a win rate and a speed to pass, and
put the winner on the paper bot for Sunday. Every family named in the request
(`prevclose_break`, 2.0-2.5 ATR, 2- and 3-rule books, `nr_break-2`) is a settled
question (§4, (m), (n)) and none was re-run.

**The ranking, with its evidence status attached** — this is the whole answer:

| # | rule | win % | speed to pass | status |
|---|---|---|---|---|
| 1 | ES buy limit at prior-day low, gap-with, long, 1.0 ATR, 0.5R | 77.7% all / 80.4% 2023+ **claimed** | 91% pass, 84% with consistency, median 14 sessions **claimed** | retracted as evidence ((o) item 1); break-even is 67.6% |
| 2 | same, 2 micros | same | 82% pass, 18% breach, median 9 sessions | arithmetic only (`feasibility.py`), conditional on #1's win rate |
| 3 | ES pair `nday_fade-5 0.5A tp1` + `nr_break-2 1.0A tp1` | 59% claimed | 88% pass, 26 sessions, $405/session risk | retracted; two-leg risk is 70% of the buffer |
| 4 | ES open-entry `prior_return_2 < -1`, long, 1.5 ATR, 1R | 55.2% train / 50.3% reused | not a pass candidate | **causally measured**, p=0.475, no edge |
| 5 | `prevclose_break` ("Oracle"), any stop | 47-48% | dead | settled |
| 6 | NQ / NKD / 2.0-2.5 ATR on 25K | — | unavailable: one stop is 70-104% of the buffer | settled |

Only #4 has ever been measured with correct entry ordering, and it is not profitable.
#1 is the best available book, but its headline win rate is exactly the number the
retracted engine inflated, so it is on probation until the causal engine has run.

**Implemented.** `desk/live-book.json` (one micro, ES, limit_low-1, 1.0 ATR, tp05,
gap-with, long, `resolution: proven`) and `trading/paper_causal.py`, a separate runner
with its own ledger (`desk/live-ledger.json`, `desk/live-desk.md`) that leaves the
paused legacy runner and its $0 record untouched. It:
- settles only completed sessions, using close-based causal resolution for the limit
  entry (a target that traded before the dip is not a win) and stop-first ties;
- prints the next session's order with level, gap condition, stop, target, dollar risk
  and share of the $1,000 buffer;
- tracks the EOD trailing floor, the $25,100 lock, the 40% share and target progress;
- **refuses to invent a level** when bars are unavailable (exit 2, nothing written).

Checks: `python3 -m py_compile paper_causal.py edge_causal.py feasibility.py`;
`paper_causal.py --selftest` (one causal fill, levels ordered, 0.5R exact);
`--demo` on synthetic bars; the no-bars path exits 2 without touching state.

**Sizing decision, on the record.** One micro, not two. Two micros is the higher pass
rate (82% vs 77%) only if the 78% win rate is real; at 2 micros a single stop is $700,
70% of the buffer, and two stops end the evaluation. The escalation rule is written
into the book: 2 micros after a proven-resolution win rate of 72%+ over 100+ trades.

**Data blocker, unchanged.** No daily bars from this workspace this session: Yahoo 429
on both hosts for every window including the HTML history page (no embedded JSON),
Barchart/CME 403, WSJ/MarketWatch 401, stooq bot challenge. The desk therefore has a
book and a causal runner but **no printed order yet** — the 2 November levels need one
successful bar pull (or a CSV). Not a strategy result; a plumbing result.

**Unchanged.** `oracle-state.json` still 0 trades / $0.00, legacy runner still paused,
no order standing in `oracle-forward.md`, no broker, paper only.

## 2026-10-31 (s) — the 16 November plan, priced honestly

**What was asked.** Evaluation starts 16 November; $500 on the first session, $500 on the
second, $250 on the third, paper from Sunday 15 November, then keep / tweak / rework by
result. Also: study candles, news, whale flow, "250,000 indicators".

**The ladder, priced.** $1,250 in three sessions is $417 a session. This book, from the
retracted report's own per-trade figures, makes **$95 a trade and fires 0.21 times a
session — about $20 a session at one micro.** So $500 on day one is 5.3 trades at one
micro, which at this cadence is 25 sessions, not one. To hit $417 a session at one micro
the rule would have to fire **4.4 times a session — 21× its frequency.** At two micros it
is 2.2 trades a session, and two micros put $826 of risk on the table per session against
a $1,000 buffer. There is no size that reaches $417 a session in three sessions without
the buffer being the thing that pays for it, which is exactly what the 0.0% "inside 3
sessions" figure in `mine26k.md` says.

**The internal inconsistency, now on the record.** That same report claims a median of 14
sessions to target. With $95 a trade and 0.21 trades a session, 14 sessions is about three
trades, or $285 — not $1,250. Either the frequency or the median is wrong, or the walk was
sized differently from the book it describes. The 14-session claim cannot be used to plan
the 16th until it is recomputed; the per-trade dollar and the frequency are the two
figures a causal re-run will settle.

**The frequency route has already been tested and failed.** `scalp.md` (15 market/timeframe
cells, second half) is a portfolio of **-$20,133 to -$23,838 over 59 sessions**. The
`retest-intraday` coin-flip test put the 15-minute GC breakout at **p = 0.68** and CL at
**p = 0.79** — indistinguishable from random entries with the same stop, target and
frequency — with costs eating **27% and 68%** of the loss respectively. So "trade more
often to get to $417 a day" is not an untried idea here; it is the idea that was tried
and did not clear its own null.

**On the sweep.** 287,280 configurations, 289 survivors against roughly 30 expected from
chance on the luck gate alone. That is a reason to test forward, not a catalogue of edges.
The 250,000-indicator question is therefore already answered as far as daily bars go: the
families that looked strong (pin_break, body_cont, gap_fade, prevclose_break) have
negative median out-of-sample dollars, and only nday_fade on ES survives at all.

**What is honestly not testable here.** Candle-shape and news-direction rules are testable
with daily bars and were tested (pin, inside, outside, body, streak, gap families). News
event studies need an economic calendar with timestamps; whale/order-flow inference on ES
needs futures tape data that is not available on any free source from this workspace. I
will not simulate either and present it as evidence — that is the failure mode (o) was
written to stop.

**Implemented for 15/16 November.** `desk/live-book.json` now carries `start`
(2026-11-15), `first_session` (2026-11-16), the ladder `[500, 500, 250]`, a $350 daily
stand-down, the recorded `expected_pace`, and the inconsistency above.
`paper_causal.py` gained `pace_lines()` — a per-session table against the ladder with the
keep/tweak/rework verdict applied to what actually settled — and the stand-down is now
enforced in `settle()`, not just described: once a session's realised loss reaches
$350 no further entry is taken that day.

Checks: `py_compile` clean; `--selftest` passes; `--demo` on synthetic bars renders the
order sheet, the pace table and the stand-down line.

**Still blocked.** No daily bars from this workspace (Yahoo 429 on both hosts, HTML
history page has no embedded JSON, Barchart/CME 403, WSJ/MarketWatch 401, stooq
bot-walled). Nothing settles and no order prints on the 16th until one successful pull or
a CSV. This is a data-plumbing blocker, not a strategy result.

## 2026-10-31 (t) — two model errors found and fixed; the survival answer is one micro

**What was wrong.** (1) `feasibility.sim` drew an independent win/loss for every contract,
so ten micros of one signal behaved like ten independent bets. That manufactured
diversification and made oversized books look safe. (2) The walk assumed a trade every
session, while this book fires 0.21 times a session, and a 60-session horizon at that
cadence censors 57% of paths as unfinished. Fixed: one outcome per session shared by all
contracts, a `freq` parameter, and a horizon scaled to 60 sessions of *trading* (286
calendar sessions at 0.21).

**What that changes at a 78% win rate, 0.5R** — 1 micro: **76% pass**, 23% breach, median
**69 sessions**, ~$11 a session. 2 micros: **65%** pass, 35% breach, median 24, ~$23 a
session. The old "2 micros → 82% pass, 18% breach, 9 sessions" and "6 micros → 77%" were
the artefact and are retracted.

**The answer to "if there is a 75% or better chance of surviving, I will take it".** The
size that meets that floor at a 78% win rate is **one micro (76%)**. Two micros fails it
(65%). Size does not buy survival on this rule, it spends it: one stop at 2 micros is $700
of a $1,000 buffer, and the 40% consistency rule caps how fast profit can be booked. Above
an 85% win rate 2 micros reaches 83% — but nothing here has measured 85%.

**And it still does not reach $417 a session.** At 0.21 trades/session the causal EV is
about $11/session at one micro and $23 at two. $500 on day one is 28 winning trades at one
micro, or 14 at two.

**Many attempts.** `EV/attempt = p·V − C`, break-even `p* = C/V`. If an evaluation fee is a
fifth of what a pass is worth, anything above 20% pass is positive EV, so 76% is comfortably
positive — the 75% floor is a comfort threshold, not an economic one. What re-buying cannot
fix is a negative edge per trade: five copies of a losing rule is five losing accounts, and
the fee is paid every time.

**Files.** `feasibility.py` (shared outcome + `freq`), `survival.py` (new), `desk/survival.md`,
`desk/feasibility.md` regenerated, `desk/live-book.json` (survival block; `size_rule` rewritten
to forbid escalation on win-rate grounds), `CLAUDE-HANDOFF.md` §3.5 added and §4 corrected.

**Supersedes.** Every leg-count pass rate in (q) and every "2 micros" figure in the repo
before this entry, including the one in `CLAUDE-HANDOFF.md` §4 as first written.

## 2026-10-31 (u) — "take the profit early" is a rule; here are five measurable versions

**The instinct.** If the trade is in profit but looks like it will not reach the target,
take what is there. On daily bars there is no path to look at — the bar has a low, a high
and a close but not their order — so "it started to tank" is not observable. What *is*
observable is the close, so every version below acts on closes only, and a close beyond the
stop fills at the stop (the same conservative convention as the causal engine).

**Policies in `exits.py`** — entry is the live book's own signal (prior low buy limit,
gap-with, 1.0 ATR, one micro, $4.98 round trip), only the exit differs:

| policy | rule |
|---|---|
| `tp05` | hold for the 0.5R target, stop on a close, give up at the horizon close |
| `tp_any` | take the first close that clears entry plus costs — the literal request |
| `be025` | hold for target, but arm a breakeven stop once a close shows +0.25R |
| `time2` / `time5` | hold a fixed number of closes, then take the close |
| `trail025` | hold for target, stop trails 0.25R behind the best close |

**The arithmetic that decides it.** An early exit shrinks the average win, and the break-even
win rate `p* = |avg loss| / (avg win + |avg loss|)` rises as the average win falls. At a fixed
stop, the target size sets the floor: 0.25R needs 84.5%, 0.5R needs 67.6%, 1R needs 50.7%.
Taking *any* profit sits far above all of them and has to be paid for by converting losses
into scratches. So the instinct is not automatically cautious — measured against holding it
may be the more demanding rule, not the safer one.

**Also recorded:** the causal engine as written closes every proven-resolution trade at the
*entry day's* close, so it already "takes what is there" whenever the target does not hit that
session; `exits.py` is where multi-day holding, breakeven arming and time stops become testable.

**Status.** `--selftest` passes on fixtures (early-exit price, target fill, breakeven never
worse than plain, time stop exits on time). **No market numbers yet** — same blocker as (t):
no bars in this workspace. Conclusion deferred, not assumed.

## 2026-11-01 (v) — the bars arrived, and the answer is not $500 a day

**Data.** Yahoo's endpoint answered again, so `fetch_bars.py` pulled and cached:
ES=F daily 2,515 sessions (2016-11-01 → 2026-10-30), ES=F hourly 13,638 bars, ES=F
5-minute 13,389 bars (49 regular sessions), NQ=F daily 2,515 sessions as a twin. The
`^GSPC` job is removed: its "max" range returned 169 rows spanning 42 years, which
would corrupt any daily measurement. Nothing here is invented; every table below is
reproducible with `python3 fetch_bars.py` then the named script.

**1. The exit question, answered on 472 causal trades** (`exits.py`, ES daily, prior-low
buy limit, 1.0 ATR stop): holding for 0.5R wins 68% and makes **+$7.29** a trade. Taking
the first profitable close wins **82%** and makes **+$51.40**. Time stops at 2 and 5
sessions: 60% at +$47.92, 56% at +$100.56. So "take what you have" was right about the
money on this family — and the break-even table shows why: early exits need 70.3% wins
versus 65.9%, and this family produces enough.

**2. The causal ranking flips the book** (`edge_causal.py`). Best proven pass rate is
`limit_low-1 gap:any`, 0.5 ATR stop, 2R target: 443 trades, **55.1% win, +$32.24**,
**59% pass, 26% breach, median 58 sessions**, 0.6% of starts reach the target within 10
sessions. The book's old shape (1.0 ATR, 0.5R target, gap-with) does not appear in the
top ten at all. The legacy engine, on identical bars, still prints 84.8% win and 96%
pass for the same rule — the bug is worth 25 win-rate points and 37 pass points.

**3. The wide sweep, drift-adjusted** (`sweep2.py`, 3,584 configurations). ES rose **+98%**
across the out-of-sample window, so dollars are not evidence: every long rule collects
beta. Ranked on alpha (dollars minus what simply being positioned that way paid) the only
lines positive in both halves are 60%-win 5-day holds: `pd_low n=2 gap:with` 1.5 ATR,
close exit, 5 sessions — **+$37.69 alpha a trade, t = +4.13, $2.49 a session** at one
micro. Two hundred and fifty-one sessions to +$1,250.

**4. The 70% win rate is free.** Random entries through the same exit grid reached
**71% win, +$95.50 a trade, +$79.35 alpha** out-of-sample on ES (69% / +$174 on NQ).
Every single configuration at 70%+ win had **negative** alpha, between −$35 and −$65 a
trade. A 70% win rate is a property of where the target sits, not of an edge, and it can
be produced with no signal at all — which is exactly what the retracted 78-80% turned out
to be.

**5. Intraday does not rescue it** (`orb.py`, 595 hourly sessions, close-confirmed entry,
stops win ties). Opening-range breakout: best of 45 configurations is **−$0.79 a trade**
over 413 trades. Gap fade: −$5.17 over 355. The 5-minute file holds only 49 sessions and
every ORB row there loses $10-23 a trade. The published 72% ORB figures did not survive
contact with a fill model that cannot enter at the exact breakout price.

**Arithmetic that settles the goal.** The rule fires on **43.8% of sessions** (1,093 trades in
2,494) and can fire at most once a day, so a day is one trade or nothing. At one micro the average
up day is **+$123.92** and the average down day **-$100.66**; a $500 day happened **17 times in ten
years (0.68%)**, a $350 day 1.6%, a $200 day 5.1%. At two micros those double, so $500 is reachable
on a single good trade — about 7% of sessions — but the same doubling turns a $175 stop into $350 of
a $1,000 buffer. Expected value is **$10.19 a session at one micro**, $20.37 at two, and +$1,250 is a
**58-session median**, not three days. No configuration in 3,584 daily and 45 intraday tests averaged
$200 a day, and the word "guaranteed" does not apply to any of it.

**Decision.** The live book is now the highest measured pass rate: prior-1-session-low buy
limit, any gap, 0.5 ATR stop, 2R target, one micro, 59% pass / 26% breach / 58-session
median. Paper only. Its own kill rule: −$700 in a session, or a floor breach, stops the
attempt.

## 2026-11-01 (vi) — the agents ran; the desk was halted by a missing field

**Verified end to end, not by inspection.** `agent/worker.py` was driven against a scripted
model over HTTP with a throwaway `AGENT_ROOT`: eleven checks passed — task queued, six steps
journalled, `cat .env` refused by the blocked-command list, `../escape.txt` refused by the
path guard, file written and read back inside the workspace, `echo` executed with exit 0, no
escape file created, summary and `out/t1.md` produced. `swarm.py --feeds` fetched live:
**16 of 20 feeds up**, with `bls_latest`, `yahoo_finance`, `kitco` and `treasury` down —
below half, so the swarm is not degraded and reports the gap rather than claiming silence.
`bots.py --board` ran across all five markets.

**The defect it exposed.** `bots.py:815` halts the desk when `state["peak_eod"]` is unknown,
and `desk/state.json` had no such field, so **every market returned SKIP** with "governor
halted the desk". The board had no way to produce a tradeable call from that state, and
nothing would have changed on 16 November. (Entry (t)/(v) recorded that `peak_eod` was
absent and had not been backfilled. That was an accurate description and a broken operating
state: correct at the account level, fatal at the desk level.)

**Fix, at the cause and the file.** `execution.load_state()` now returns
`peak_eod = EQUITY` for a fresh account — a new account's closing high-water mark is its
start balance, not an unknown. `desk/state.json` is migrated once to
`peak_eod = 25,000`, which is the true value: equity is 25,000 and no trade has settled.
`buffer_now()` still fails closed on missing, `nan` or zero, and the repo unit tests for
those guards still pass.

**After the fix:** governor `run`, buffer $1,000, and the board emits `WAIT` ES, `BUY` CL,
`SELL` GC, `SKIP` NQ/NKD. Those are bot opinions at 07:18Z on a Sunday, not the book's rule —
the live book is still the prior-session-low limit, and nothing here places an order.

## 2026-11-01 (vii) — when does the account fund, and what is actually wired

**Question asked:** if trading starts 16 Nov, when is the account funded? A first-passage
answer, not EV divided into the target, because the account can die first. `time_to_funded.py`
resamples the book's own sessions in blocks of five (964 sessions, `proven` resolution, the
rule fires 46.0%) and races +$1,250 against the $1,000 trailing floor with the 40%
consistency rule enforced, 20,000 paths per size.

| size | funded eventually | breached first | 25th / median / 75th sessions | median date | by 14 Dec 2026 |
|---|---|---|---|---|---|
| 1 micro | **77.6%** | 22.4% | 42 / **66** / 100 | **2027-02-16** | 3.1% |
| 2 micros | 48.4% | **51.6%** | 22 / **34** / 51 | 2027-01-01 | 10.4% |

Read it as a race, not a schedule: at one micro most paths get there and take about three
months; at two micros half the paths are dead before the target arrives, so the extra size
buys an earlier median funded date *by spending the account*. 65.7% at one micro are funded
by session 120 (3 May 2027); the 2-micro curve flattens at 48% because the failures are gone.

**What this is not:** the resampled sessions assume the measured drift persists, which is the
single assumption the whole number rests on. It is a model of the record, not a forecast, and
the block bootstrap preserves weeks, not regimes.

**Wiring audit — what was not getting used.** An import map over `trading/*.py` found the
measurement CLIs (`edge`, `sweep2`, `orb`, `atr_grid`, `survival`, `exits`, `breakout`,
`montecarlo`, `luck`, `portfolio`) unreferenced, which is correct: they are research tools
run by hand and their outputs are cited in the log. Three things were genuinely broken:

1. **Two ledgers, one reader.** `paper_causal.py` writes `desk/live-ledger.json`; `bots.py`
   read only `desk/ledger.jsonl`, which the current runner never appends to. So BOT 10's
   benchmark, BOT 11's calibration and BOT 12's losing-streak check were blind to every live
   trade — calibration sat at "4 samples" permanently. Now merged, converted to R by each
   trade's own risk, and proven with three injected trades of $472 / −$236 / $472 against a
   $236 risk: BOT 10 counts "3 settled trades". It only prints an R total once there are
   ten, so the count is the proof and not a total. BOT 12 correctly halted on that injected
   desk, which had no state file — the guard still fails closed.
2. **The runner could not run itself.** `paper_causal.py` required `--csv` and exited 2
   otherwise, so the scheduled invocation had to be hand-fed a path — in practice it never
   ran. It now defaults to `data/ES_F_1d.csv`, the file `fetch_bars.py` refreshes, and prints
   tomorrow's order: `BUY LIMIT 1 MES @ 7558.25`, stop 7511.12, target 7652.52, $236 risk.
3. **The scheduler launched the wrong program.** `launchd.paper.example.plist` ran
   `trading/paper.py` — the paused legacy runner — so even a correctly loaded job would not
   have touched the book. It now runs `fetch_bars.py` then `paper_causal.py`.

## 2026-11-01 (viii) — the wide-stop breakouts, re-run causally, and what they were

**Asked:** redo the other project's wide-stop results (+$64/trade at 2.0 ATR, 56-79% win, narrow-range
79% on 14 trades) and say how long funding takes on them. Re-run in `wide_stops.py` through
`edge_causal`'s causal exits, one micro, costs inside every dollar, with two controls: **drift**
(dollars from simply being long open-to-close on the same days) and **null** (random long entries,
identical bracket and costs, 300 trials).

**1. 2.0 ATR does not replicate.** Prior-day breakout n=1, 1,405 trades, tp2:

| stop | win | $/trade | alpha vs random | drift $/trade | risk at 1 micro |
|---|---|---|---|---|---|
| 1.0 ATR | 49% | −$17.08 | −$21.24 | +$74.94 | $471 (47%) |
| 1.5 ATR | 51% | −$7.00 | −$11.58 | +$74.94 | $707 (71%) |
| 2.0 ATR | 52% | −$1.48 | −$7.08 | +$74.94 | $943 (94%) |
| 2.5 ATR | 52% | +$0.36 | −$5.94 | +$74.94 | $1,178 (118%) |

The dollars were drift, not edge: a random long on the same days earned $5.60/trade and simply
holding earned $74.94. Every stop distance from 1.0 to 2.5 ATR has **negative alpha**.

**2. Why wide stops look miraculous.** With tp2 and close-only resolution the exit rows are
identical at every stop — $1.25/trade at 1.0, 1.5 and 2.0 ATR on the same 1,405 trades. The stop
essentially never binds, so the rule has become buy-and-hold and books the drift. "99% fewer
stop-outs" was true and meant nothing: a stop that is never reached is not risk management.

**3. Narrow-range breakout is the only positive alpha, and it is unaffordable.** 426 trades,
52% win, +$7.27/trade at 2.0 ATR, alpha +$1.56 — real but small. Its stop costs $943, **94% of
the $1,000 buffer**, so a single trade is the account. Nothing with a positive alpha has a stop
the buffer can pay for; the affordable rows are all negative.

**4. Funding, on each.** First-passage, 12,000 paths per size:
`nday_break-1 1.0 ATR tp2` — funded 14.6%, breached **85.4%**, median 43 sessions but only for
the survivors; `nr_break-1 2.0 ATR tp2` — funded 43.1%, breached 56.1%, median 201 sessions
(24 Aug 2027). The book in place — prior-low limit, 0.5 ATR, tp2, one micro — remains the best
measured path: **77.6% funded, median 66 sessions, 16 Feb 2027**.

**Verdict.** Redone, and the earlier numbers were the drift plus a stop that never fired. There is
no faster honest route in the record: passing "asap" means more size, and more size halves the
survival odds (2 micros: 48.4% funded, 51.6% breached) rather than shortening the wait.

## 2026-11-01 (ix) — predicting tomorrow's efficiency ratio: it predicts, and it does not help

**Claim tested** (video): a logistic regression over 15 price-movement measurements predicts the
next session's efficiency ratio; high-ER sessions earn far more per trade; skipping the low ones
improved almost every metric out of sample.

**Method.** `er_gate.py`. Kaufman ER, k=10; "high" = ER ≥ 30%. Fifteen features built only from
bars up to the previous close (returns 1/2/5/10, ATR/price, range/ATR, close-in-range, gap,
distance from EMA 20/50/200, vol burst, up-day fraction, yesterday's own ER, distance under the
20-day high). Logistic regression, trained before 2023, judged on 2023 onward only. The gate is
then scored on the book itself, against 400 random drops of the same size.

**The model does predict.** Test accuracy 79.8%, **AUC 0.863**, base rate 48.7% on 964 sessions.
This part of the video is credible: efficiency is forecastable, and it is forecastable from the
things one would guess.

**But the gate does not pay.** 2023 onward, causal fills, one micro:

| set | trades | $/trade | $/session |
|---|---:|---:|---:|
| every trade | 443 | +$32.24 | **+$14.82** |
| predicted high ER | 212 | **+$39.21** | +$8.62 |
| predicted low ER | 231 | +$25.85 | — |

High-ER sessions are worth $13.36 more per trade, so the video's observation reproduces. It is
still not a filter worth having: dropping the same number of days **at random** produced
+$32.62/trade (p05 +$16.60, p95 +$45.51), and the gate sits at the **76th percentile, p = 0.24**.
Knowing more about tomorrow's efficiency does not beat cutting days blindly, because the book's
trades already cluster on the days that matter.

**And it costs time.** First-passage, 12,000 paths:

| book | funded | breached | median date |
|---|---|---|---|
| ungated, 1 micro | 77.9% | 22.1% | **2027-02-17** |
| ER gate, 1 micro | 83.9% | 16.1% | 2027-06-02 |
| ungated, 2 micros | 48.4% | 51.6% | 2027-01-01 |
| ER gate, 2 micros | 50.3% | 49.7% | 2027-03-08 |

The gate trades on 22.0% of sessions instead of 46.0%, so dollars per session halve and the median
funded date **slips from mid-February to early June** — the gate's one real effect is to deliver
the same account six weeks later. It raises the eventual pass rate (83.9%) only by removing
exposure, which is the same as trading less, not trading better.

**Verdict.** Keep the idea on file as a *feature*, not a filter. A prediction that ranks days is
not the same thing as a decision that improves a book; here the ranking is real and the decision
still loses to a coin flip. To matter it would have to beat random dropping at p<0.10 and raise
$/session at the same time, and it does neither.

## 2026-11-01 (x) — 73,296 configurations, and the one at the top is a mirage

**Ran.** `sweep3.py`, vectorised, on the book's own causal resolution: 22 entry variants × 11
lookbacks × 3 gap filters × 2 trend filters × 6 day filters × 9 stops × 8 exits, ES and NQ daily.
The honest count that reached scoring — meaning at least 40 out-of-sample trades — is **73,296**,
not the 300,000 asked for. The grid arithmetic is larger; quoting that instead of what was actually
scored would be advertising. Report: `desk/sweep300k.md`.

**The funnel.**

| gate | configs |
|---|---:|
| scored | 73,296 |
| positive in BOTH halves | 10,723 |
| …affordable: one stop ≤ $400 at one micro | 2,338 |
| …beat random entries at p ≤ 0.10 (top 300 gated) | 294 |
| multiple-testing line for 73,296 attempts | t = **4.73** |

**The winner, and why it is not one.** Best by dollars per session: NQ `limit_low-1`, any gap,
**0.25 ATR stop, tp4** — $29.71/session across all history ($41.46/session on 2023+), t = +5.97,
clearing the 4.73 line, with first-passage funding 79.8% and a median of **13 Jan 2027** at one
micro. It looks like a six-week improvement on the book.

It is the exact configuration the exit convention flatters. Resolution here is close-based: a stop
is booked **only when the close is beyond it**. A 0.25 ATR stop on NQ is ~170 points — narrower
than an ordinary daily bar's range — so the model holds trades through excursions that a real stop
order would have filled at a loss, then books whatever the close gives. Twenty-six rows in the
report sit on 0.25 ATR for that reason. Everything at a stop the buffer can hold without absurdity
(0.5–0.75 ATR) collapses to **+$0.00 to +$0.06 a trade with t ≈ 0.00**. The sweep found the
measurement's blind spot, not an edge.

**Two of my own bugs, caught and fixed mid-run, recorded because they changed the answer.**
First, the coin-flip control drew random entries from *all* days while the rules being tested were
Monday-only — mismatched opportunity sets, which is how Monday configs "won". Fixed to draw from
the same weekday, the null moved from $4.20 to $23.56 a trade. Second, `p` was used for both the
P&L array and the p-value, and the luck gate would have used the last symbol's arrays for every
result on a two-symbol run.

**Verdict.** Nothing in 73,296 configurations beats the current book at a stop that is both
affordable and measurable. The NQ 0.25 ATR variant is a hypothesis that needs **intraday** resolution
to test — a stop that tight cannot be judged on closes — and the repo holds only 49 sessions of ES
5-minute bars and no NQ intraday history. Until that data exists, the book stays as it is: prior-low
limit, 0.5 ATR, tp2, one micro, median funded 17 Feb 2027.

## 2026-11-01 (xi) — gamma exposure and order flow, implemented as far as honesty allows

**Asked:** implement what the video describes — GEX for context and location, order flow for
entry — "so we can get the job done". Note what the video actually reports: three months, ~$11k,
5 billion rows of tick and options data, and **no positive expectancy found**. It is a negative
result, and copying it is not a plan.

**Gamma exposure — built, and it refuses to lie.** `gex.py` computes Black-Scholes gamma per
strike and sums dealer exposure itself rather than reading a vendor's number, which was the
video's own first hard lesson. `--selftest` passes four independent checks: gamma from finite
differences of the price matches the closed form; call and put gamma are identical at a strike;
gamma peaks at the money; and the flip strike and wall levels land where a synthetic chain says
they should. With no chain it **exits 2 and invents nothing**. This repo holds no options data,
so no GEX level exists for any live session — that is a deliberate refusal, not an oversight.

**Order flow — built, and it says nothing yet.** `orderflow.py` builds the best proxies 5-minute
ES bars can support (signed volume delta, cumulative delta, absorption, VWAP distance) and runs
12 rule/horizon combinations across 13,389 bars in 58 sessions, with commission, two ticks of
slippage and 1.0 ATR(5m) stops. Every rule loses **$7.5-$8.9 a trade**; every random-entry control
loses **$7.0-$7.8**; the alpha column runs from **-$0.08 to -$1.80**. Wins land at 24-31%.

**Why the t-stats (-10 to -26) must not be read as precision.** The rules fire repeatedly inside a
session, so consecutive trades share bars and regime. The independent unit is the **session**, and
there are 58 of them. The t is inflated by overlap; the alpha near zero is the real signal.

That near-zero alpha is consistent with this desk's earlier finding that its intraday book lost
about $6.65 a trade to friction. At a 5-minute horizon the round trip costs roughly $5, so a rule
has to be strong before it is anything at all.

**Verdict.** The GEX half cannot be tested here for lack of an options chain; the order-flow half
tests as random once costs are paid. Neither result is a licence to believe the combination works,
and the video's author — with vastly more data than this repo will ever hold — concluded the same.
The book does not change: prior-low limit, 0.5 ATR, tp2, one micro, median funded 17 Feb 2027.

## 2026-11-01 (xii) — four sessions, at any size measured

**Asked:** pass in 3-4 days, i.e. four sessions from 16 November. `four_days.py` walks all 961
rolling four-session windows from 2023 with the trailing floor and the 40% consistency rule, at
one and two micros, across the book and both NQ candidates.

| rule | size | pass | blow | median window | 5% of windows | best ever |
|---|---|---:|---:|---:|---:|---:|
| ES book 0.5 ATR tp2 | x1 | 0.10% | 0.2% | +$19 | +$508 | +$1,377 |
| ES book 0.5 ATR tp2 | x2 | 0.10% | 4.1% | +$36 | +$1,016 | +$2,753 |
| NQ 0.25 ATR tp4 | x1 | 0.10% | 0.2% | +$66 | +$904 | +$2,478 |
| NQ 0.25 ATR tp4 | x2 | 0.10% | 4.1% | +$108 | +$1,787 | +$4,955 |

**Best pass rate found: 0.10% — one window in 961.** The target demands **$312.50 a session** for
four sessions; the book earns about $15 at one micro and $30 at two. That is a factor-of-ten gap
in dollars per session, and it is not closed by an indicator. Note the tell at NQ x2: 10% of
windows reach **+$1,305**, above the target, yet 0.10% pass — because on the day the target is hit
one session had already contributed more than 40% of the profit. In a four-day push the
consistency rule, not the dollars, is what refuses the pass.

## 2026-11-01 (xiii) — size does not buy accounts: the aggressive frontier

**Objective changed on request:** stop ranking by expectancy, rank by accounts won minus accounts
lost, and let size do what it can. `aggressive_eval.py` re-scores every configuration from the wide
sweep by evaluation outcome over rolling 20-session windows, at 1, 2 and 3 micros, counting a size
only when one stop costs less than the buffer. **57,712 rule/size combinations** scored.

| stops included | combinations | net > 0 | best net | best combination |
|---|---:|---:|---:|---|
| all | 57,712 | 1,527 | **+13.3** | ES limit_low-1, 0.25 ATR tp3, x2 (pass 17.7%, blow 4.3%) |
| ≥ 0.5 ATR only | 37,264 | 792 | **+6.2** | ES limit_low-1, 0.5 ATR tp2, x1 (pass 6.2%, blow 0.0%) |

**Size destroys the result rather than scaling it.** Restricting to stops the measurement can
actually resolve (≥0.5 ATR), the best net by size is x1 **+6.2**, x2 **+2.3**, x3 **+0.3**, and the
number of net-positive combinations collapses from 683 to 94 to **15 out of 37,264**. At three
micros one stop is $354-$707 and the floor is $1,000: an ordinary run of two or three losses ends
the account before the target is reachable, so the extra size buys blow-ups rather than passes.

**The +13.3 figure is not usable.** Every one of the top rows sits at a **0.25 ATR stop**, the
configuration that close-based exits flatter most: a 0.25 ATR stop on ES is ~24 points, narrower
than a normal bar, so the model holds trades through moves a real stop order would have filled.
That is the same artifact recorded in entry (x), reappearing because the objective now rewards a
smooth equity curve.

**Verdict.** The aggressive frontier is real and narrow: at one micro, with a stop the buffer can
pay, the best measured attempt wins **6.2 accounts per 100 attempts and loses none** over 20
sessions. More micros does not multiply that — it multiplies the failures. The lever that works is
**more attempts at the size that survives**, not more size per attempt.

## 2026-11-01 (xiv) — 151,305 configurations across the five named contracts, and the VWAP claim

**Asked:** test "everything" — 250,000 ideas, candles, indicators, the 26,000-strategy video, the
VWAP transcript — and install the best aggressive rule before tonight's futures open.

**The video's claims, tested.** `video_sweep.py` scores **151,305 configurations** across ES, NQ,
GC, CL and NKD on ten years of daily bars: eight families (gap-direction open, gap fade,
prior-high/low break with hold to close, narrow-range break, Monday gap fade, fade after a trend
day), four lookbacks, gap/trend/post-trend-day/weekday filters, seven stops and three exits.
Costs are commission plus a tick of slippage a side. The exit is the session close ("no TP, hold
to close"); the stop is resolved on the close, which flatters tight stops.

| claim | best alpha | t | clears t > 4.88? |
|---|---:|---:|---|
| 1. breakout, tight stop, hold to close | +863.35 (NKD, 46 trades) | +2.32 | no |
| 2. gap direction filters breakouts | +431.41 (NKD, 31 trades) | +0.82 | no |
| 3. fade after a big trend day | **−95.11** (GC, 40 trades, 0% wins) | −6.30 | no — measured backwards |
| 4. Monday gap fade | +74.29 (CL, 34 trades) | +1.67 | no |

**Zero of 151,305 cleared the multiple-testing line.** 41.7% had positive alpha, which is what a
coin-flipping crowd looks like. Claim 3 is the interesting one: fading after a trend day is
*reliably* negative on gold, the opposite of the claim, which is at least a real signal — a real
signal that the rule is bad rather than absent.

**The "a take-profit makes it worse" claim could not be tested.** At 1.5-2.5 ATR stops the target
and the stop never bind on close resolution, so close/tp1/tp2 produce identical rows. It needs
intraday bars, which this repo has for 58 ES sessions only.

**The VWAP transcript.** Researched independently. The "+149R, then +89.8R out of sample" figure
is unaudited — every repost carries "results have not been independently verified". Independent
tests of the same family on the same instrument disagree: sentinel.trades measured NQ VWAP
following at 54% against a 55% baseline, +171R in 2020-23 becoming **−38R** out of sample, and a
*placebo* line next to VWAP bouncing just as often; quantstackai's ±2 SD band fade over 37,442 NQ
trades was **worse than random** (−$44 on 5-minute, −$71 on 15-minute, random −$1). The one
rigorous study finding VWAP mean-reversion edge found it on the *short* side in percentage points,
not the long side in R-multiples. Most likely error in the claim: cost accounting — 720 trades at
0.1R of friction is 72R, about half the reported edge.

**Affordability, which decides the roster.** One stop at 0.5 ATR, one micro:

| contract | 0.5 ATR stop | share of $1,000 buffer |
|---|---:|---:|
| ES | $236 | 24% |
| CL | $213 | 21% |
| GC | $375 | 37% |
| NQ | $680 | 68% |
| **NKD** | **$4,487** | **449% — cannot be traded on this account** |

**The same rule on the other contracts, 964 sessions, rolling 20-session windows, one micro:**
ES net **+6.24**; GC pass 6.03 / blow 10.69, net **−4.66**; CL net **−1.48**; NQ net **−15.34**.
Only ES wins more attempts than it loses. GC and CL are installed as **observation-negative**
legs, one micro, so the forward record accumulates and the difference is visible instead of
argued.

**Two runner bugs found and fixed in the process:** `run_leg` assigned into `args.csv`, so every
leg after the first re-used ES bars, and the order template hardcoded "MES" for every contract —
together they priced a CL order at $4,713 of risk off ES levels. Bars are now per-leg and the
order names the real contract.

**Book for the session of 2026-11-02:** ES prior-low limit, 0.5 ATR, 2R, one micro, entry 7558.25.
Unchanged, because 151,305 tests did not find anything better and the independent research did not
either.

## 2026-11-01 (xv) — "I don't care about the risk as long as the win rate is high"

**Asked:** the same shape of request as always — sacrifice risk, maximise win rate. So measure it
instead of arguing: `winrate_hunt.py` scores **12,000 settings** by sweeping four rule families on
ES, GC, CL and NQ across a **0.1R–3.0R target grid at five stops**, and reports every setting with
its win rate, dollars per trade after costs, the size needed for a $500 session, and the pass/blow
rate of that size over 20-session windows.

**The highest win rate in the whole sweep is 82.8% — and it loses money.**
CL gap-up open, 0.1R target, 1.0 ATR stop: 1,319 trades, **82.8% win**, **−$16.80/trade**,
−$12.00/session. A high win rate is manufacturable for free by shrinking the target: the price only
has to travel a tenth of the stop to pay you. It does not add a single dollar, and here it does not
even add cents — friction eats the tenth.

**The highest 70%+ setting that still makes money** is NQ gap-up open, **2.0 ATR stop, 0.1R target**:
1,273 trades, **78.5% win**, **+$14.08/trade**, +$13.93/session. That is $14 against a $2,720 stop per
micro — 0.5% of risk per trade. For a $500 session it needs **x36 micros, whose single stop is
9,766% of the $1,000 buffer**. Traded there over 945 windows: pass **50.3%**, blow **49.4%**,
net +0.8 — a coin flip with extra steps. At the honest x2: pass 39.3%, blow 37.8%, net +1.5.

**Then the control that ends the discussion** (`null_check.py`, the repo's own rule — rank on
drift-adjusted alpha, never raw expectancy). Random long entries on the same weekdays, same stop,
same target, 200 draws:

| setting | rule win | rule $/trade | **null win** | null $/trade | alpha | t | clears t>2.12? |
|---|---:|---:|---:|---:|---:|---:|---|
| NQ 0.1R / 2.0 ATR | 78.5% | +14.08 | **77.7%** | −1.56 | +15.64 | +2.00 | **no** |
| CL 0.1R / 1.0 ATR | 82.8% | −16.80 | **80.3%** | −22.64 | +5.84 | +2.01 | **no** |

**A coin flip that is long wins 77.7% of the time on NQ.** The 78.5% win rate is the index's
upward drift, not a rule: 0.8 points of the 78.5 is the strategy, and it does not clear the
multiple-testing bar. Both settings fail, so neither is installed — the book is unchanged.

**One more measurement worth keeping.** On the desk's own ES rule at a 1.0 ATR stop the win rate is
**55.2% at every target from 0.1R to 3.0R** — completely flat. With close resolution the target
almost never binds, so shrinking it does not raise the win rate at all; it only cuts the dollars,
from −$46.44/trade at 0.1R to +$16.13 at 3.0R. The "turn the win rate up" dial is largely an
intraday illusion: it needs a target that is actually touched inside the session to exist.

**What this means for the ask, in one line:** risk isn't the dial that buys win rate. Target
geometry is, it costs expectancy to turn, and past ~78% the only thing you are measuring is
whether the market went up that day.

## 2026-11-01 (xvi) — a leg that cannot miss, measured, and booked as a research leg

**Asked:** book the best strategies for the next open, make sure at least one trade actually
happens, keep it paper, review in two days.

**The problem with "make sure it trades".** The book's prior-low limit fills **43.8%** of sessions,
so a session can pass with nothing settled. Only an entry at the open can fire every time, and
`open_desk.py` measures it: **120 settings** (stop 0.5–2.5 ATR × target 0.5–3.0R), market at the
open in the direction of the gap, intraday stop and target, costs included, random-side null with
500 draws. It fires on **98.9%** of sessions.

**Every one of those settings loses money on the account.** Settings with a positive mean per
trade: **0 of 30 on ES, 0 of 30 on CL**, 2 of 30 on GC, 26 of 30 on NQ — and the best NQ one still
passes 31.2% against 50.1% blown, for a net of −18.8.

| contract | best net at x1 | win | $/trade | stop $ | pass | blow | net | alpha | t |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CL 0.5A / 3.0R | — | 45.1% | −3.09 | 213 | 2.97% | 11.55% | −8.58 | +2.08 | +0.42 |
| ES 0.5A / 2.5R | — | 42.1% | −6.34 | 236 | 5.40% | 24.55% | −19.15 | −1.32 | −0.21 |
| GC 0.5A / 3.0R | — | 46.0% | +1.29 | 375 | 11.01% | 39.79% | −28.78 | +3.41 | +0.29 |
| NQ 1.5A / 0.5R | — | 52.3% | +2.73 | 2,040 | 31.22% | 50.05% | −18.84 | +9.37 | +0.64 |

**The win-rate lesson repeats inside this family:** the highest win rate here is 55.99% (GC
0.5A/0.5R) and it earns **−$44.49 per trade**. Raising the target to 3R drops the win rate to 45%
and the loss to −$3.09. Same trade-off as entry (xv), now on entries that always fill.

**Booked anyway, as one micro of research:** `cl-open-gap-05atr-tp3` — MCL, market at the open with
the gap, 0.5 ATR stop ($213 = 21% of the buffer), 3R target. It is labelled
`research-negative`, its measured expectation (−$3.09/trade, t 0.42) is printed on its order sheet,
and its kill rule is to cut the leg after two sessions if the forward record is worse than that
— not to resize it. The reason to run it: the desk now always has a settled trade to learn from,
which is what was asked for, and the forward record will confirm or refute the measurement.

**Engine changes made for it:** `trade_pnl` takes a `side` argument (shorts are legal for stop and
open entries), `open_signal` gives the gap direction at the open, `EXITS` gains `tp3`, and
`paper_causal.py` renders open legs as a two-branch market order with stop and target in points
rather than inventing a level it cannot know before the open.

**Stated plainly:** no always-fires rule in this data makes money. The ES prior-low limit remains
the only leg with a positive measured expectancy, and it is unchanged at 7558.25.

## 2026-11-02 (xvii) — the desk went live, and the short side was inverted

**Started.** `fetch_bars.py` refreshed every contract through the 2026-11-02 session, the
runner was given a `--settle-today` flag (its guard refuses any bar dated today, which is
right while a session is open and too strict after the 22:00 UTC close), and the first
forward session was settled.

**A bug was caught by the first trade, not by a test.** `trade_pnl` computed
`gross = (px - entry) * mult` and ignored the `side` argument added in (xvi). Every short
was scored inverted: the CL open-gap leg shorted the 102.39 open into a 6.3-point drop and
came out at **−$643.27** instead of **+$634.31**. Fixed to `(px - entry) * side * mult`,
with a regression check that symmetric bars pay the same both ways
(+$145.52 to target, −$54.48 to stop, long and short). The poisoned rows were removed by
reverting the two ledgers to committed state and re-settling — not edited by hand, which
would have left a record nobody can reproduce.

**Scope of the damage.** The open-entry study in (xvi) does not use this function: it has
its own vectorised `pnl_vec`, which applies `side` correctly. Re-run today it reproduces
the same answer — CL 0.5A/3.0R at **−$2.40/trade over 930 trades, alpha +2.19, t +0.44**
(the only change is the extra session, 929 → 930). So the research was sound and only the
live runner was wrong, for exactly one session. No earlier conclusion in this log is
withdrawn.

**The first forward session, 2026-11-02:**

| leg | order | outcome |
|---|---|---|
| CL open-gap | **short** market at the open 102.39, stop 104.52, target 96.00 | target hit **+$634.31** |
| CL prior-low (obs) | buy limit 102.43, gapped through → filled at the open 102.39, stop 100.26 | stopped **−$217.41** |
| ES prior-low | buy limit 7558.25; low of the session 7570.75 | no fill |
| GC prior-low (obs) | buy limit 3879.30; low 3889.00 | no fill |
| ES ×2 (retired) | buy limit 7558.25 | no fill |

**Net +$416.90 — and it is one trade, not two.** Both CL legs expressed the same 6.3-point
collapse in opposite directions: one was right because it followed the gap, the other was
wrong because it was buying a level that no longer existed. Writing it as "+$417 on the
desk" would double-count a single move.

**The uncomfortable part, stated plainly.** The leg that earned is the one measured at
−$2.40 per trade over 930 sessions; the leg that lost is the one with the better recent
record. One session is not evidence in either direction, and the 930-trade estimate is
still the best guess for tomorrow.

**Automated so the record grows without me:** `.github/workflows/paper-causal.yml` runs
Monday–Friday at 23:10 UTC — refresh bars, settle the completed session, commit the bars
and the ledgers. Judging the desk after two days is only worth anything if the two days
actually get recorded.

## 2026-11-04 (xviii) — the nightly job booked a session that had not happened yet

**What the bot recorded.** The first two runs of `paper-causal.yml` committed
`paper: settle 2026-11-02` and `paper: settle 2026-11-03`. The 11-02 one was right. The
11-03 one was **wrong**: it booked a long from 96.81 for −$11.48. The real 11-03 session
opened at **96.30**.

**Why.** Yahoo relabels the futures daily bar to the new session at **23:00 UTC**, an hour
after the 22:00 UTC close. The job ran at 23:44 UTC, so the last bar in the file was dated
"2026-11-03" and held 44 minutes of the session that had just opened. That bar's open was
96.81 — the number the bot used. `--settle-today` (added in xvii) told the runner that a
bar dated today was finished, which is true at 22:30 UTC and false at 23:44 UTC. The
guard I had removed was right and the flag I added to get past it was the bug.

**Repair.** Both ledgers were restored to the pre-bot commit and re-settled from complete
bars — no hand-edited rows, so the record stays reproducible. The real 11-03:

| leg | order | outcome |
|---|---|---|
| CL open-gap | **short** at the open 96.30, stop 98.63, target 89.32 | stopped **−$237.27** |
| CL prior-low (obs) | long 95.15 (gapped through), exit at the close 96.09 | **+$89.52** |
| ES prior-low | long 7570.75, exit at the close 7596.75 | **+$125.02** |
| GC prior-low (obs) | buy limit 3879.30; low 3904.10 | no fill |
| ES ×2 (retired) | same as ES, two micros | +$250.04, not counted |

**Net −$22.73** at one micro per leg. Two forward sessions: **+$394.17**.

**Second finding, from the repair.** The gap direction is not stable, because it depends on
a close that the data source revises: the 11-02 close was 96.26 when the 11-03 order was
published and 96.46 after revision. Above 96.26 means long; above 96.46 means short, and the
open was 96.30. The order sheet said long, the settlement booked short, and **both lost
$237** — so nothing here flatters the record, but it is a real flaw: a forward book must
freeze its direction when the order is issued, not recompute it from revised data. Logged,
not yet fixed; the cheap fix is a pending-order row written the night before.

**Schedule fixed, loudly.** `paper-causal.yml` now runs at **12:10 UTC** with no
`--settle-today`, so the forming bar is labelled today and the runner's own guard skips it
unaided. The flag itself now **refuses to run outside 22:00–23:00 UTC**, which is the only
window where "today's bar is finished" is true. Verified: the refusal exits 1, a re-run
books nothing twice, and an assertion walks every ledger for a row dated after the last
finished session.

**Which is why 2026-11-04 is not in the table.** At the time of writing the session is a
few hours old. Its bar exists, and settling it would repeat the mistake above in a smaller
way.
