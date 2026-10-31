# Start here — paper trading the five December contracts

> **Out of date in places.** The current state of the desk, the live book, every settled
> research question and the honesty conventions are in **`trading/HANDOFF-DESK.md`**
> (written 2026-10-31). Read that first; this page is the 26 October starting point.

You do not need the Mac for this. A browser is enough, and a phone works for
placing the orders. Read the numbers in section 1 first, because they change
what "aggressive" is allowed to mean.

---

## 1. What the research actually found

9,288 stop/target/hold combinations were scored on five contracts
(`trading/edge.py`, full output in `trading/edge.json`).

**A coin-flip win rate is easy to buy.** 2,942 of 9,288 settings won 50% or more.
But only 499 of them made money in both halves of history. The highest win rate
found was **92.9%** — on a setting that averages **+0.21R** over 42 trades in
seventeen years. You win almost every time and barely earn anything, because the
target is a quarter of the stop.

**The one setting worth trading that also wins most of the time:**

| market | rule | stop/target/hold | win rate | avg | both halves | vs coin flip |
|---|---|---|---|---|---|---|
ESZ2026 → MES | inside day breakout | 0.5 / 1.0 / 5 bars | **58.1%** | **+0.62R** | +14.1R, +12.6R | p < 0.01 |

That is a real, measurable edge: 43 trades, positive in the years before 2020
*and* after, and random entries with the identical bracket did not reproduce it.

**The settings that survived being chosen blind.** The sweep also picked settings
using only one half of history and then scored the other half — the test that
kills most backtests:

| market | chosen on 2009–2019 | result 2020–2026 |
|---|---|---|
ES | fade_trend_day 0.5/3.0/10 | **+9.3R** |
CL | fade_trend_day 0.5/3.0/2 | **+4.0R** |
NKD | continue_trend_day 0.5/3.0/5 | **+13.4R** (and picked identically in reverse) |
NQ | best early setting | −4.4R — **failed** |
GC | best early setting | −16.6R — **failed** |

**The number I will not dress up.** Lock the settings using 2009–2019 only, then
run the $25,000 book on 2020–2026 only:

```
38 trades over 6.8 years · final $24,603 · -0.2%/yr
51 signals skipped because one contract's stop did not fit the budget
```

So when nothing is allowed to peek at the future, the basket does **not**
compound. The +8.4%/yr figure from the full-history run is the optimistic end,
because those settings were chosen with hindsight.

**Can you trade them at all?** One contract's typical stop, at $25,000 and a 1%
($250) budget:

| contract | trade as | stop | verdict |
|---|---|---|---|
NQZ2026 | MNQ | $478 | too big for 1% |
GCZ2026 | MGC | $490 | too big for 1% |
NKDZ2026 | no micro exists | $3,946 | **15.8% of the account — do not trade this** |
ESZ2026 | MES | $199 | fits |
CLZ2026 | MCL | $218 | fits |

NKD is the best-measured signal in the whole study and you cannot afford it.
That is not a detail — it is the whole reason the account curve stays flat.

**One week to $1,250:** replaying every historical week, the best measured pass
rate is **3.0%** at 1% daily risk. At 2% it rises to 4.9% and 35% of starts
breach the $1,000 limit first. There is no sizing that fixes this, because the
basket fires ~37 times a year and a week contains ~0.7 of a signal.

---

## 2. Open the code in a Codespace (phone-friendly, nothing to install)

1. On your phone, browser → `github.com` → sign in.
2. Open `pjaco2842-lgtm/Free-ai`. If today's work is not there yet, ask me to
   commit and push first — a Codespace only sees what has been pushed.
3. Tap the green **Code** button → **Codespaces** tab → **Create codespace on main**.
4. Wait for the VS Code window. Then open a terminal: **☰ → Terminal → New Terminal**.
5. Type:

```bash
python3 --version          # should be 3.11 or newer
python3 trading/basket.py --pending
```

That prints, for each contract, either a resting order or "nothing new".

To see the research yourself:

```bash
python3 trading/edge.py --min-trades 12 --runs 100    # ~4 minutes
```

Codespaces sleeps after 30 minutes idle; your files survive, the process does not.

---

## 3. The daily routine (10 minutes, once a session closes)

Futures trade 23 hours, but every rule here decides **on the open** and holds for
whole sessions. So you need one check a day, after the 5pm ET close.

```bash
python3 trading/basket.py --scan
```

Three things can appear:

- `ORDER LONG stop order at 7,698.75 · risk 39.49 pts · target 78.98 pts · 1 contract(s)`
  → place a buy-stop at that price plus a sell-stop at the short trigger. One
  cancels the other. That is the whole trade.
- `OPEN ... entry 7,690.00 stop 7,655.00 target 7,760.00 held 2/5 bars`
  → already in a trade. Do not add to it, do not move the stop.
- `(nothing new)` → the most common outcome. Do nothing. This is most days.

---

## 4. Where to paper trade it

Any of these, in order of least friction for a phone:

1. **TradingView paper trading** — you already have the account. Add `MES1!`,
   `MCL1!`, `MNQ1!`, `MGC1!` to a watchlist and use the Paper Trading panel.
   Free tier is delayed data, which is fine for a daily-bar system.
2. **Tradovate or NinjaTrader demo** — a real futures demo with real fills and
   real commissions. Better test, more setup.
3. **Our own ledger** — `trading/basket.py --scan` already records every finished
   trade to `trading/basket/ledger.jsonl` with entry, stop, target, exit and R.
   `python3 trading/basket.py --report` summarises it.

Do both 1 and 3: place the orders by hand in TradingView so you feel the fills,
and let the ledger be the machine record. If they disagree, that is a finding.

---

## 5. Rules that are not negotiable

- **One contract** until the ledger shows 20 closed trades. One.
- **Stop for the day at −2%** ($500 on $25,000). The replay shows the daily stop
  is what keeps the $1,000 trailing limit intact.
- **Never hold through a session where a stop was already hit** to "give it room".
  Every number above assumes the stop is honoured exactly.
- **Check the roll.** `ES=F` is the front month and is December 2026 today. After
  mid-December the front month becomes March 2027 and the signals come from a
  different contract. Re-read `CONTRACTS` in `trading/edge.py` then.
- **NKD: no.** $3,946 of risk per contract. Record the signal, do not trade it.

---

## 6. What would change my mind

The forward ledger is the only test that has not been contaminated. Judge it on
**20 closed trades minimum** and compare against the backtest expectation:

| rule | backtest expectation |
|---|---|
ES inside_day 0.5/1.0/5 | 58% win, +0.62R average |
ES fade_trend_day 0.5/3.0/10 | 58% win, +0.58R average |
CL fade_trend_day 0.5/3.0/2 | 46% win, +0.55R average |

If 20 forward trades come in below **+0.10R** average, the edge is not there at a
tradeable size and the honest move is to stop, not to increase size. If they come
in near the backtest, the next question is frequency, not accuracy — and the
answer to frequency is more markets, which is a separate piece of work.

`python3 trading/basket.py --report` prints exactly this comparison.

---

## 7. Then the Mac (your step 3, last)

```bash
git clone https://github.com/pjaco2842-lgtm/Free-ai.git
cd Free-ai
bash setup-cc-free.sh        # agent kit + local gateway
python3 trading/basket.py --pending
```

The Mac adds the agent kit and a scheduler (see `trading/launchd.paper.example.plist`)
so the scan runs itself at 5:10pm. Nothing in section 3–6 needs it.

## The six bots (after the desk is running)

From the Codespace terminal, in this order:

```bash
python3 trading/swarm.py --force     # 300 readers, timestamp-verified, ~20s
python3 trading/desk.py --board      # what all six bots say about all five markets
python3 trading/dashboard.py         # writes trading/desk/dashboard.html
```

Then open `trading/desk/dashboard.html` in the Codespace file tree (right-click →
Download) to read it on your phone.

What the letters mean:

- **BUY / SELL** — every gate passed. It is a decision to record, not an order.
- **WAIT** — the setup or the news is not there yet, or a scheduled release is
  inside the blackout window. Try again later; nothing is wrong.
- **SKIP** — BOT 5 refused it: the stop does not fit $250, a correlated position is
  already open, the daily stop is hit, or a full win would break the consistency
  rule. Nothing to do.

A board where everything says WAIT or SKIP is a working desk on a quiet day, not a
broken one. Signals arrive about 2–3 times a month.

Read `trading/DESK.md` once, end to end. It explains each bot, what each one is
allowed to veto, and the arithmetic that decides whether a Lucid evaluation is even
passable with this bracket.
