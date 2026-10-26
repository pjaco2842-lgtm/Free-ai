# Handoff — 2026-10-26 (latest: research sweep + forward ledger)

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
- **Forward ledger** — `trading/forward.py --scan` appends every completed session's
  signal for the three surviving rules, gated on a `since.txt` start date so history
  can never be back-filled into it. Started 2026-10-26; currently empty by design.

## In flight
Nothing half-edited. `trading/paper/` was deleted after the verification run so the
repo stays clean — the first real run recreates it.

## Next
1. Walk the Mac setup: Terminal → `git --version` → Homebrew → `python@3.12 node` →
   clone → Gemini key → `bash setup-cc-free.sh`. Nothing has been run on the Mac yet.
2. Run `python3 trading/forward.py --scan` after each session close, then `--report`
   weekly. Three rules, about 10 signals a year — the sample is the product.
3. Find an uncorrelated, affordable rule. Today's portfolio is NQ+YM fade (r = +0.39,
   one bet twice) plus soybeans, which needs $535 of risk per contract and so cannot
   trade a $25k account. That is the single biggest weakness in the plan.
4. Test ES `inside_day` harder (+13.41R forward, p 0.006) — it missed the luck gate at
   0.080 in the other half by a whisker and is the best-looking near-miss.
5. Decide `HOST=127.0.0.1` in `.env` (dashboard currently answers to the whole LAN).

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
