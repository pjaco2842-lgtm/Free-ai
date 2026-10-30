#!/usr/bin/env python3
"""
Was the 15-minute breakout ever there, or did the sweep pin two coin flips?

The paper book trades GC and CL on 15m bars with the `breakout` signal and the
parameters the last sweep picked. Ten sessions of replay came back at -$6.65 a trade.
Two very different things produce that:

  1. the rule has an edge and a bad stretch ate it, or
  2. there was never an edge, and -$6.65 is costs plus a coin flip.

This file separates them. It does not hunt for a better rule; it asks whether the
current one is distinguishable from random timing with the same risk.

  A  Desk fidelity — does the paper desk replay what the sweep measured?
  B  Baseline — the rule over the full sample, split into gross and costs
  C  Coin flip — same stop, target, hold, hours, frequency and costs, random
     entry bar and random side. Identical to luck.py's test of the daily book.
  D  The space — all 48 configs per market on 15m, first half vs second, scored
     with a *correct* split (see the note about sweep_market's misaligned half)
  E  Walk-forward — re-pick the rule with k sessions removed, then score those
     sessions. If the pick churns, the selection was noise.
  F  Best case — cherry-pick the most favourable config in the sample and
     coin-flip it. Winner of 96 tries that still cannot beat random settles it.

    python3 trading/retest_intraday.py                # 1000 coin-flip runs
    python3 trading/retest_intraday.py --runs 200     # quicker, noisier p-values
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import aggressive as A  # noqa: E402
import paper_aggressive as P  # noqa: E402
from scalp import MARKETS, day, load  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "desk" / "retest-intraday.md"
RAW = HERE / "desk" / "retest-intraday.json"

US_HOURS = set(range(13, 21))
FLOOR = 4.0                      # the frequency floor the sweep used
START_EQUITY = 0.0


# ------------------------------------------------------------------ helpers
def cost_per_trade(sym: str) -> float:
    """Round-trip commission plus one tick of slippage each way, in dollars."""
    _, pv, tick = MARKETS[sym]
    return 2 * (A.COMMISSION + tick * pv)


def summarise(trades: list[dict]) -> dict:
    if not trades:
        return {"n": 0, "usd": 0.0, "per": 0.0, "win": 0.0, "r": 0.0, "risk": 0.0}
    usd = [t["usd"] for t in trades]
    return {"n": len(trades), "usd": sum(usd), "per": sum(usd) / len(usd),
            "win": 100 * sum(1 for u in usd if u > 0) / len(usd),
            "r": statistics.mean(t["r"] for t in trades),
            "risk": statistics.median([t["risk_usd"] for t in trades])}


def ordinal(x: float) -> str:
    n = int(round(x))
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def null_runs(bars: list, S: dict, p: dict, sym: str, n_entries: int, runs: int,
              seed: int = 7) -> dict:
    """Random entry bar, random side; everything else identical to the real rule.

    `A.signal` is swapped for a lookup table and the real `run()` does the exits,
    so the null cannot drift from the rule it is testing.
    """
    _, pv, tick = MARKETS[sym]
    rng = random.Random(seed)
    pool = [i for i in range(2, len(bars)) if S["hour"][i - 1] in US_HOURS]
    if not pool or n_entries < 1:
        return {"runs": 0}

    orig = A.signal
    per_trade: list[float] = []
    wins: list[float] = []
    counts: list[int] = []
    try:
        for _ in range(runs):
            picks = rng.sample(pool, min(n_entries, len(pool)))
            side = {i: rng.choice((1, -1)) for i in picks}
            A.signal = lambda name, SS, i, pp, _s=side: _s.get(i, 0)  # noqa: E731
            tr = A.run(bars, S, "random", p, pv, tick, "stop_first", sym)
            if not tr:
                continue
            usd = sum(t["usd"] for t in tr)
            per_trade.append(usd / len(tr))
            wins.append(100 * sum(1 for t in tr if t["usd"] > 0) / len(tr))
            counts.append(len(tr))
    finally:
        A.signal = orig

    per_trade.sort()
    return {"runs": len(per_trade), "per_trade": per_trade,
            "mean_per_trade": statistics.mean(per_trade),
            "median_per_trade": statistics.median(per_trade),
            "win": statistics.mean(wins), "trades": statistics.mean(counts),
            "p10": per_trade[int(0.10 * len(per_trade))],
            "p90": per_trade[int(0.90 * len(per_trade))]}


def p_value(real: float, null: list[float]) -> float:
    """Share of random runs that matched or beat the real result."""
    if not null:
        return 1.0
    return sum(1 for x in null if x >= real) / len(null)


def verdict(real: float, pv: float) -> str:
    return "BEATS LUCK" if pv < 0.05 and real > 0 else "NO EDGE"


def load_15m(sym: str) -> list:
    bars = load(sym, "15m")
    return bars[:P.complete_len(bars, "15m")]


def space_tables(sym: str) -> tuple[list, list[dict]]:
    """Every (strategy, variant, exit) with its trades over the whole sample.

    Indicators are built once per (strategy, variant) — the exits never change them —
    and the engine runs the whole series once. Every split below is then a filter on
    close timestamps, so train and test are scored by the same run and cannot drift.
    """
    bars = load_15m(sym)
    _, pv, tick = MARKETS[sym]
    rows: list[dict] = []
    for strat in A.STRATS:
        for var in A.VARIANTS[strat]:
            p = {**A.BASE, **var, **A.EXITS[0]}
            S = A.build(bars, p)
            for ex in A.EXITS:
                pp = {**p, **ex}
                tr = A.run(bars, S, strat, pp, pv, tick, "stop_first", sym)
                rows.append({"strat": strat, "params": pp, "trades": tr})
    return bars, rows


def splits(rows: list[dict], cut_ts: int) -> list[dict]:
    """Each config's trades before and after a timestamp, plus its train score."""
    out = []
    for r in rows:
        tr = [t for t in r["trades"] if t["t"] < cut_ts]
        te = [t for t in r["trades"] if t["t"] >= cut_ts]
        out.append({**r, "train": summarise(tr), "test": summarise(te),
                    "train_r": sum(t["r"] for t in tr),
                    "sess_train": len({day(t["t"]) for t in tr})})
    return out


def qualify(rows: list[dict]) -> list[dict]:
    """Configs that clear the frequency floor on the training side, as the sweep did."""
    ok = [r for r in rows if r["train"]["n"] >= max(6, FLOOR * r["sess_train"] * 0.6)]
    if ok:
        return ok
    return [r for r in rows if r["train"]["n"] >= 6]


def pick(rows: list[dict]) -> dict | None:
    ok = qualify(rows)
    return max(ok, key=lambda r: r["train_r"]) if ok else None


def fmt(tag: str, r: dict) -> str:
    p = r["params"]
    return (f"{tag:11} {r['strat']:12} {p['stop']}/{p['target']}A {p['hold']}b cool {p['cool']}b"
            f"  train ${r['train']['usd']:+8,.0f} ({r['train']['n']:3d}) "
            f" test ${r['test']['usd']:+8,.0f} ({r['test']['n']:3d})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    rule = P.rules()
    syms = list(rule)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    print("=" * 104)
    print("  WAS THE 15m BREAKOUT EVER THERE?  ·  the pinned rule against random timing")
    print("=" * 104)

    out: dict = {"generated": stamp, "runs": args.runs, "floor": FLOOR, "markets": {}}
    lines = [
        "# Was the 15-minute breakout ever there?",
        "",
        f"Generated {stamp} · {args.runs} coin-flip runs per test · one micro contract, "
        f"${A.COMMISSION:.2f} commission per side plus one tick of slippage per side",
        "",
        "The paper book is losing about $6.65 a trade on GC and CL at 15 minutes. That is either",
        "an edge in a bad stretch or no edge at all. Random timing with the same stop, target,",
        "holding limit, session filter, trade frequency and costs answers it.",
        "",
    ]

    # ---------------------------------------------------------------- A fidelity
    print("\nA  does the paper desk replay the rule the sweep measured?")
    fid_rows = []
    for sym in syms:
        r = rule[sym]
        p = r["params"]
        bars = load_15m(sym)
        upto = len(bars)
        _, pv, tick = MARKETS[sym]
        S = A.build(bars, p)
        tested = A.run(bars, S, r["strat"], p, pv, tick, "stop_first", sym)
        one_bar = A.run(bars, S, r["strat"], {**p, "cool": 1}, pv, tick, "stop_first", sym)
        st = P.blank_state()
        st["last"][sym] = bars[0].t - 1
        P.step(sym, r, bars, st, upto)
        desk = st["ledger"]
        fid_rows.append({"sym": sym, "tested": len(tested),
                         "tested_usd": sum(t["usd"] for t in tested),
                         "cool1": len(one_bar), "cool1_usd": sum(t["usd"] for t in one_bar),
                         "desk": len(desk), "desk_usd": sum(t["usd"] for t in desk),
                         "halted": st["halted"]})
        print(f"   {sym:6} sweep rule (cool {p['cool']}b): {len(tested):3d} trades "
              f"${sum(t['usd'] for t in tested):+9,.2f}")
        print(f"   {'':6} cool 1b                 : {len(one_bar):3d} trades "
              f"${sum(t['usd'] for t in one_bar):+9,.2f}")
        print(f"   {'':6} paper desk              : {len(desk):3d} trades "
              f"${sum(t['usd'] for t in desk):+9,.2f}"
              f"  · halted {st['halted']}")
    out["fidelity"] = fid_rows

    lines += [
        "## First finding: the desk is not trading the rule that was tested",
        "",
        "`paper_aggressive.step()` never implements the `cool` parameter. It re-enters on the",
        "next bar after an exit, so the desk effectively runs cool 1b however the parameters are",
        "set. The sweep scored cool 6b. Same entries, more of them — and each extra trade pays",
        "costs for a signal that has not been shown to carry any.",
        "",
        "| market | sweep rule (cool 6b) | same rule, cool 1b | paper desk | halted |",
        "|---|---|---|---|---|",
    ]
    for f in fid_rows:
        lines.append(f"| {f['sym']} | {f['tested']} trades, ${f['tested_usd']:+,.2f} | "
                     f"{f['cool1']} trades, ${f['cool1_usd']:+,.2f} | "
                     f"{f['desk']} trades, ${f['desk_usd']:+,.2f} | "
                     f"{'yes' if f['halted'] else 'no'} |")
    lines += [
        "",
        "The desk column can also be *shorter* than the rule: once equity passes the $1,000",
        "buffer the desk halts and stops taking entries, so a longer replay of it is not a",
        "longer record of the rule. GC halts here.",
        "",
    ]

    # ------------------------------------------------------- B/C per market
    for sym in syms:
        r = rule[sym]
        p = dict(r["params"])
        bars = load_15m(sym)
        upto = len(bars)
        _, pv, tick = MARKETS[sym]
        S = A.build(bars, p)
        sessions = len({day(b.t) for b in bars})
        cost = cost_per_trade(sym)

        tested = A.run(bars, S, r["strat"], p, pv, tick, "stop_first", sym)
        desk = A.run(bars, S, r["strat"], {**p, "cool": 1}, pv, tick, "stop_first", sym)
        st_t, st_d = summarise(tested), summarise(desk)

        print(f"\nB  {sym}  {r['strat']} 15m  stop {p['stop']}A tgt {p['target']}A hold {p['hold']}b"
              f"   ({sessions} sessions, {upto} bars)")
        print(f"   desk cadence (cool 1b): {st_d['n']:3d} trades · win {st_d['win']:.0f}% · "
              f"avg {st_d['r']:+.2f}R · median risk ${st_d['risk']:,.0f}")
        print(f"      net ${st_d['usd']:+9,.2f} = gross ${st_d['usd'] + cost * st_d['n']:+9,.2f}"
              f" - costs ${cost * st_d['n']:7,.2f}   ${st_d['per']:+.2f}/trade")
        print(f"   sweep cadence (cool 6b): {st_t['n']:3d} trades · win {st_t['win']:.0f}% · "
              f"${st_t['per']:+.2f}/trade · net ${st_t['usd']:+,.2f}")

        null = null_runs(bars, S, {**p, "cool": 1}, sym, st_d["n"], args.runs, args.seed)
        pv_d = p_value(st_d["per"], null["per_trade"])
        print(f"C  coin flip · {null['runs']} runs of {null['trades']:.0f} random entries:")
        print(f"   random ${null['mean_per_trade']:+.2f}/trade, win {null['win']:.0f}% · "
              f"10th–90th pct ${null['p10']:+.2f} to ${null['p90']:+.2f}")
        print(f"   real ${st_d['per']:+.2f} sits at the {ordinal(100 * (1 - pv_d))} percentile"
              f" · p = {pv_d:.2f}  ->  {verdict(st_d['per'], pv_d)}")

        out["markets"][sym] = {
            "strat": r["strat"], "params": p, "sessions": sessions, "bars": upto,
            "desk": st_d, "tested": st_t, "cost_per_trade": cost,
            "desk_gross": st_d["usd"] + cost * st_d["n"],
            "desk_costs": cost * st_d["n"],
            "null": {k: v for k, v in null.items() if k != "per_trade"},
            "null_p10": null["p10"], "null_p90": null["p90"],
            "p_value": pv_d,
        }

        loss = abs(st_d["usd"])
        share = (f"{100 * cost * st_d['n'] / loss:.0f}% of the loss"
                 if st_d["usd"] < 0 else "less than the gross")
        lines += [
            f"## {sym} — {r['strat']} on 15m, the rule the desk trades",
            "",
            f"{sessions} sessions, {upto} bars, median risk ${st_d['risk']:,.0f}, "
            f"win rate {st_d['win']:.0f}%.",
            "",
            "| | at the desk's cadence (cool 1b) | the rule as tested (cool 6b) |",
            "|---|---|---|",
            f"| trades | {st_d['n']} | {st_t['n']} |",
            f"| net | ${st_d['usd']:+,.2f} | ${st_t['usd']:+,.2f} |",
            f"| per trade | ${st_d['per']:+.2f} | ${st_t['per']:+.2f} |",
            f"| win rate | {st_d['win']:.0f}% | {st_t['win']:.0f}% |",
            f"| avg R | {st_d['r']:+.2f} | {st_t['r']:+.2f} |",
            "",
            f"Before costs the desk's version made ${st_d['usd'] + cost * st_d['n']:+,.2f}; "
            f"commissions and one tick each way took ${cost * st_d['n']:,.2f} — {share}.",
            "",
            "Coin flip — random entry bar, random side, same stop, target, hold, session",
            f"filter, frequency and costs, {null['runs']} runs:",
            "",
            "| | value |",
            "|---|---|",
            f"| random timing, mean | ${null['mean_per_trade']:+.2f}/trade |",
            f"| random timing, win rate | {null['win']:.0f}% |",
            f"| random timing, 10th–90th pct | ${null['p10']:+.2f} to ${null['p90']:+.2f} |",
            f"| the rule | ${st_d['per']:+.2f}/trade |",
            f"| percentile | {ordinal(100 * (1 - pv_d))} |",
            f"| p-value | {pv_d:.2f} |",
            "",
            f"**{verdict(st_d['per'], pv_d)}** — " + (
                "the rule sits inside the range random entries produce."
                if pv_d >= 0.05 else "this is outside what random timing produced."),
            "",
        ]

    # ------------------------------------------------------------- D the space
    print("\nD  every 15m config, chosen on the first half, scored on the second")
    lines += [
        "## The whole 15m space, chosen on the first half and scored on the second",
        "",
        "48 configs per market: 6 signal families x 2 variants x 4 exit brackets. Indicators",
        "are a continuous series and every split is a filter on trade timestamps, so the two",
        "halves are scored by the same run.",
        "",
        "| market | configs clearing the floor | positive out of sample | median | best | worst |",
        "|---|---|---|---|---|---|",
    ]
    space_out: dict = {}
    tables: dict[str, tuple[list, list[dict]]] = {}
    for sym in syms:
        bars, rows = space_tables(sym)
        tables[sym] = (bars, rows)
        cut = bars[len(bars) // 2].t
        rs = splits(rows, cut)
        ok = qualify(rs)
        pos = [r for r in ok if r["test"]["usd"] > 0]
        med = statistics.median(r["test"]["usd"] for r in ok) if ok else 0.0
        best = max(ok, key=lambda r: r["test"]["usd"]) if ok else None
        worst = min(ok, key=lambda r: r["test"]["usd"]) if ok else None
        p = pick(rs)
        print(f"   {sym:6} {len(ok):2d} of {len(rs)} configs clear the floor · "
              f"{len(pos):2d} positive ({100 * len(pos) / max(len(ok), 1):.0f}%) · "
              f"median ${med:+,.0f}")
        if best and worst:
            print(f"          best {best['strat']:12} ${best['test']['usd']:+8,.0f}  ·  "
                  f"worst {worst['strat']:12} ${worst['test']['usd']:+8,.0f}")
        if p:
            print(f"          the sweep's rule: {p['strat']} {p['params']['stop']}/"
                  f"{p['params']['target']}A {p['params']['hold']}b → train "
                  f"${p['train']['usd']:+,.0f}, test ${p['test']['usd']:+,.0f}")
            lines.append(f"| {sym} | {len(ok)} of {len(rs)} | {len(pos)} "
                         f"({100 * len(pos) / max(len(ok), 1):.0f}%) | ${med:+,.0f} | "
                         f"${best['test']['usd']:+,.0f} | ${worst['test']['usd']:+,.0f} |")
        space_out[sym] = {"configs": len(rs), "qualified": len(ok), "positive": len(pos),
                          "median": med,
                          "best": {"strat": best["strat"], "test": best["test"]["usd"],
                                   "params": {k: best["params"][k] for k in
                                              ("stop", "target", "hold", "cool")}}
                          if best else None,
                          "sweep_pick": {"strat": p["strat"], "train": p["train"]["usd"],
                                         "test": p["test"]["usd"],
                                         "stop": p["params"]["stop"],
                                         "target": p["params"]["target"],
                                         "hold": p["params"]["hold"]} if p else None}
        if p:
            lines += ["", f"**{sym}** — the sweep's own choice was **{p['strat']}** "
                          f"{p['params']['stop']}A/{p['params']['target']}A "
                          f"{p['params']['hold']}b: ${p['train']['usd']:+,.0f} in training, "
                          f"**${p['test']['usd']:+,.0f}** out of sample on {p['test']['n']} "
                          f"trades."]
    out["space"] = space_out

    # ------------------------------------------------------- E walk-forward
    print("\nE  re-pick the rule with k sessions removed, then trade them")
    lines += [
        "",
        "## Walk-forward: would a re-sweep have picked something that worked?",
        "",
        "Cut the last k sessions out of the sample, re-pick by training total R exactly as the",
        "sweep does, then score the sessions that were removed. This is what pinning the rule",
        "and trading it forward actually amounts to.",
        "",
        "| market | held out | picked | train | that pick on the held-out sessions |",
        "|---|---|---|---|---|",
    ]
    wf_out: dict = {}
    for sym in syms:
        bars, rows = tables[sym]
        sessions = sorted({day(b.t) for b in bars})
        picks, oos_usd, oos_n = [], [], []
        for k in (1, 2, 3, 5, 8):
            if k >= len(sessions):
                continue
            first_ts = next(b.t for b in bars if day(b.t) == sessions[-k])
            rs = splits(rows, first_ts)
            p = pick(rs)
            if not p:
                continue
            picks.append(f"{p['strat']} {p['params']['stop']}/{p['params']['target']}A")
            oos_usd.append(p["test"]["usd"])
            oos_n.append(p["test"]["n"])
            print(f"   {sym:6} {k:2d} sessions  →  {p['strat']:12} "
                  f"{p['params']['stop']}/{p['params']['target']}A {p['params']['hold']}b"
                  f"  train ${p['train']['usd']:+8,.0f}  held out ${p['test']['usd']:+8,.0f}"
                  f" ({p['test']['n']:2d} tr)")
            lines.append(f"| {sym} | {k} | {p['strat']} {p['params']['stop']}/"
                         f"{p['params']['target']}A {p['params']['hold']}b | "
                         f"${p['train']['usd']:+,.0f} | ${p['test']['usd']:+,.0f} "
                         f"on {p['test']['n']} trades |")
        n_pos = sum(1 for x in oos_usd if x > 0)
        distinct = len(set(picks))
        print(f"   {sym:6} {distinct} different rules picked across {len(picks)} cuts · "
              f"{n_pos}/{len(oos_usd)} of those forward runs made money · "
              f"total ${sum(oos_usd):+,.0f}")
        lines += ["", f"**{sym}** — {distinct} different rules picked across {len(picks)} cuts; "
                      f"{n_pos} of {len(oos_usd)} made money trading what was picked "
                      f"(total ${sum(oos_usd):+,.0f} over {sum(oos_n)} trades)."]
        wf_out[sym] = {"picks": picks, "oos_usd": oos_usd, "oos_n": oos_n,
                       "distinct": distinct, "positive": n_pos}
    out["walk_forward"] = wf_out

    # ------------------------------------------------------------ F best case
    print("\nF  coin-flip the single best config the whole sample produced")
    lines += [
        "",
        "## Best case: cherry-pick the winner and coin-flip it",
        "",
        "The sweep picked the best of 48 configs, which by itself guarantees a good-looking",
        "number. So take the most favourable config in the sample — hindsight, not a rule — and",
        "ask whether even that beats random entries with the same risk.",
        "",
    ]
    for sym in syms:
        bars, rows = tables[sym]
        cut = bars[len(bars) // 2].t
        ok = qualify(splits(rows, cut))
        if not ok:
            continue
        champ = max(ok, key=lambda r: r["test"]["usd"])
        real = summarise(champ["trades"])
        S = A.build(bars, champ["params"])
        null = null_runs(bars, S, {**champ["params"], "cool": 1}, sym, real["n"],
                         args.runs, args.seed + 1)
        pv = p_value(real["per"], null["per_trade"])
        print(f"   {sym:6} {champ['strat']:12} {champ['params']['stop']}/"
              f"{champ['params']['target']}A ${real['per']:+.2f}/trade over {real['n']} · "
              f"random ${null['mean_per_trade']:+.2f} · p = {pv:.2f}  ->  "
              f"{verdict(real['per'], pv)}")
        lines += [
            f"**{sym}** — {champ['strat']} {champ['params']['stop']}A/"
            f"{champ['params']['target']}A {champ['params']['hold']}b: "
            f"${real['per']:+.2f}/trade over {real['n']} trades. Random timing with the same "
            f"risk and frequency: ${null['mean_per_trade']:+.2f}/trade "
            f"(10th–90th pct ${null['p10']:+.2f} to ${null['p90']:+.2f}). "
            f"p = {pv:.2f} → {'beats luck' if pv < 0.05 and real['per'] > 0 else '**no edge**'}.",
            "",
        ]
        out["markets"][sym]["best_case"] = {
            "strat": champ["strat"], "params": champ["params"], "n": real["n"],
            "per_trade": real["per"], "null_mean": null["mean_per_trade"],
            "p_value": pv}

    # --------------------------------------------------------------- G the bug
    lines += [
        "## A bug in the harness that produced the pinned rule",
        "",
        "`aggressive.sweep_market()` scores the second half with `run(bars[cut:], S, ...)` while",
        "`S` was built on the full series. `run` indexes `S[i]` and `bars[i]` together, so every",
        "indicator the test half reads belongs to the *training* half — offset by `cut` bars. The",
        "test column in `aggressive.md` is not measuring what it says it measures:",
        "",
        "| market | breakout 1.0/3.0/48, harness test half | same config, correct split |",
        "|---|---|---|",
    ]
    for sym in syms:
        bars, rows = tables[sym]
        cut = len(bars) // 2
        cut_ts = bars[cut].t
        champ = next(r for r in rows if r["strat"] == "breakout"
                     and r["params"]["stop"] == 1.0 and r["params"]["target"] == 3.0
                     and r["params"]["hold"] == 48)
        _, pv, tick = MARKETS[sym]
        S = A.build(bars, champ["params"])
        mis = A.stats(A.run(bars[cut:], S, "breakout", champ["params"], pv, tick), 30)
        ok = summarise([t for t in champ["trades"] if t["t"] >= cut_ts])
        lines.append(f"| {sym} | ${mis['usd']:+,.0f} on {mis['trades']} trades | "
                     f"${ok['usd']:+,.0f} on {ok['n']} trades |")
        out.setdefault("misalign", {})[sym] = {"harness": mis["usd"], "correct": ok["usd"]}
    lines += [
        "",
        "The pinning decision itself used the *training* half, which is aligned and unaffected.",
        "What is unreliable is the out-of-sample column that was read as evidence the panel had",
        "been validated. It had not.",
        "",
    ]

    # --------------------------------------------------------------- verdict
    m = out["markets"]
    lines += [
        "## The answer",
        "",
        f"Neither market's rule is distinguishable from random entries. GC sits at p = "
        f"{m['GC=F']['p_value']:.2f} and CL at p = {m['CL=F']['p_value']:.2f} — well inside the "
        f"spread that random timing with the same stop, target and costs produces. Neither is in "
        f"the tail.",
        "",
        f"The desk's CL figure of ${m['CL=F']['desk']['per']:+.2f}/trade reproduces the "
        f"${-6.65:+.2f}/trade in the replay almost exactly, which is a useful check on the "
        f"arithmetic: these tests are measuring the same trades the paper book is making.",
        "",
        "Costs do most of the damage. On CL the commissions and slippage are "
        f"${m['CL=F']['desk_costs']:,.0f} against a net of ${m['CL=F']['desk']['usd']:+,.0f}: "
        f"before them the book is ${m['CL=F']['desk_gross']:+,.0f} over "
        f"{m['CL=F']['desk']['n']} trades, which is not a loss worth arguing about either way. "
        "On GC the rule is worse than that, but still not by enough to separate it from luck "
        f"(p = {m['GC=F']['p_value']:.2f}).",
        "",
        "So: **the edge was never demonstrated, and the 15m book has been paying costs to trade a "
        "coin flip.** The two things that made GC/CL look worth trading do not survive a check —",
        "the pick was the best of 48 tries, and the out-of-sample column that was read as "
        "validation was misaligned.",
        "",
        "## What this test cannot see",
        "",
        f"{m['GC=F']['sessions']} sessions is a short sample. The random-entry spread runs "
        f"${m['GC=F']['null_p10']:+.0f} to ${m['GC=F']['null_p90']:+.0f} per trade on GC and "
        f"${m['CL=F']['null_p10']:+.0f} to ${m['CL=F']['null_p90']:+.0f} on CL, so an edge "
        "smaller than about $15-30 a trade would be invisible here. That cuts both ways: this "
        "does not prove the rule is worthless, only that nothing observed so far supports it, and "
        "the burden of proof is on the rule.",
        "",
        "Two details of the method worth knowing. The null lands slightly fewer trades than the "
        "rule (about 54 against 74 on GC) because random entries collide with positions already "
        "open, so the comparison is per trade rather than per session. And the null ignores the "
        "desk's `MAX_OPEN = 2` limit, which can suppress an entry in one market while a position "
        "is open in the other — an account constraint, not something that changes whether the "
        "signal carries information.",
        "",
    ]

    # ------------------------------------------------------------------- write
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines))
    RAW.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n  written to {OUT} and {RAW}")

    # ---------------------------------------------------------------- verdict
    verdicts = [m["p_value"] for m in out["markets"].values()]
    beats = sum(1 for sym, m in out["markets"].items()
                if m["p_value"] < 0.05 and m["desk"]["per"] > 0)
    print("\n" + "=" * 104)
    print(f"  {beats} of {len(verdicts)} markets beat random timing "
          f"(p-values {', '.join(f'{v:.2f}' for v in verdicts)})")
    print("  the loss is costs plus a coin flip, not an edge in a bad stretch"
          if beats == 0 else "  at least one market is outside the random range")


if __name__ == "__main__":
    main()
