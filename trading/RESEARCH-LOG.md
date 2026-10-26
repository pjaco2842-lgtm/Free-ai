# Research log

Every idea that gets tested, with its parameters and what happened. Never edited to
look better afterwards; new entries go at the top. The count at the bottom is the
point: most ideas die, and forgetting how many died is how you fool yourself.

Rules for an entry: date, idea in one line, exact parameters, in-sample result,
out-of-sample result, coin-flip p-value, verdict.

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

## How to read this file

- A positive in-sample number means nothing on its own. It is the cost of admission.
- A positive **out-of-sample** number is interesting.
- A positive out-of-sample number that **beats random entry** at p < 0.05 is the only
  thing that earns paper money, and paper money is the only thing that earns real money.

## Tally

Ideas tested: **9** rule families, 3 specific video claims, across **22 markets** — 198
rule/market combinations, plus ~600 parameter variants within them.
Survived both directions of time: **24 of 198**.
Beat 500 random-entry versions in both halves at p<0.05: **3** (NQ fade, YM fade, ZS NR7).
Affordable at $25,000 with whole contracts: **2**.
Cleared every gate: **3 statistics, 2 practical**.

Earlier entries in this file (2010-2020 single-split results) were produced with a bug
that entered open-based rules a day late; see the 2026-10-26 (d) entry. Their *direction*
holds, their magnitudes do not. Nothing before that entry should be quoted as a number.
