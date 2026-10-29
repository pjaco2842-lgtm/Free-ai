#!/usr/bin/env python3
"""
From idea to executable strategy, and the tests that stop you fooling yourself.

A strategy here is not prose. It is a JSON object with a rule name, parameters, a
bracket and a stated hypothesis — machine-readable, diffable, and re-runnable.
The point is that "the bot got better" becomes a commit with a number attached.

    python3 trading/research_engine.py --template momentum > idea.json
    python3 trading/research_engine.py --spec idea.json        # full report + verdict
    python3 trading/research_engine.py --loop                  # the improvement loop
    python3 trading/research_engine.py --history                # every experiment so far

What the verdict refuses
------------------------
The eight ways a backtest lies, each as a check that can fail:

  1. works only in a small parameter range   -> parameter neighbourhood stability
  2. disappears after realistic costs        -> 3x cost stress
  3. uses future information                 -> entry timing is asserted, not assumed
  4. survivorship bias                       -> the five markets are named in advance
  5. too few trades                          -> minimum sample per half
  6. not consistent across time              -> five equal folds, all reported
  7. no edge over a simple baseline          -> random-entry p-value + buy & hold
  8. beaten by a coin flip                   -> the same random-entry test

A strategy is only `KEEP` when every check passes. Anything else is `REJECT` with
the reason, because a report that can only say yes is not a report.

The improvement loop, and its one real danger
---------------------------------------------
observe -> diagnose -> hypothesise -> experiment -> validate -> keep or revert.

The danger is that this is exactly how a strategy gets fitted to its own history:
try enough fixes and one will look brilliant in the past. Two guards: a variant
must improve on the **holdout** period it was not designed on, and the trial count
raises the significance bar, so the twentieth attempt has to be better than the
second to be believed.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from basket import CONFIGS, HAIRCUT  # noqa: E402
from edge import CONTRACTS, bracket  # noqa: E402
from lab import COMMS, COMMISSION, RULES, atr_series, ema, fetch_daily  # noqa: E402

DESK = HERE / "desk"
LAB = HERE / "lab"
EXPERIMENTS = LAB / "experiments.jsonl"
SPLIT = "2020-01-01"
MIN_TRADES = 15
STOP_CHOICES = (0.5, 0.75, 1.0, 1.5)
TARGET_CHOICES = (0.5, 0.75, 1.0, 1.5, 2.0, 3.0)
HOLD_CHOICES = (1, 2, 3, 5, 10)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------- the spec
TEMPLATES = {
    "momentum": {
        "name": "momentum-close-extreme",
        "market": "ES=F",
        "rule": "close_extreme",
        "params": {"edge": 0.9, "slow": 200},
        "stop": 0.5, "target": 1.0, "hold": 3,
        "hypothesis": ("a close in the top decile of the day's range, above the 200-day "
                       "average, continues into the next session"),
    },
    "breakout": {
        "name": "inside-day-breakout",
        "market": "ES=F",
        "rule": "inside_day",
        "params": {},
        "stop": 0.5, "target": 1.0, "hold": 5,
        "hypothesis": ("compression (an inside day) followed by an open outside its range "
                       "expands in that direction"),
    },
    "reversion": {
        "name": "trend-day-fade",
        "market": "CL=F",
        "rule": "fade_trend_day",
        "params": {"trend": 1.5},
        "stop": 0.5, "target": 3.0, "hold": 2,
        "hypothesis": ("a wide-range day that gaps into its own extreme over-extends and "
                       "pulls back"),
    },
}


def validate_spec(spec: dict) -> list[str]:
    """Structural checks. A spec that fails here never reaches a backtest."""
    errs: list[str] = []
    if not isinstance(spec, dict):
        return ["spec is not an object"]
    for key in ("name", "market", "rule", "stop", "target", "hold", "hypothesis"):
        if key not in spec:
            errs.append(f"missing {key}")
    if spec.get("market") not in CONFIGS:
        errs.append(f"market {spec.get('market')!r} is not one of the five contracts")
    if spec.get("rule") not in RULES:
        errs.append(f"rule {spec.get('rule')!r} unknown")
    if spec.get("stop") not in STOP_CHOICES:
        errs.append(f"stop {spec.get('stop')!r} not in {STOP_CHOICES}")
    if spec.get("target") not in TARGET_CHOICES:
        errs.append(f"target {spec.get('target')!r} not in {TARGET_CHOICES}")
    if spec.get("hold") not in HOLD_CHOICES:
        errs.append(f"hold {spec.get('hold')!r} not in {HOLD_CHOICES}")
    if spec.get("rule") in RULES:
        grid = RULES[spec["rule"]][1]
        params = spec.get("params") or {}
        if grid and grid != [{}]:
            allowed = [set(g.items()) for g in grid]
            if set(params.items()) not in allowed:
                errs.append(f"params {params} is not one of the tested grid values {grid}")
        elif params:
            errs.append("this rule takes no parameters")
    hyp = str(spec.get("hypothesis", ""))
    if len(hyp) < 20:
        errs.append("hypothesis is too short to be falsifiable")
    return errs


# ------------------------------------------------------------------- mechanic
class Market:
    """Daily context for one market, fetched once."""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bars = fetch_daily(symbol)
        self.atr = atr_series(self.bars)
        self.emas = {k: ema([b.c for b in self.bars], k) for k in (20, 50, 200)}
        self.meta = CONTRACTS[symbol]
        self.comm = COMMS.get(symbol, COMMISSION)

    def trades(self, spec: dict, cost_mult: float = 1.0,
               keep=None) -> list[dict]:
        fn, _grid, rcfg = RULES[spec["rule"]]
        sig = fn(self.bars, self.atr, self.emas, spec.get("params") or {})
        if keep is not None:
            sig = [(i, s) for i, s in sig if keep(self.bars, self.atr, self.emas, i, s)]
        comm = self.comm * cost_mult
        return bracket(self.bars, self.atr, sig, spec["stop"], spec["target"],
                       spec["hold"], self.meta["pv"], self.meta["tick"],
                       rcfg["entry"], comm)

    def random_baseline(self, spec: dict, trials: int = 400, seed: int = 11) -> dict:
        """The same bracket on random entries. This is the coin flip to beat."""
        rng = random.Random(seed)
        fn, _grid, rcfg = RULES[spec["rule"]]
        n_sig = len(fn(self.bars, self.atr, self.emas, spec.get("params") or {}))
        if not n_sig:
            return {"trials": 0}
        means = []
        for _ in range(trials):
            idx = sorted(rng.randrange(2, len(self.bars) - 2) for _ in range(n_sig))
            sig = [(i, rng.choice(("long", "short"))) for i in idx]
            rows = bracket(self.bars, self.atr, sig, spec["stop"], spec["target"],
                           spec["hold"], self.meta["pv"], self.meta["tick"],
                           rcfg["entry"], self.comm)
            if rows:
                means.append(statistics.mean(r["net"] for r in rows))
        return {"trials": len(means), "means": means}


def summarise(trades: list[dict]) -> dict:
    if not trades:
        return {"trades": 0, "win": 0.0, "avg_r": 0.0, "total_r": 0.0, "t": 0.0}
    rs = [t["net"] for t in trades]
    wins = sum(1 for r in rs if r > 0)
    sd = statistics.pstdev(rs) or 1e-9
    return {"trades": len(rs), "win": round(100 * wins / len(rs), 1),
            "avg_r": round(statistics.mean(rs), 3), "total_r": round(sum(rs), 2),
            "t": round(statistics.mean(rs) / (sd / math.sqrt(len(rs))), 2)}


def folds(trades: list[dict], count: int = 5) -> list[dict]:
    """Five equal slices of time. Consistency has to be visible, not asserted."""
    dated = [t for t in trades if t.get("date")]
    if len(dated) < count:
        return []
    dated.sort(key=lambda t: t["date"])
    size = len(dated) // count
    out = []
    for k in range(count):
        chunk = dated[k * size:(k + 1) * size] if k < count - 1 else dated[k * size:]
        s = summarise(chunk)
        out.append({"from": chunk[0]["date"], "to": chunk[-1]["date"],
                    "trades": s["trades"], "avg_r": s["avg_r"], "total_r": s["total_r"]})
    return out


def evaluate(spec: dict, market: Market | None = None, quiet: bool = False,
             baseline_trials: int = 400, keep=None) -> dict:
    """Score one spec. `keep` is an optional signal filter, used by the loop."""
    market = market or Market(spec["market"])
    errs = validate_spec(spec)
    if errs:
        return {"spec": spec, "errors": errs, "verdict": "REJECT"}

    base = market.trades(spec, keep=keep)
    by_date = lambda rows, lo, hi: [t for t in rows if lo <= t["date"] < hi]  # noqa: E731
    early, late = by_date(base, "0000", SPLIT), by_date(base, SPLIT, "9999")
    stressed = market.trades(spec, cost_mult=3.0, keep=keep)
    stress_late = by_date(stressed, SPLIT, "9999")

    # --- parameter neighbourhood: does the edge survive one step sideways?
    neigh = []
    for d_stop, d_target in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        si = STOP_CHOICES.index(spec["stop"]) + d_stop
        ti = TARGET_CHOICES.index(spec["target"]) + d_target
        if not (0 <= si < len(STOP_CHOICES) and 0 <= ti < len(TARGET_CHOICES)):
            continue
        variant = {**spec, "stop": STOP_CHOICES[si], "target": TARGET_CHOICES[ti]}
        rows = by_date(market.trades(variant, keep=keep), SPLIT, "9999")
        neigh.append({"stop": variant["stop"], "target": variant["target"],
                      "avg_r": summarise(rows)["avg_r"], "trades": len(rows)})

    # --- baselines
    rnd = market.random_baseline(spec, trials=baseline_trials)
    actual_avg = summarise(late)["avg_r"]
    p_value = None
    if rnd.get("means"):
        beaten = sum(1 for m in rnd["means"] if m >= actual_avg)
        p_value = round(beaten / len(rnd["means"]), 3)
    bh = (market.bars[-1].c / market.bars[0].c - 1) * 100 if market.bars else 0.0

    report = {
        "spec": spec,
        "at": now_iso(),
        "market": spec["market"],
        "as": market.meta["trade_as"],
        "all": summarise(base),
        "early": summarise(early),
        "late": summarise(late),
        "folds": folds(base),
        "cost_stress_3x": {"late": summarise(stress_late)},
        "neighbourhood": neigh,
        "random_baseline": {"trials": rnd.get("trials", 0), "p_value": p_value,
                            "mean_r": round(statistics.mean(rnd["means"]), 3)
                            if rnd.get("means") else None},
        "buy_hold_pct": round(bh, 1),
    }
    report["checks"], report["verdict"] = judge(report)
    if not quiet:
        print_report(report)
    return report


def judge(rep: dict) -> tuple[list[dict], str]:
    """The eight refusals, applied literally."""
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    late, allr = rep["late"], rep["all"]
    check("enough trades", late["trades"] >= MIN_TRADES and allr["trades"] >= 2 * MIN_TRADES,
          f"{allr['trades']} total, {late['trades']} after {SPLIT} (need "
          f"{2 * MIN_TRADES} / {MIN_TRADES})")
    check("positive out of sample", late["avg_r"] > 0,
          f"{late['avg_r']:+.3f}R average after {SPLIT}")
    check("costs", rep["cost_stress_3x"]["late"]["avg_r"] > 0,
          f"{rep['cost_stress_3x']['late']['avg_r']:+.3f}R with 3x commission and slippage")
    pos_folds = sum(1 for f in rep["folds"] if f["avg_r"] > 0)
    check("consistent across time", not rep["folds"] or pos_folds >= 3,
          f"{pos_folds}/{len(rep['folds'])} time slices positive")
    stable = [n for n in rep["neighbourhood"] if n["avg_r"] > 0]
    check("not a lone parameter", not rep["neighbourhood"] or len(stable) >= 2,
          f"{len(stable)}/{len(rep['neighbourhood'])} neighbouring settings also positive")
    p = rep["random_baseline"]["p_value"]
    check("beats random entries", p is not None and p <= 0.10,
          f"random-entry p-value {p if p is not None else 'n/a'}")
    check("significant", late["t"] >= 1.5,
          f"t-stat {late['t']} on the out-of-sample half")
    timing = RULES[rep["spec"]["rule"]][2]["entry"]
    check("no look-ahead", timing in ("same_open", "next_open"),
          f"entry is {timing}: the signal is knowable at the price that fills it")

    hard = [c for c in checks if not c["ok"]]
    return checks, "KEEP" if not hard else "REJECT"


def print_report(rep: dict) -> None:
    s = rep["spec"]
    print("=" * 92)
    print(f"  {s['name']}   {rep['market']} as {rep['as']}   "
          f"rule {s['rule']} {s.get('params')}   "
          f"{s['stop']}/{s['target']}/{s['hold']}")
    print("=" * 92)
    print(f"  hypothesis: {s['hypothesis'][:88]}")
    print()
    print(f"  {'set':<22}{'trades':>7}{'win':>8}{'avg R':>9}{'total R':>10}{'t':>7}")
    for label, key in (("all history", "all"), (f"before {SPLIT}", "early"),
                       (f"after {SPLIT}", "late")):
        row = rep[key]
        print(f"  {label:<22}{row['trades']:>7}{row['win']:>7.0f}%{row['avg_r']:>+9.3f}"
              f"{row['total_r']:>+10.2f}{row['t']:>7.1f}")
    print()
    if rep["folds"]:
        print("  time slices: " + "  ".join(
            f"{f['from'][:7]}→{f['to'][:7]} {f['avg_r']:+.2f}R" for f in rep["folds"]))
        print()
    print(f"  costs at 3x: {rep['cost_stress_3x']['late']['avg_r']:+.3f}R out of sample")
    print(f"  neighbours:  " + ("  ".join(
        f"{n['stop']}/{n['target']} {n['avg_r']:+.2f}R" for n in rep["neighbourhood"]) or "none"))
    print(f"  random entry: p = {rep['random_baseline']['p_value']} over "
          f"{rep['random_baseline']['trials']} trials (mean "
          f"{rep['random_baseline']['mean_r']}R)")
    print(f"  buy & hold:  {rep['buy_hold_pct']:+.1f}% over the same span")
    print()
    for c in rep["checks"]:
        print(f"  {'PASS' if c['ok'] else 'FAIL'}  {c['check']:<26}{c['detail']}")
    print()
    print(f"  VERDICT: {rep['verdict']}")
    if rep["verdict"] == "REJECT":
        print("  " + "; ".join(c["detail"] for c in rep["checks"] if not c["ok"]))
    print()


# --------------------------------------------------- the self-improvement loop
HYPOTHESES = {
    "atr_band": ("only trade when volatility is inside its normal band",
                 60, 95),
    "trend_agree": ("only trade with the 50/200 alignment", 0, 0),
    "skip_monday": ("skip the session after the weekend, when gaps dominate", 0, 0),
    "tighter_target": ("take profit sooner than the bracket says", 0, 0),
    "wider_stop": ("give the trade more room so noise cannot stop it", 0, 0),
}


def _keep(spec: dict, name: str):
    """Turn a hypothesis into a signal filter or a bracket change."""
    if name == "atr_band":
        def keep(bars, atr, emas, i, side):
            live = [a for a in atr[max(0, i - 120):i] if a]
            if len(live) < 20:
                return False
            pct = 100 * sum(1 for v in live if v <= atr[i - 1]) / len(live)
            return 60 <= pct <= 95
        return {"spec": spec, "keep": keep}

    if name == "trend_agree":
        def keep(bars, atr, emas, i, side):
            f, s = emas[50][i], emas[200][i]
            if f is None or s is None:
                return False
            return (f > s) == (side == "long")
        return {"spec": spec, "keep": keep}

    if name == "skip_monday":
        def keep(bars, atr, emas, i, side):
            return datetime.fromtimestamp(bars[i - 1].t, tz=timezone.utc).weekday() != 4
        return {"spec": spec, "keep": keep}

    if name == "tighter_target":
        ti = max(TARGET_CHOICES.index(spec["target"]) - 1, 0)
        return {"spec": {**spec, "target": TARGET_CHOICES[ti]}}
    if name == "wider_stop":
        si = min(STOP_CHOICES.index(spec["stop"]) + 1, len(STOP_CHOICES) - 1)
        return {"spec": {**spec, "stop": STOP_CHOICES[si]}}
    return {"spec": spec}


def loop(base: dict | None = None) -> dict:
    """observe -> diagnose -> hypothesise -> experiment -> validate -> keep or revert."""
    base = base or {**TEMPLATES["reversion"], "market": "CL=F"}
    market = Market(base["market"])
    errs = validate_spec(base)
    if errs:
        print(f"  baseline spec is invalid: {errs}")
        return {}

    baseline = evaluate(base, market, quiet=True, baseline_trials=120)
    print("=" * 92)
    print(f"  IMPROVEMENT LOOP — baseline {base['name']} on {base['market']}")
    print("=" * 92)
    print(f"  baseline: {baseline['late']['avg_r']:+.3f}R out of sample over "
          f"{baseline['late']['trades']} trades, win {baseline['late']['win']:.0f}%")
    if baseline["late"]["avg_r"] <= 0:
        print("  diagnosis: the baseline is not working out of sample, so the honest "
              "move is to fix or drop it, not to add filters until the number is "
              "positive.")
    else:
        print("  diagnosis: baseline works; the question is whether a filter helps "
              "or just fits noise.")

    # Each hypothesis is one trial, and every trial raises the bar for the next.
    # Trying six fixes and keeping the best is how a strategy gets fitted to its
    # own past, so the significance hurdle rises with the number of attempts.
    late_base = baseline["late"]["avg_r"]
    trials: list[dict] = []
    attempts = 0
    for name, (why, *_rest) in HYPOTHESES.items():
        candidate = _keep(base, name)
        spec, keep = candidate["spec"], candidate.get("keep")
        # A filter keeps the same spec and narrows the signals. The first version
        # skipped these entirely because `spec == base`, so three of the five
        # hypotheses were written, never tested, and never reported.
        attempts += 1
        rep = evaluate(spec, market, quiet=True, baseline_trials=120, keep=keep)
        late_var = rep["late"]["avg_r"]
        improved = late_var > late_base and rep["late"]["trades"] >= 10
        bar = 1.5 + 0.12 * attempts          # 1.62, then 1.74, then 1.86 ...
        significant = rep["late"]["t"] >= bar
        decision = "KEEP" if (improved and significant and rep["verdict"] == "KEEP") else "REVERT"
        trials.append({
            "name": name, "why": why, "decision": decision, "filter": bool(keep),
            "late_r": rep["late"]["avg_r"], "late_trades": rep["late"]["trades"],
            "t": rep["late"]["t"], "t_bar": round(bar, 2),
            "verdict": rep["verdict"], "vs_baseline_r": round(late_var - late_base, 3),
            "spec": spec,
        })
        mark = "KEEP  " if decision == "KEEP" else "REVERT"
        print(f"  {mark} {name:<16} {late_var:+.3f}R vs baseline {late_base:+.3f}R "
              f"({late_var - late_base:+.3f})  t={rep['late']['t']:.1f} "
              f"need ≥{bar:.2f}")
        print(f"         {why}")

    log = {"at": now_iso(), "baseline": base, "baseline_late_r": late_base,
           "trials": trials}
    LAB.mkdir(parents=True, exist_ok=True)
    with EXPERIMENTS.open("a") as fh:
        fh.write(json.dumps(log) + "\n")
    kept = [t for t in trials if t["decision"] == "KEEP"]
    print(f"\n  {len(kept)} of {len(trials)} hypotheses cleared both the holdout and "
          f"the rising bar. Logged to {EXPERIMENTS}")
    print("  A loop that always finds an improvement is not learning, it is overfitting.")
    return log


def history() -> None:
    if not EXPERIMENTS.exists():
        print("  no experiments recorded yet — run --loop")
        return
    for line in EXPERIMENTS.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        print(f"  {row['at']}  baseline {row['baseline']['name']} on "
              f"{row['baseline']['market']} → {row['baseline_late_r']:+.3f}R")
        for t in row.get("trials", []):
            print(f"    {t['decision']:<7}{t['name']:<16}{t['late_r']:+.3f}R  "
                  f"t={t['t']}  verdict {t['verdict']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", help="path to a spec JSON file")
    ap.add_argument("--template", choices=sorted(TEMPLATES), help="print a starter spec")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--history", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.template:
        print(json.dumps(TEMPLATES[args.template], indent=2))
    elif args.history:
        history()
    elif args.loop:
        loop()
    elif args.spec:
        spec = json.loads(Path(args.spec).read_text())
        rep = evaluate(spec)
        if args.json:
            print(json.dumps(rep, indent=2))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
