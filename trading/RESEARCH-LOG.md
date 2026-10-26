# Research log

Every idea that gets tested, with its parameters and what happened. Never edited to
look better afterwards; new entries go at the top. The count at the bottom is the
point: most ideas die, and forgetting how many died is how you fool yourself.

Rules for an entry: date, idea in one line, exact parameters, in-sample result,
out-of-sample result, coin-flip p-value, verdict.

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

Ideas tested: **2** families, plus the two videos' three specific claims.
Survived out-of-sample: **2 of 5** symbols in family 1; **1 of 5** in the fade rule (NQ only).
Beat the coin flip at p<0.05: **0**.
Closest thing to an edge: NQ fade-after-trend-day, p 0.08 / 0.10, positive in both
windows and across six parameter settings — a forward-test candidate, not a funded one.
Cleared every gate: **0**.
