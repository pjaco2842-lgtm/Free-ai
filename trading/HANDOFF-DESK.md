# Handoff — the trading desk, everything learned so far

> **AUDIT WARNING — 2026-10-31:** The old sweep, paper fill engine, account walks,
> and many claims below are **unreliable**, not proven strategies. Daily-bar highs
> and lows can occur before entry; the advertised buy stop below market is not a
> standard buy-stop order; the luck test uses completed-bar information; and account
> simulations miscount sessions and mishandle consistency. Both paper workflows,
> the paper runner, and the legacy sweep are paused where this revision is installed.
> The $0 forward ledger remains intact. The November 2 order is withdrawn, not standing. Read the audit in `trading/RESEARCH-LOG.md` and
> `trading/desk/audit-search.md` before using any historical report. The 80% win,
> 84% pass, 14-session and replay claims are retracted; do not infer impossibility
> of three-day passage from the flawed tests. A scheduled workflow exists, but its
> status is unverified; the pause only applies where these changes are present.
> Prior reports are historical records, not current instructions.

**Last updated: 2026-10-31.** This file is the memory of the desk. If a chat dies, a new
one reads this and nothing else is lost. Read it before touching anything in `trading/`.

The sections below are preserved historical claims, **not current instructions or
validated results**. Use the warning above and research-log entry (o) instead; the
old bottom-of-file prompt is superseded.

---

## 1. The account, exactly

| | |
|---|---|
| firm / product | Lucid Trading, **LucidFlex evaluation** |
| size | **$25,000** (one account) |
| profit target | **+$1,250** → closes at $26,250 |
| max loss | **$1,000**, end-of-day trailing |
| floor | highest **closing** balance − $1,000, stops moving (locks) at **$25,100** |
| consistency | largest single day ≤ **40%** of profit — a real pass gate, evaluation only |
| daily loss limit | none |
| phase | **paper only until 2026-11-13** |
| then | when the 25K banks its cushion: fund it to **+$2,000** or buy a **50K** |

Machine-readable: `trading/desk/account.json`. Code that reads it: `paper_oracle.py`
(`account_rules()`), `pick_book.py`, `mine26k.py` (constants).

**Paper only. Do not add a live broker without a separate, explicit request.** No keys in
the repo, never read `.env`.

---

## 2. What the desk trades right now

`trading/desk/mined-book.json` — one rule, one micro:

> **ES (MES):** buy a **stop at the prior day's low**, but only when the session **opens
> above the prior close** (`gap: with`), **long only**, stop **1.0 × yesterday's ATR**,
> take **0.5R**. No target at the close, no trailing, no break-even moves.

| measure | value |
|---|---|
| trades since 2009 | 820 |
| win rate | **77.7%** |
| $/trade | **+$49** |
| worst drawdown | −$1,086 |
| years positive | **18 of 18** (weakest 2018, +$33) |
| 2023 onward | 204 trades, **80.4% win**, +$95/trade |
| 2022 (bad tape) | +$6,218 over 75 trades |
| 2025 / 2026 | +$4,087 / +$5,792 |
| **25K pass rate** (2023+) | **91%** raw, **84%** with the 40% consistency rule |
| breach rate | **3%** |
| median sessions to target | **14** |
| inside 3 / 5 / 10 / 15 sessions | **0% / 5.4% / 21% / 57%** |
| risk in a median session | **$413** |
| luck test | beat **500/500** random fills (100th pct) |
| plateau | 6 of 6 parameter neighbours positive |

Win rate comes from the **0.5R target**: average win ≈ $170, average loss ≈ $330. Two
wins pay for one loss. That is the trade being made.

Forward record: `trading/desk/oracle-forward.md`, state `trading/desk/oracle-state.json`
(reset 2026-10-31 — the ledger before that belonged to the previous book and was void).
Replay of the last 40 sessions on this rule: **10 trades, +$538.94**
(`trading/desk/oracle-replay.md`).

**Superseded book (fallback, still valid):** ES `nday_fade-5 0.5A tp1` + ES
`nr_break-2 1.0A tp1`, one micro each. 88% pass with consistency, 7% breach, 59% win,
median 26 sessions, $405 median session risk. Slower and lower win rate than the current
rule, roughly the same pass rate.

---

## 3. The research, and what it cost

Configurations tested so far, by script — the count matters, because the more you try the
more wins by luck:

| script | space | verdict |
|---|---|---|
| `lab.py` | 198 rule/market combos, both directions of time | 3 beat luck both ways |
| `edge.py` | **9,288** stop/target/hold settings × 5 contracts | 499 profitable both halves; best win rate 92.9% at +0.21R (a quarter-stop target — wins often, earns nothing) |
| `lab26k.py` | **28,350** per market (ES, NQ) | the first 26,000-style sweep; `oracle-book.json` came from it |
| `atr_grid.py` | 144 rule × stop × exit lines, walked as a 25K from every start | settled the stop question (§4) |
| `pick_book.py` | candidate books, account-walked | settled the ES pair |
| **`mine26k.py`** | **287,280** (57,456 in each of ES, NQ, GC, CL, NKD) | **the current book** |
| `portfolio.py`, `target.py`, `montecarlo.py`, `luck.py`, `swarm.py`, `basket.py` | multi-account and sizing tools | supporting, not current |

`mine26k.py` space per market: **38 rule variants** × **7 stops** (0.25–2.5 ATR) × **4
exits** (close, 0.5R, 1R, 2R) × **54 filters** (gap 3 × day-of-week 3 × trend 2 ×
direction 3). Five markets → 287,280. Runtime ~65 s.

### The gates every result had to pass (the video's protocol, implemented)

1. **Unseen years** — positive 2009–2019 **and** 2020–2024, with ≥150 / ≥100 trades.
2. **Parameter plateau** — ≥4 of 6 neighbours (lookback, stop, exit) also positive out of
   sample. "Works at 1.0 but not 0.75" is a coincidence.
3. **Recent regime** — 2025–2026 not negative.
4. **Luck** — beat the **95th percentile of 500 random fills** on the *same days, same
   side, same stop, same exit, same costs*. Only the fill price is randomised.
5. **The account** — walked as $25,000 with the trailing floor and the 40% consistency
   rule, **from every starting trade**, in the **2023+ era** (a stop's dollar size is a
   property of the price level; 2009–2020 was traded at a fifth of today's prices).

Result: 9,629 of 287,280 positive in both halves → **289** through all gates. Chance alone
would pass ~30 at a 95th percentile. So there is an edge in the population, and it is
narrow.

**Every survivor was `nday_fade`.** Nothing else made it.

---

## 4. Settled questions — do not re-run these

| question | answer | evidence |
|---|---|---|
| Does the "Oracle" (`prevclose_break`, prior-close break both ways) work? | **No.** 47–48% win, **−$7 to −$16 a trade**, 65–90% of attempts breach | `atr_grid.py`; nothing survived `mine26k.py` either. The old 93% win rate was the both-orders-fill look-ahead artefact |
| Do wider stops (2.0–2.5 ATR) raise the pass rate? | **No on a 25K.** Win rate rises 43%→54% then flattens; pass rate 25% (0.5A) → 52% (1.0A) → 57% (1.5–2.0A) → 56% (2.5A). A wider stop buys win rate by making each loss bigger | `atr_grid.py` |
| Can NQ pass a 25K? | **No.** One micro at 1.0 ATR = **$1,043** = the whole buffer; every NQ line fails the $500 session-risk cap. NQ breakouts reach the target 90% of the time but satisfy consistency only **23%**, because one $2,000 day is >40% of a $1,250 target | `atr_grid.py`, `pick_book.py`, `mine26k.py` |
| Is NKD tradeable on 25K? | **No.** 1.0 ATR = **$5,600–8,700** at today's volatility (6–8× buffer). It *looked* fastest in the sweep (5–6% of starts inside 3 sessions) purely because most historical attempts were made when the index was a fifth of today's level | `mine26k.py` |
| Can we make $1,250 in **3 sessions**? | **No honest rule did.** 0 of 204 starts. $417/session ≈ 1.3R a day at 60% win, every day, with consistency intact | `mine26k.py` |
| Does a machine-learned signal add anything? | **Not at daily granularity.** Walk-forward ridge (10 features, refit each year on prior years only, no shuffling) produced no survivor | `mine26k.py` family `model` |
| Do gap / inside-day / MA-pullback / pin-bar / body-continuation / Monday-gap-fade rules survive? | **None did**, at any stop or exit | `mine26k.py` |
| Is the 40% consistency rule avoidable? | **No**, it is a pass gate. It is what eliminates NQ and every big-day strategy on a 25K | `pick_book.py`, `atr_grid.py` |

---

## 5. Honesty conventions baked into the code (keep them)

- One position per market per session. If a day would fill both a long and a short order,
  the day is **skipped** unless the open already says which side — taking only the good
  half is the look-ahead that once produced a 93% win rate.
- Stops are sized from **yesterday's** ATR, never the bar's own.
- When a stop and a target are both touched, the **stop** wins.
- One tick of slippage per side plus $1.24 commission per side.
- `mine26k.py` runs a **parity check** at startup: its scalar replay must reproduce the old
  replay trade-for-trade (2,440 ES trades) or it refuses to write a book.
- Every idea and its parameters go into `trading/RESEARCH-LOG.md` **before** it is
  believed. New entries at the bottom, formatted like entries (m) and (n).

**Known limits:** Yahoo gives daily bars from 2009, but only 7 days of 1-minute and 60 days
of 15-minute data. The video's actual edge — "break out early in the day, tight stop, hold
to the close" — **cannot be tested over 17 years here**. Everything the desk does is a
daily-bar proxy. If real intraday history is bought, that is the next genuine frontier.

---

## 6. File map

| file | what it is |
|---|---|
| `trading/HANDOFF-DESK.md` | **this file** — the whole memory |
| `trading/RESEARCH-LOG.md` | every idea tested, with parameters and verdicts, entries (a)–(n) |
| `trading/desk/account.json` | the account rules + the current book + the 50K plan |
| `trading/desk/mined-book.json` | the live book (what `paper_oracle.py` trades) |
| `trading/desk/mine26k.md` / `.json` | the wide sweep report: space, gates, axis tables, top of the pile |
| `trading/desk/atr-grid.md` | the stop/exit grid on a 25K |
| `trading/desk/oracle-forward.md` | the forward paper record (the live scoreboard) |
| `trading/desk/oracle-replay.md` | the last 40 sessions replayed on the current book |
| `trading/desk/pick-book.md`, `portfolio.md`, `board.md` | older book comparisons |
| `trading/mine26k.py` | the sweep + book builder (the research engine) |
| `trading/paper_oracle.py` | the forward paper runner for whatever book is live |
| `trading/pick_book.py`, `atr_grid.py`, `lab26k.py`, `lab.py`, `edge.py` | earlier sweeps |

### Commands

```bash
cd trading
python3 mine26k.py                       # the full 287,280 sweep (~65 s), rewrites the book
python3 mine26k.py --risk-cap 650        # same, allowing a bigger single-session risk
python3 paper_oracle.py                  # forward step: appends the last completed session
python3 paper_oracle.py --replay 40      # last 40 sessions, forward record untouched
python3 -m py_compile mine26k.py paper_oracle.py
```

The forward runner only ever processes sessions it has not already recorded, so running it
hourly, daily or weekly produces the same ledger. Orders for the next session are printed
in `oracle-forward.md` with the worst case against the $1,000 buffer.

---

## 7. Where this stands and what comes next

- **2026-11-02 → 11-13:** paper sessions accumulate automatically. Median 14 sessions to
  the target means expect roughly **$700–900 of the $1,250** by the 13th, not funded.
- **Open question 1:** does the 80% win rate hold forward? The backtest says it should; the
  forward record is the only thing that can answer it. Do not add risk before 20+ trades.
- **Open question 2:** the 25K is the bottleneck, not the rules. Two accounts on this book
  or a 50K unlocks the NQ and wider-stop books, which is where the bigger $/trade lines
  live — but they were rejected here for buffer reasons, not edge reasons. Re-run
  `mine26k.py` with the 50K constants before buying one.
- **Not done:** true intraday testing (needs paid 1-minute history), multi-account
  portfolio selection on the new book (`portfolio.py` still models the old 50K trio).

---

## 8. Paste this into the next chat

> Read `trading/RESEARCH-LOG.md` entry (o) first. The paper desks are paused and no
> strategy or order is approved. The legacy fills and pass rates are unreliable; do
> not present replays as earnings. Preserve both forward records. Confirm the 25K
> account's customized rules with Lucid, and validate causal fills and session
> boundaries with suitable data before considering a strategy. Paper only; do not
> add a live broker without a separate explicit request. Keep the $2,000 cushion
> or 50K idea for consideration after the 25K has banked its cushion.
