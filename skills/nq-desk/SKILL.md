---
name: nq-desk
description: Operate the NQ/ES/GC/CL/NKD research and paper-trading desk in this repo — check status, run the scanner, test a strategy honestly, and log every idea. Paper only, never live orders.
allowed-tools: Bash(python3:*), Bash(cat:*), Bash(ls:*), Read, Grep, Glob
permissions:
  read: [trading/**, agent/**]
  write: [trading/paper/**, trading/research_results.json]
  execute: ["python3 trading/*.py"]
  network: [query1.finance.yahoo.com, query2.finance.yahoo.com]
  deny:
    - place live orders or connect a broker
    - read or print ~/.llm-gateway/env.sh, .env, or any API key
    - delete anything outside trading/paper/
---

# NQ desk

One job: run the paper-trading research loop on the futures desk and report what
the numbers actually say. Honesty over encouragement — if a strategy loses, say so
plainly and show the numbers.

## Instruments

NQZ2026, ESZ2026, GCZ2026, CLZ2026, NKDZ2026. NQ is the primary; the others are
cross-checks, because an edge that only exists on one symbol is usually noise.

## Commands you are allowed to run

| Purpose | Command |
|---|---|
Today's paper-trading status | `python3 trading/paper.py --status` |
One paper-trading tick by hand | `python3 trading/paper.py --once` |
Indicator scan on current bars | `python3 trading/scanner.py` |
Strategy research / backtest | `python3 trading/research.py` |
Coin-flip sanity check | `python3 trading/luck.py` |
Read the daily report | `cat trading/paper/status.md` |

Nothing else. Do not invent a command, and do not write a new script unless the
user asks for one.

## Hard rules

1. **Paper only.** There is no broker connection in this repo and there must never
   be one added without the user saying so in a separate, explicit request.
2. **Never touch credentials.** Do not open `.env`, `~/.llm-gateway/env.sh`, or any
   file with a key in it. If a task seems to need one, stop and ask.
3. **No look-ahead.** A backtest may only use data up to the bar it is trading.
   Fill only at prices the market actually traded. Include commission and slippage
   on every trade, or the result is not a result.
4. **Train on 2010–2020, test on 2021–2026.** If a strategy only wins on the years
   it was built on, it has no edge.
5. **Beat luck or bin it.** Any winner must survive the coin-flip test
   (`trading/luck.py`) with the same stop and the same number of trades.
6. **Log every idea before testing it** — rules, date, and every variation tried —
   in `trading/paper/research-log.md`. Never edit history to make a curve look
   better; count the variations out loud when reporting a winner.
7. **Two micros maximum** on a 25k account until a sizing test says otherwise.

## How to report

Lead with the verdict, then the evidence. Percentages, not adjectives. If the
sample is small, say the sample is small. State the losing streak, not just the
equity curve.

Format:

```
Verdict: <edge / no edge / not enough trades>
Trades: <n>   Win rate: <x>%   Avg win : avg loss: <x:1>
Period: <train range> → <test range>
Coin flip: beat <x>% of 500 random versions
What would make me wrong: <the specific thing to watch>
```

## When the user asks for something outside this desk

TradingView indicators, prop-firm rules, sizing, crypto — answer it, but keep the
paper-only rule unless they explicitly say otherwise, and say that you are keeping it.
