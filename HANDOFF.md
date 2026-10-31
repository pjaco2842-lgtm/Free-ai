# Handoff — 2026-10-26 (latest: $2,500 account reality check)

> **For the trading desk, read `trading/HANDOFF-DESK.md` instead.** That file (2026-10-31)
> holds the current account, the live paper book, every settled research question, the
> test counts and the honesty conventions. This page covers the agent kit, the security
> work and the earlier research, and parts of it are superseded.

## Where the project is
Free Claude Code + a free model gateway, a durable task worker, and a paper-trading
desk for NQ futures are built and security-audited. Nothing is running yet: the Mac
setup has not been started, so all of this exists as files in this repo.

## Done and verified
- **Free agent kit** — `setup-cc-free.sh` installs Claude Code + a local LiteLLM
  gateway pointed at a free Gemini/Groq key; `ccg` is the launcher. Gateway binds
  `127.0.0.1:4000`, telemetry off. Shell syntax checked only — never run end to end
  on a Mac.
- **Paper trader** — `trading/paper.py` verified against live NQ data: 4 trades,
  equity $25,302, `trading/paper/status.md` written. Sample is 4 trades; that proves
  it works, not that it wins.
- **Backtest honesty harness** — `trading/luck.py` (coin-flip test), `research.py`,
  `scanner.py`, plus two Pine v6 scripts for the chart side.
- **Skill safety** — `agent/scan-skill.sh` wraps NVIDIA SkillSpector: installs it,
  reads folder / `.zip` / `.skill` / git URL, refuses a target with no `SKILL.md`,
  exits 1 on critical findings. Verified on a benign zip (0/CLEAN), a deliberately
  malicious zip (100/YARA), a non-skill folder (refused), and a GitHub URL.
- **Our own skill** — `skills/nq-desk/SKILL.md` declares its tool scope; scans CLEAN.
- **Third-party skills read in full** — ponytail, addy-agent-skills, day-trader-skill:
  515 files, 131k lines, every network/exec/write call site reviewed. No malware.
  ponytail's task board is on by default (local CSV only) and it runs a Node hook on
  every prompt; day-trader's broker module only writes tickets, never places orders.
  Verdict and method: `agent/skill-audits/2026-10-26-three-packs.md`.
- **Security fixes this round** — worker commands get a scrubbed child environment
  (no `GEMINI_API_KEY`), credential paths refused, `safe_path` prefix bug fixed;
  TradingView webhook fails closed, constant-time secret, replay + dedupe + rate
  limit. Both verified live.
- **Dependencies** — runtime CVEs 20 → 1, all deps 27 → 5, 47 packages removed.
  Server builds clean; 372/372 test files, 4599 tests pass on the updated lockfile.
- **Audit trail** — `SECURITY-AUDIT.md` (narrative) and `SECURITY-CHECKLIST.md`
  (all 70 requested items with a verdict each).
- **Strategy sweep** — `trading/lab.py` tests 9 rule families × 22 markets, validating
  each rule in BOTH directions of time, then against 500 random-entry versions.
  **198 combinations → 24 positive both ways → 3 beat luck in both halves.**
  Full record: `trading/RESEARCH-LOG.md`, entry 2026-10-26 (d).
- **Two bugs found and fixed** — `simulate()` and `coin_flip()` both overwrote the
  `entry` flag with a price, so every open-based rule after its first trade entered a
  day late. Fixing it took the six-market sweep from 4 to 11 survivors. Any number
  quoted from an earlier log entry is superseded.
- **Account model** — `trading/target.py`: whole-contract sizing, time-to-+5% measured
  from every start date, correlation, parameter-neighbour stability, edge-haircut
  stress. Median **10.8 months to +$1,250 at 2% risk**, 19% max drawdown, 3 breaches
  of −10%. At 3% risk the drawdown is 47% — that is the account-killer.
- **$2,500 account reality (corrected)** — `--micro` converts **only ZS** to the real
  MZS spec (500 bu, 0.5-cent tick); `MARKETS` already holds MNQ/MYM values for NQ/YM,
  so the earlier blanket 1/10 scaling was wrong in both directions. `--risk` is now a
  planned risk budget per **day**, not per trade, plus a 20-contract daily cap.
  Corrected result at $2,500 / 2% daily: 65 trades over 16.3 years, **final $2,457**,
  −0.1%/yr, 12.2% max DD, eight −10% breaches, 153 signals skipped — the goal is never
  reached. The old "+3.4%/yr, ~71 years" figure is **retracted**. Record:
  `trading/target_2500_micro.json`, RESEARCH-LOG entry 2026-10-26 (e).
- **Lucid 25K evaluation test** — `target.py` gained `--lucid-max-loss`, `--consistency`,
  `--lucid-daily-loss-limit` and a `lucid_start_sweep` replay that starts a fresh
  $25,000 account on every historical signal date and applies EOD trailing drawdown
  plus largest-day/gross-profit consistency. Results at 0.5% / 1% / 2% planned daily
  risk: **1.0% / 18.8% / 25.6%** of starts pass both gates without breaching $1,000
  (breaches 0 / 114 / 145). Median pass at 1% is ~603 calendar days. Daily bars only —
  an approximation, not an official simulator. RESEARCH-LOG entry 2026-10-26 (f).
- **Karpathy skills repo (new)** — `multica-ai/andrej-karpathy-skills` pinned commit
  `71c5c70`, scanned with NVIDIA SkillSpector **v2.12.0 static pass**: **27/100 CAUTION,
  0 critical, 0 high, 8 medium**. All 8 are text-pattern hits on example code and the
  words "without asking" / "without checking" in prose plus paths in a README table —
  the tree has 9 files, **no scripts, no hooks, no network calls, no key/home access,
  no invisible characters** (`--deep` confirms). Safe to use; it is instructions, so it
  changes agent behaviour by design. Report: `agent/scans/andrej-karpathy-skills-2026-10-26.md`.
  Added to `Free ai`.
- **Repo list verified** — the seven real engines from the transcript (Lean, Nautilus,
  backtesting.py, vectorbt, FinRobot, TensorTrade, StockSharp) are added to `Free ai`.
  **`PiBroker`, `Lumibuy` and the "55k-star Free Trade bot" do not exist** (zero search
  results); a name nobody can verify is how a lookalike repo gets planted, so they are
  deliberately not listed.
- **Forward ledger** — `trading/forward.py --scan` appends every completed session's
  signal for the three surviving rules, gated on a `since.txt` start date so history
  can never be back-filled into it. Started 2026-10-26; currently empty by design.
- **The five requested December contracts (new)** — `trading/edge.py` scores ~9,300
  stop/target/hold combinations on NQZ2026, ESZ2026, GCZ2026, CLZ2026, NKDZ2026
  (via the front-month continuous feed), on both halves of history, then re-chooses
  settings using ONE half and scores the other. Findings:
  * **Win rate is cheap.** 2,942 of 9,288 settings won ≥50%; only 499 were positive in
    both halves. Best win rate found: **92.9%** at **+0.21R** average — you win and
    earn nothing, because the target is a quarter of the stop.
  * **One setting does both:** ES `inside_day` 0.5/1.0/5 — **58.1% win, +0.62R avg,
    +26.7R over 43 trades, positive in both halves, coin-flip p < 0.01.** This is the
    ES `inside_day` follow-up that item 4 of the old "Next" list asked for.
  * **Blind selection test:** ES fade, CL fade and NKD continue-trend survived; NQ
    (−4.4R) and GC (−16.6R) failed. NKD `continue_trend_day` 0.5/3.0/5 was picked
    **identically in both directions**, the strongest single result in the study.
  * **The number that matters:** with settings locked on 2009–2019 and the account run
    on 2020–2026 only — **38 trades, final $24,603, −0.2%/yr, 51 signals skipped** for
    not fitting the risk budget. The +8.4%/yr full-history figure is hindsight; this
    out-of-sample one is the honest end.
  * **Affordability at $25k / 1%:** MES $199 and MCL $218 fit; MNQ $478 and MGC $490
    do not; **NKD is $3,946 = 15.8% of the account** — the best-measured signal here is
    untradeable at this size. That is why the curve stays flat, not the win rate.
  * **$1,250 in one week:** best measured pass rate is **3.0%** at 1% daily risk (4.9%
    at 2%, with 35% breaching $1,000 first). The basket fires ~37x/yr, so a week holds
    ~0.7 signals. No sizing fixes a missing signal.
- **Live paper basket (new)** — `trading/basket.py` trades only what survived the blind
  test (ES inside_day, ES fade, CL fade), records NKD/NQ/GC without trading them, and
  writes an append-only ledger at `trading/basket/ledger.jsonl` with entry/stop/target/
  exit/R and library-size contracts. `--pending` prints tomorrow's resting orders.
  Beginner walkthrough: `trading/START-HERE.md`.
- **The desk (new, 2026-10-29)** — `trading/desk.py` runs seven agents over every
  signal: trend/structure/momentum make the bull case, **skeptic** argues against and
  can veto, **edge** prices reward minus cost, **odds** gives a 95% interval on the win
  rate, **volatility** sets size. A chair trades only on 2/3 context agreement, no
  veto, expectancy ≥ +0.10R and a win-rate lower bound above a coin flip. Every
  argument lands in `trading/desk/decisions.jsonl`.
  * **Fills are resolved on fifteen-minute bars** (four thousand per symbol), so the
    desk can see whether stop or target actually traded first and at what time of
    night, instead of guessing the pessimistic order from a daily bar. Rows that fall
    outside intraday coverage are labelled `daily` and kept out of the 15m statistic.
  * **Two ledgers on purpose:** `ledger.jsonl` is forward and starts the day the desk
    first ran (never back-filled); `shadow.jsonl` is a `--backfill N` replay for
    reading today. The report keeps them in separate sections so a replay can never be
    mistaken for evidence.
  * **Agents read the signal night, not today.** They are handed `bars[:idx+1]`, so a
    trade from three weeks ago is judged on what was knowable then. This was a real
    bug: the first version evaluated everything against the newest bar.
  * `.github/workflows/desk.yml` runs one pass an hour for free, commits only when a
    trade actually appears, one permission, action pinned to a SHA, no secrets.
  * Plan and the stop conditions: `trading/TRADING-PLAN.md`.

- **The six-bot desk (2026-10-29)** — `trading/bots.py` splits the live decision
  the way the plan asks: BOT 1 opportunity (unusual movement, five setup types with
  confidence), BOT 2 catalyst (verified news + computed recurring events), BOT 3
  sentiment (headline lexicon + price crowding), BOT 4 levels (entry/stop/target),
  BOT 5 risk (the only bot that can block), BOT 6 final (BUY/SELL/WAIT/SKIP).
  Guardrails are structural: BOT 5's reject is final, BOT 2 can only delay, BOT 3
  cannot veto, and `validate_call()` fails malformed output to SKIP. First board
  (2026-10-29): ES `WAIT 53`, CL `WAIT 29`, NQ/GC/NKD `SKIP` on size.
- **The reading swarm** — `trading/swarm.py`: 300 readers = 20 public feeds × 5
  markets × 3 concepts, no key. Live run: 2,595 item checks, 16/20 feeds reachable,
  23 fresh + 37 context kept, **1,265 stale, 45 duplicate, 5 future-dated and 5
  undated rejected before any score exists**. Dedupe is per market (a global hash
  gave every story to whichever market was read first — real bug, fixed). Headlines
  are sanitised (tags, control chars and URLs stripped) and never joined into an
  instruction.
- **Research engine** — `trading/research_engine.py`: JSON spec → `KEEP`/`REJECT`
  against the eight refusals (sample, 3× costs, parameter neighbourhood, five time
  slices, random-entry p, t-stat, entry timing). Worked example: CL fade, +0.336R
  out of sample, p=0.128, t=0.64 → **REJECT**. `--loop` adds the improvement cycle
  with two anti-overfitting guards (holdout improvement required; significance bar
  rises `1.5 + 0.12 × attempt`), logging to `trading/lab/experiments.jsonl`.
- **Execution + risk engine** — `trading/execution.py`: DRAFT→VALIDATED→SUBMITTED→
  ACCEPTED→FILLED→CLOSED with an all-or-nothing `validate()` (BOT 5 approval, stop
  side, position cap, daily stop, order cap, spread, planned market, not
  record-only), a `trading/desk/KILL` kill switch, and every transition appended to
  `desk/orders.jsonl`. 45-session replay: 3 orders, 3 closed, 18 transitions, +1.41R.
- **10,000-path replay** — `trading/montecarlo.py`: block bootstrap (block of 3, so
  losing streaks survive), fixed +$1,250 / −$1,000 barriers, consistency check.
  Honest mode (`--honest`, drops the inside-day rule whose parameters were chosen on
  the full sample): **28 out-of-sample trades, +0.196R mean, 74.9% reach target,
  24.8% breach, median 36 trades, 95th-pct drawdown $1,815**. The unflagged run says
  98% over 41 trades — that flag exists because the first version made exactly that
  hindsight error.
- **Dashboard + alerts** — `trading/dashboard.py`: one static HTML page (no server,
  no JS, strict CSP, every string HTML-escaped because it renders feed text),
  showing account, six-bot board, levels, risk meters, system health, forward
  ledger, committee audit and replay probability. Alerts only for conditions that
  change what a person does.
- **The consistency arithmetic (finding, not bug)** — BOT 5's first board revealed
  that a 6:1 bracket pays ~$967 on MES while Lucid's 50% rule caps a best day at
  $625 on a $1,250 target. **A single full win voids the pass even when the target
  is hit.** Either the target must be ≥2× the win (~$1,934) or the exit must be
  partial (~$480–$625), which changes the bracket to ~2.5:1 and must be
  re-backtested. The gate is now fatal only on a *realised* breach, so the desk
  keeps recording instead of going permanently silent.
- **Four bugs found and fixed today** — (1) swarm dedupe was global, not per market;
  (2) the first Monte Carlo reported 99.8% because it replayed the trades the
  settings were chosen on; (3) execution counted "orders already sent today" across
  nineteen years of history and rejected 511 trades against a one-day cap; (4) it
  also reported 100-tick slippage by comparing the 18:00 Globex open with the 09:30
  print. Slippage cannot be measured from a paper fill at all; that is now stated
  instead of faked.
- **Operator manual** — `trading/DESK.md` (13 sections: what runs each hour, the six
  bots, the swarm, research refusals, the loop, execution, dashboard, the
  consistency arithmetic, both probability numbers, security posture, daily
  commands). `trading/desk/calendar.json` seeded for FOMC/CPI dates the engine
  deliberately does not invent.

- **Thirteen bots, not six (2026-10-29)** — `bots.py` grew a context layer around
  the trade: **0 regime** (trend/chop/high-vol/drift, which the setup list is scored
  against), **7 session** (cash hours vs Globex, how far the day has travelled),
  **8 liquidity** (thin book, flat bars), **9 roll** (blocks new risk inside 3 days),
  **10 benchmark** (vs simply holding), **11 calibration** (per-agent accuracy from
  settled decisions), **12 governor** (drawdown breaker, daily stop, 4-loss streak,
  kill switch). Four doors now close in ascending authority: BOT 2 delays a session,
  BOT 5 rejects a trade, BOT 9 refuses new risk near a roll, BOT 12 halts everything
  and overrides BOT 6. First 13-bot board: ES `drift / gov run / roll 41d`,
  opportunity 35 → `WAIT 52`.
- **Analytics (new)** — `trading/analytics.py` answers the four questions that make
  the desk auditable: which rule earns its keep (per rule/market), how trades end
  (stop/target/clock, cash hours vs overnight), which agent is actually right
  (directional accuracy from recorded votes, vetoes included), and whether confidence
  means anything (Brier score once calls join outcomes). Everything under 20 samples
  prints its size and refuses to conclude. Board calls are appended to
  `desk/calls.jsonl` because the board file itself is overwritten hourly.
## In flight
Nothing half-edited. `trading/paper/` was deleted after the verification run so the
repo stays clean — the first real run recreates it.

## The three rollout steps (user's plan, in this order)
1. **Manual paper trading** with the TradingView indicators. Code lives at
   `trading/ai-signal-bot.pine` (structure + momentum, JSON alert payload, stop 1×ATR,
   target 2R, closed-bar only) and `trading/structure-range-compass.pine`. Paste into
   TradingView → Pine Editor → Add to chart → set an alert on any `alert()` call.
2. **Phone / GitHub / CodeSpaces** — same repo in the browser, no local install.
3. **Mac last** — `bash setup-cc-free.sh` (never run end to end yet).

## Next
0. Push this branch, then enable the workflow: repo → **Actions** → *desk* → **Run
   workflow** once by hand to confirm it works, then leave the hourly schedule on.
   GitHub disables scheduled workflows after 60 days of repository inactivity; the
   workflow's own commits count as activity, so it keeps itself alive.
0b. Run `python3 trading/desk.py --backfill 60` and read `trading/desk/report.md`
   before trusting a forward signal — it exercises every agent on real sessions.
0c. Run `python3 trading/basket.py --scan` after each 5pm ET close. Judge it at 20
   closed trades, not before; `--report` prints the backtest comparison.
1. Walk the Mac setup: Terminal → `git --version` → Homebrew → `python@3.12 node` →
   clone → Gemini key → `bash setup-cc-free.sh`. Nothing has been run on the Mac yet.
2. Find an uncorrelated, affordable rule. Today's book is now six markets instead of
   three, but the affordable subset is still ES + CL — one index and one energy. That
   is the single biggest weakness in the plan.
3. The real open problem is **frequency**, not accuracy: ~37 signals/yr across five
   markets against a 20-signal-per-week requirement for +$1,250 in seven days. More
   markets and an intraday version are the only honest routes; more size is not.
4. Decide `HOST=127.0.0.1` in `.env` (dashboard currently answers to the whole LAN).

## The $2,500 question
10.5x is not a risk setting, it is a different business. Corrected micro sizing on
$2,500 with a 2% daily budget ends at **$2,457 after 16.3 years** — flat to slightly
down. The earlier "+3.4%/yr, ~71 years" figure came from a double-scaled contract map
and is retracted. The honest routes are: add capital until the rules fit at full
size, trade the evaluation instead of the account, or lower the target. Do not let a
model be tuned until it "reaches" $26,250 — that is how the entry-timing bug got
believed the first time.

## Avoid
- Never paste a provider key into chat, a commit, or a screenshot. Keys go in `.env`
  or the dashboard only.
- `npm audit fix --force` — it drags in major upgrades; `zod` 4 is a separate task.
- Do not read `.env` while inspecting the repo; if a task needs a value, ask.
- Don't treat the 4-trade paper result as an edge. It needs weeks of forward test, and
  `trading/luck.py` must clear the coin flip first.
- Don't quote a number from a RESEARCH-LOG entry older than 2026-10-26 (d): those runs
  contained the entry-timing bug. Re-run before believing a figure.
- Don't size above 2% per trade on $25k. At 3% the same rules produce a 47% drawdown
  and three −10% breaches; the sweep is not an argument for leverage.
- Don't add a broker or wallet connection. Paper only unless the user says otherwise in
  a separate request.
- Don't install a repo by name from an AI-generated "top 5" list. Search the exact
  owner/repo first; if it returns nothing, stop. `PiBroker` and `Lumibuy` are invented.
- Don't promise or chase 10x on $2,500. See "The $2,500 question".
- **Don't trade NKD on a $25,000 account.** Its stop is $3,946 (15.8%). Record the
  signal, skip the trade. This is the trap the whole five-contract idea walks into.
- Don't treat a ≥50% win rate as an edge. 2,942 settings had one and 84% of them lost
  money in at least one half of history.
- `trading/webhook.py` will refuse to start on a public interface without
  `TV_SECRET` — that is the fix, not a bug.

## Commands and paths
```
bash setup-cc-free.sh              # one-time install (Mac)
ccg                                # Claude Code on the free gateway
python3 trading/paper.py --once    # one paper tick
python3 trading/paper.py --status  # equity, open position, recent trades
python3 trading/lab.py             # 9 rules x 22 markets, both time directions
python3 trading/lab.py --fixed     # same params in both eras, no re-selection
python3 trading/target.py --risk 0.02    # sizing, time-to-+5%, correlation
python3 trading/edge.py            # 9,300 exit combos on the five contracts, blind-tested
python3 trading/basket.py --pending     # tomorrow's resting orders, writes nothing
python3 trading/basket.py --scan        # log finished sessions, show open trades
python3 trading/basket.py --report      # forward ledger vs backtest expectation
python3 trading/forward.py --scan  # append this session's signals
python3 trading/forward.py --report
python3 trading/luck.py            # coin-flip test for a strategy
./agent/scan-skill.sh --deep <path|zip>   # code read + verdict, before installing
npm run build -w server && npx -w server vitest run
```
Repo root holds `agent/`, `trading/`, `skills/`, `SECURITY-*.md`, `HANDOFF.md`.
Gateway lives outside the repo at `~/.llm-gateway/` (`env.sh` is `0600`).

## Open questions for the user
- `HOST=127.0.0.1`, or keep LAN access for the phone?
- Do the zod 4 upgrade now, or after the paper trading has a few weeks of data?
- Which of the ten new trading repos get added to the `Free ai` list (Lean and Nautilus
  are the two with real futures support; VectorBT could replace the homegrown backtester).
