# The trading plan

Written 2026-10-29. Every number here comes from a run in this repo, and every
run is cited so you can re-check it instead of trusting the document.

---

## 1. The five contracts, and what each one is actually for

| contract | feed | trade as | $/point | role in the plan |
|---|---|---|---|---|
| ESZ2026 | `ES=F` | **MES** | $5 | the only market with two surviving edges |
| CLZ2026 | `CL=F` | **MCL** | $100 | uncorrelated to ES — the diversifier |
| NQZ2026 | `NQ=F` | MNQ | $2 | record only — its edge failed the blind test |
| GCZ2026 | `GC=F` | MGC | $10 | record only — failed the blind test |
| NKDZ2026 | `NKD=F` | none exists | $5 | record only — **$3,946 of risk per contract** |

Nothing about NQ or GC is broken. Their best settings, chosen on one half of
history, lost money on the other half — which means the apparent edge was the
search finding noise. They stay in the ledger so the claim is testable rather
than an opinion. NKD is the strongest measured signal in the whole study
(+13.4R out of sample, and the same setting was chosen independently in both
time directions) and you cannot afford it: one stop is 15.8% of a $25,000
account. Recording a great trade you cannot take is not a failure, it is the
correct behaviour.

**Two contracts is thin, and that is the plan's main weakness.** ES and CL are
one index and one energy. Everything else in this document is designed to
survive that thinness rather than to wish it away.

## 2. What we trade

Three setting/rule pairs survived the blind selection test in
`trading/edge.py` (see `trading/edge.json` → `selection_test`):

| market | rule | stop / target / hold | historical | net of costs |
|---|---|---|---|---|
| MES | inside-day breakout | 0.5 / 1.0 / 5 bars | 58% win, +0.62R avg | +26.7R over 43 trades |
| MES | fade the trend day | 0.5 / 3.0 / 10 bars | ~58% win, +0.58R avg | +23.3R |
| MCL | fade the trend day | 0.5 / 3.0 / 2 bars | ~46% win, +0.55R avg | +13.1R |

All three are **enter-at-the-open** rules, which means the whole trade is a
resting order you can place the night before. You never need to watch a screen.

A 0.5/3.0 bracket is a 6:1 reward-to-risk trade that wins 46–58% of the time.
That combination is the entire edge. It also means **most trades are losses** —
a 58% win rate with 6:1 payoff loses two trades in five. Expect strings of
losses; that is the shape of a positive-expectancy system, not a malfunction.

## 3. Sizing

- **$25,000 book, 1% ($250) of planned risk per trade.** At 2% the same rules
  produce a 47% drawdown over history; the sweep is not an argument for leverage.
- **One contract until 20 closed trades.** One.
- **At most two positions open at once**, and never the same direction in two
  markets correlated above 0.70 — the desk's skeptic agent enforces this,
  because ES and NQ are close to the same bet.
- **Stop the day at −$500.** The Lucid replay shows the daily stop is what keeps
  the $1,000 trailing limit intact, not the per-trade stop.

Affordability at $25,000 / 1%: MES $199 and MCL $218 fit. MNQ $478 and MGC $490
do not. That is not a rounding error — it is why the out-of-sample account curve
is flat.

## 4. The honest expectation

Run `trading/edge.py` section 8 to reproduce: with settings frozen on 2009–2019
and the account replayed on 2020–2026 only, the book makes **38 trades in 6.8
years, ends at $24,603, −0.2%/yr**, and skips 51 signals because one contract's
stop did not fit the budget.

The +8.4%/yr figure from the full-history run is hindsight and should not be
quoted. The honest range for this book at this size is **roughly flat to
+3%/yr**, with long stretches of nothing happening.

**$1,250 in one week: about 1 attempt in 40.** Best measured pass rate is 3.0% of
historical weeks at 1% daily risk. At 2% it is 4.9% with 35% breaching the
$1,000 limit first. The basket fires ~37 times a year (about 2–3 times a month),
so most weeks contain no signal at all. No sizing fixes a missing signal.

## 5. Which prop firm rules actually bind

For Lucid's 25K evaluation ($1,250 target, 50% consistency, $1,000 end-of-day
trailing drawdown):

- **The consistency rule is not the binding constraint — the trailing drawdown
  is.** At a $1,250 target, 50% means your best day must be ≤ $625. Two clean 2R
  wins of about $625 each pass. One giant $1,250 day hits the target and *fails
  the consistency rule anyway*. That is the trap.
- **The trailing drawdown rises with your equity.** Earning $600 does not give
  you $1,000 of room; it gives you $400. Size as if the floor is following you.
- **Replayed honestly, about one attempt in five passes and more than half
  breach first** (`target.py lucid_start_sweep`, at 1% daily risk: 39/207 pass,
  114 breach). Treating an evaluation as a coin flip with a 20% success rate is
  the correct mental model, and it means **do not fund a second attempt from
  money you need**.

## 6. The committee, and why it exists

`trading/desk.py` runs seven agents over every signal:

- **bull side** — trend, structure, momentum argue for the trade
- **skeptic** — argues against, and can veto outright
- **edge** — is the reward worth the cost after commission and slippage
- **odds** — what are the chances, as a 95% interval rather than a number
- **volatility** — does one contract's stop fit the budget, which sets size

The chair trades only when two of three context agents agree, the skeptic does
not object, expectancy clears +0.10R, and the win rate's lower bound is better
than a coin flip. Every argument is written to `trading/desk/decisions.jsonl`, so
a bad decision can be traced to whichever agent argued for it.

**The chair is a filter, and filters can be wrong.** `trading/desk/report.md`
compares the average outcome of approved trades against rejected ones. If the
rejected trades do better for long enough, the chair is subtracting value and the
honest response is to loosen it or drop it — not to keep it because it feels
responsible.

## 7. What would make me stop

Written down now, while it is still cheap to be honest:

- **Twenty forward trades below +0.10R average** → the edge is not there at a
  size you can afford. Stop. Do not increase size to compensate.
- **A −$500 day followed by a revenge trade** → stop for the week. The system did
  not fail; the operator did.
- **The chair's rejected trades beating its approved ones over 40 decisions** →
  the committee is noise, and simple is better.
- **Any month where you moved a stop.** Every number in this document assumes the
  stop is honoured exactly. One widened stop invalidates the whole table.

## 8. The first thirty days

| when | what | success looks like |
|---|---|---|
| day 1 | run `desk.py --backfill 60`, read the shadow report | you can explain why each trade was taken or rejected |
| days 1–30 | `desk.py --cycle` runs itself every 15 min in GitHub Actions | the forward ledger fills without you touching it |
| weekly | read `desk/report.md` | nothing to do; it is a record, not a dashboard |
| day 30 | compare forward count to expectation (~2–3 per month) | if zero, the feeds or the roll need checking |
| 20 trades | the first real decision point | avg R vs the +0.55R backtest |

## 9. Roll risk — the thing that will quietly break this

`ES=F`, `NQ=F`, `GC=F`, `CL=F`, `NKD=F` are **continuous front-month feeds**. They
are December 2026 contracts until mid-November, then they roll. After the roll the
signals come from a different contract while the file still says `ESZ2026`.

Check `trading/edge.py` → `CONTRACTS` after **13 November 2026**. If the plan is
still running into December, re-read the roll dates for each market before
trusting another signal: ES/NQ/GC/CL roll quarterly, NKD monthly.

## 10. The bots — thirteen

`trading/bots.py` is the live desk. One classifies the market (`regime`), one
watches (`opportunity`), one reads (`catalyst`), one follows the crowd
(`sentiment`), one plans (`levels`), one protects the trade (`risk`), one calls it
(`final`), and seven more surround the trade: `session` (cash hours or overnight),
`liquidity` (is the book thin), `roll` (is the contract about to change), 
`benchmark` (are we better than holding), `calibration` (which agent has been
right), and `governor` (the desk-level circuit breaker that can halt every market
at once, including overriding BOT 6).

Four doors can close, in ascending authority: **BOT 2 delays one session**, **BOT 5
rejects one trade**, **BOT 9 refuses new risk inside three days of a roll**, **BOT 12
halts the whole desk**. Nothing downstream can reopen them.

The asymmetry is deliberate and is the whole point:

* **BOT 5 can only say no.** Its reject is final; no amount of agreement from the
  other five overrides it. The risk engine sits between the strategy and the
  execution, not beside it.
* **BOT 2 can only delay.** A scheduled high-impact release inside the window
  turns a call into `WAIT`. A dead news feed is reported as `unknown`, never as
  quiet, and changes confidence by zero.
* **BOT 3 cannot veto.** It is a word list over verified headlines plus a price
  crowding proxy. Useful, weakly weighted, never decisive.
* **BOT 6 may only emit BUY / SELL / WAIT / SKIP** plus one confidence and one
  falsifier. `validate_call()` downgrades anything malformed to `SKIP`.

`trading/DESK.md` is the full operator manual. Read it before the first session.

## 11. The reading swarm

300 readers = 20 public feeds × 5 markets × 3 concepts, no key required. The value
is not the headline count, it is the **timestamp verification**: undated items,
future-dated items, items older than the window and resurfaced duplicates are all
rejected *before* a score exists. A live run rejected 5 future-dated items, 45
duplicates and 1,265 stale ones out of 2,595 checks.

Headlines are sanitised — markup, control characters and URLs stripped — and never
concatenated into an instruction. That is what stops a crafted headline becoming
a prompt injection or a link that something later fetches.

## 12. Research, and the eight refusals

`trading/research_engine.py` turns an idea into a machine-readable spec and then
tries to destroy it: sample size, 3× cost stress, parameter neighbourhood, five
time slices, random-entry p-value, t-stat, and entry timing (look-ahead). A
strategy is `KEEP` only when all pass.

Today's worked example — the CL trend-day fade, which *looks* profitable — was
rejected on 12 out-of-sample trades, p = 0.128 and t = 0.64. That is the engine
doing its job.

## 13. The improvement loop

observe → diagnose → hypothesise → experiment → validate → keep or revert, logged
to `trading/lab/experiments.jsonl`. Two guards: a variant must improve on the
holdout it was not designed on, and the significance bar rises with every attempt
(`1.5 + 0.12 × attempt`). Without those, "the bot keeps improving" just means the
bot is memorising.

## 14. The consistency arithmetic — read this before paying for an evaluation

The bracket is 0.5 ATR stop against 3.0 ATR target, so one MES win pays about
**$967**. Lucid's best day may not exceed 50% of the profit target; at a **$1,250
target that limit is $625**. A single full win is 77% of the profit and **voids the
pass even when the target is hit**.

So either the target has to be at least 2× the win (**~$1,934**), or the exit has
to be partial (~$480–$625) so no day lands above the limit — and a partial exit
changes the bracket to roughly 2.5:1, which has to be re-backtested rather than
assumed.

10,000 replays of the 28 truly out-of-sample trades: **74.9%** reach +$1,250 before
a *fixed* −$1,000, median 36 trades, 95th-percentile drawdown $1,815. Under Lucid's
*trailing* limit the measured rate is **18.8%** passing with 114 of 207 breaching
first. Plan on one attempt in five.
