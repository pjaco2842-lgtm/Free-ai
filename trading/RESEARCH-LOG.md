# Research log

Every idea that gets tested, with its parameters and what happened. Never edited to
look better afterwards; new entries go at the top. The count at the bottom is the
point: most ideas die, and forgetting how many died is how you fool yourself.

Rules for an entry: date, idea in one line, exact parameters, in-sample result,
out-of-sample result, coin-flip p-value, verdict.

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

Ideas tested: **1** family (5 symbols × 1 parameter set each).
Survived out-of-sample: **2 of 5**.
Beat the coin flip: **0 of 5**.
Cleared every gate: **0**.
