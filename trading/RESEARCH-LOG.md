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
