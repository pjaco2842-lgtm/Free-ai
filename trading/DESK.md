# The desk, end to end

Everything in this repository that runs, why it exists, and what it refuses to do.
Written 2026-10-29. Every number here came from a run you can repeat; each one
names the command that produced it.

**Nothing here places an order.** There is no broker connection, no API key and no
account number in this repo. A "fill" is a simulated fill at a price the market
actually printed.

---

## 1. What runs, and in what order

| step | command | what it does | writes |
|---|---|---|---|
| 1 | `python3 trading/swarm.py --force` | reads 20 public feeds through 300 readers, verifies timestamps | `desk/swarm.json` |
| 2 | `python3 trading/desk.py --cycle` | records finished signals, runs the 7-agent committee | `desk/ledger.jsonl`, `desk/decisions.jsonl` |
| 3 | `python3 trading/desk.py --board` | the six bots on all five markets, right now | `desk/board.json` |
| 4 | `python3 trading/execution.py --replay` | orders through the state machine, risk gate first | `desk/orders.jsonl` |
| 5 | `python3 trading/dashboard.py` | one static HTML page + alerts | `desk/dashboard.html`, `desk/alerts.jsonl` |

`.github/workflows/desk.yml` runs all five every hour, for free, and commits only
when something changed. Steps 3–5 are `continue-on-error` on purpose: a dead news
feed must never stop the record from being saved.

## 2. The bots — thirteen, and three of them can say no

| bot | name | answers | can it block a trade? |
|---|---|---|---|
| 0 | regime | what kind of market is this — trend, chop, high-vol or drift | no — it narrows what the others mean |
| 1 | opportunity | is anything unusual, and which of five setups is it | no — scores it out of 100 |
| 2 | catalyst | what just happened, and is a release inside the window | **delays** it (`WAIT`), never authorises |
| 3 | sentiment | what the crowd is saying, and how much is hype | no — shades confidence |
| 4 | levels | trend, entry, stop, target, distance to structure | no |
| 5 | risk | does this fit the account, the day, the correlation cap, the consistency rule | **yes — `reject` is final** |
| 6 | final | BUY / SELL / WAIT / SKIP, one confidence, one falsifier | it is the call |
| 7 | session | cash hours or overnight, and how far the day has already run | no |
| 8 | liquidity | is the book thin, do bars print flat | no — costs confidence |
| 9 | roll | how close is the contract roll | **yes — blocks new risk inside 3 days** |
| 10 | benchmark | is any of this better than simply holding | no |
| 11 | calibration | has each agent actually been right | no — costs confidence |
| 12 | governor | drawdown breaker, daily stop, losing streak, kill switch | **yes — halts the whole desk** |

Three doors can close, in ascending order of authority: **BOT 2 delays one
session**, **BOT 5 rejects one trade**, **BOT 9 refuses new risk near a roll**, and
**BOT 12 halts every market at once**. Nothing downstream can reopen a door that a
higher-authority bot has shut, and BOT 6 is not allowed to try.

The regime bot is the one that makes the rest legible. A pullback in `trend_up` is
a different trade from a pullback in `chop`, so the setup list is scored against
the regime's favourites and confidence is docked when they disagree. First real
board: ES `drift`, governor `run`, roll in 41 days, opportunity 35 → `WAIT 52`.

The asymmetry is the design: **the bot that suggests a trade is never the bot that
approves it**, and BOT 5 can only say no. BOT 6 emits four words and a number;
`validate_call()` rejects anything malformed and downgrades it to `SKIP`, so a bad
record cannot become an order.

The five setups are breakout, pullback, momentum, continuation and reversal. Each
gets a confidence built from measurable pieces — range z-score against its own 20
days, relative volume, body/range, distance from the 20 EMA in ATRs, RSI, and
whether the 50/200 structure agrees. A "quiet" 40-point ES day and a loud
40-point NQ day are scored differently because they are measured against each
market's own behaviour, never an absolute number.

First real board, 2026-10-29: ES `WAIT 53` (opportunity 35 — no pattern worth
planning), CL `WAIT 29`, NQ/GC/NKD `SKIP` because one contract's stop does not fit
`$250`. That is the system working: on a nothing day it says nothing.

## 3. The swarm — 300 readers, and the timestamp layer

`20 public feeds × 5 markets × 3 concepts = 300 agents`. Every reader shares a
per-feed download cache, so 300 readers cost 20 HTTP requests. No key, no account,
no scraping behind a session.

The concept split is `policy` (rates, inflation, jobs), `shock` (war, supply,
storms, tankers) and `flow` (flows, positioning, earnings).

**The verification layer is the important part.** An LLM reading X will treat a
2024 article as breaking news; the single most dangerous failure in news-driven
trading. So before any score exists, each item is stamped and checked:

| rejection | why it exists |
|---|---|
| unparseable timestamp | an undated item cannot be placed in time |
| timestamp more than 10 min in the future | a hostile or broken clock |
| older than 24 h | not context, just noise |
| seen before (per market) | a resurfaced story is not new news |
| not in the freshness window | kept as context at 0.35 weight, never as impulse |

Measured on a live run: **2,595 item checks, 16 of 20 feeds reachable, 23 fresh
kept, 37 context kept, 1,265 stale rejected, 45 duplicates rejected, 5
future-dated rejected, 5 undated rejected.** Those five future-dated items are the
whole reason the layer exists.

Headlines are also treated as hostile input: `sanitize()` strips markup, control
characters and URLs, so a crafted headline cannot become a link, a redirect, or an
instruction. Nothing in this repository makes an HTTP request to a URL that came
from feed content.

## 4. The research engine — idea to executable, with the eight refusals

A strategy is a JSON spec: rule, params, bracket, and a falsifiable hypothesis.

```
python3 trading/research_engine.py --template reversion > idea.json
python3 trading/research_engine.py --spec idea.json
```

The verdict refuses on eight grounds, each a check that can fail: too few trades,
disappears after 3× costs, a lone parameter with no surviving neighbours,
inconsistent across five time slices, no better than random entries at the same
bracket, t-stat too low out of sample, or an entry timing that could see the
future.

Worked example, run today — the CL trend-day fade:

```
all history        24 trades  46% win  +0.548R  t=1.3
after 2020-01-01   12 trades  42% win  +0.336R  t=0.6
costs at 3x        +0.293R out of sample
random entry       p = 0.128 over 400 trials
VERDICT: REJECT — 24 total / 12 after the split (need 30/15),
                 random-entry p-value 0.128, t-stat 0.64
```

It looks profitable and it is still rejected: twelve out-of-sample trades cannot
distinguish +0.34R from luck, and one run in eight of random entries did better.
That is the engine being useful.

## 5. The self-improvement loop, and the trap in it

`--loop` runs observe → diagnose → hypothesise → experiment → validate →
keep-or-revert over five fixed hypotheses: an ATR band filter, a trend filter,
skipping the weekend gap, a tighter target, a wider stop.

The trap is that this is precisely how a strategy gets fitted to its own past. Two
guards, both enforced in code:

* a variant must improve on the **holdout** period it was not designed on;
* the significance bar **rises with the number of attempts** (`1.5 + 0.12 ×
  attempt`), so the fifth idea has to be better than the first to be believed.

Every experiment is logged to `trading/lab/experiments.jsonl`. A loop that always
finds an improvement is not learning.

## 6. Execution — the risk engine sits between strategy and fill

```
DRAFT → VALIDATED → SUBMITTED → ACCEPTED → PARTIAL → FILLED → CLOSED
                          └──────────→ REJECTED
```

`validate()` is all-or-nothing: an actionable call, a BOT 5 approval, non-zero
size, stop on the correct side of entry, under the position cap, daily stop not
hit, under the daily order cap, spread inside 3 ticks, a planned market, and not
a record-only one. Every transition is appended to `desk/orders.jsonl`, so an
order's history is a file, not a log line.

`trading/desk/KILL` is a kill switch: while that file exists, nothing is
submitted. `python3 trading/execution.py --kill` creates it; `--arm` removes it.

Replay of the last 45 sessions: 3 orders submitted, 3 closed, 18 transitions,
+1.41R. Three trades prove the plumbing, not the edge.

**Slippage cannot be measured from a paper fill**, because a simulation deals at
the price it was told to deal at. The plan assumes one tick per side, charged
inside every R. The real number needs live fills — which is the reason for a paper
month.

## 7. The dashboard

`desk/dashboard.html` — static, no server, no JavaScript, no framework. Reads from
the ledger files, so it works on a phone, in GitHub, and in a Codespace that
sleeps.

Every string is HTML-escaped and the page carries
`default-src 'none'` CSP, because it renders text from twenty news feeds. No
inline handlers, no CDN, no iframes, and feed URLs are never rendered as links.

Alerts fire only for things that change what a person does: drawdown near the
limit, consistency already broken, kill switch engaged, a strategy silent for
three weeks, a degraded or stale swarm, and orders being rejected.

## 8. The number that changes the prop-firm plan

BOT 5 caught this on its first real board and it is arithmetic, not opinion.

The bracket these rules use is 0.5 ATR stop against 3.0 ATR target, so one MES
win pays about **$967** at one contract. Lucid's consistency rule says the best
day may not exceed 50% of the profit target. At a **$1,250 target, the limit is
$625** — so a single full win is 77% of the profit and *voids the pass even though
the target was reached*.

Two honest routes, and only two:

1. **Raise the target to at least 2× the win, ~$1,934**, so half the profit is
   $967. That is a bigger evaluation, not a better strategy.
2. **Take a partial exit near $480–$625** and let the rest run, so no day lands
   above the limit. This changes the bracket from 6:1 to roughly 2.5:1 and must be
   re-backtested — do not assume the expectancy survives.

Until one of those is chosen, treat the $1,250 Lucid target as **not compatible**
with this bracket. The desk keeps recording rather than refusing every trade; the
flag says so on every board.

## 9. The honest probability, and why two numbers exist

Ten thousand block-bootstrapped replays of the **28 out-of-sample trades** of the
two rules that never saw the data they are judged on (ES fade, CL fade), dropping
the inside-day rule whose parameters were chosen on the full sample:

```
mean trade                       +0.196R
reaches +$1,250 before -$1,000   74.9%
breaches -$1,000 first           24.8%
median trades to the target      36
median worst drawdown            $855
drawdown to plan for (95%)       $1,815
```

That is a **fixed** barrier. Lucid's drawdown is a *trailing* end-of-day limit,
which is much stricter: `target.py --lucid` measured **18.8% of starts passing at
1% risk, 114 of 207 breaching first**. Both are right about different questions,
and the trailing one is the one that decides a funded account. **Plan on roughly
one attempt in five, not three in four**, and never fund an attempt from money you
need.

The same file run without `--honest` returns 98% over 41 trades — because it
includes the rule that was selected by looking at all of history. That flag exists
so the mistake has a name.

## 10. Security posture

* No secrets anywhere: market data and news feeds are public, and the workflow
  needs no credentials.
* No `eval`, `exec`, `subprocess`, `pickle`, `base64` or shell interpolation in any
  module; one pinned action (`actions/checkout@11d5960`, v4.4.0); the workflow's
  `git add` is limited to `trading/desk`.
* Feed text is sanitised and escaped before it is stored, scored or rendered.
* Order output is validated against an enum and numeric bounds; malformed records
  fail to `SKIP`, not to a trade.
* The dashboard ships a strict CSP and escapes every dynamic string.
* `.gitignore` covers `__pycache__/`, `*.pyc` and `.env`.

## 10b. Switching back to six

```bash
python3 trading/desk.py --board --classic     # or: DESK_CLASSIC=1 python3 ...
```

The seven context bots **cannot create a trade**. Three of them can only remove or
delay one (BOT 9 near a roll, BOT 12 on a drawdown, BOT 2 inside an event window)
and the rest only shade confidence. Classic mode is therefore not a safer desk; it
is the same desk with fewer refusals, which makes the comparison clean.

What to expect: the six-bot desk already rejected all four shadow signals, so
thirteen probably changes little in the first month. Where it will differ is the day
a signal fires into a roll, a thin book, or after a losing streak - and on that day
nobody will be able to tell you it was wrong to skip.

## 11. What to run every day

```bash
python3 trading/desk.py --status        # open risk, equity, today's P&L
python3 trading/desk.py --board         # the six bots, five markets
python3 trading/desk.py --report        # the forward record and the committee audit
python3 trading/basket.py --pending     # tomorrow's resting orders
python3 trading/analytics.py            # which rule, which agent, which hour
trading/dashboard.py                    # rebuild the page
```

Once a week: `swarm.py --status`, `execution.py --reconcile`,
`research_engine.py --history`.

Judge nothing before 20 closed trades. At the measured rate (~2–3 signals a
month) that is about seven months — which is the single most useful number in this
document, and the reason the plan does not promise a fast $1,250.
