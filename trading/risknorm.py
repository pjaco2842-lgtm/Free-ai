#!/usr/bin/env python3
"""Fix the binding constraint: the cap skips the only leg that works.

The $300 stop cap was adopted in RESEARCH-LOG (xix) because three one-micro legs could
risk $996 against a $1,000 buffer. It works as a survival rule and it is not up for
re-measurement. But it has a side effect that the forward record has now made obvious:
the stop is written as 0.5 ATR, so when ATR rises the dollar risk rises with it and the
cap stands the leg down. ES -- the one leg with a positive forward record -- has been
refused on six consecutive sessions ($318, $381, $402, $416, $426, $440) while the legs
the cap was built to restrain (GC, 36% of its signals) are the only ones still entering.

The cap answers "too much risk" by not trading. There is a second answer: keep the trade
and make the stop narrower in points, so the dollar risk is fixed. That is a different
rule (a tighter stop is hit more often), so it has to be measured, not assumed:

  skip    -- the current policy: take the trade only if 0.5 ATR * mult <= ceiling.
  fixed   -- take every signal, with stop = min(0.5 ATR, ceiling / (mult * micros)).
             The target stays at 2R *of the risk actually taken*, so a fixed $300 stop
             targets $600, exactly like a capped trade would.

Both are scored the way the account scores them: one micro, the end-of-day trailing
floor, the $25,100 lock, the 50% consistency add-on and the $400 session lock, from
every 2023+ starting session. A policy is only adopted if it improves the pass rate
without worsening the breach rate, and if it holds on more than one leg.

Also here, because they are the other two levers on the same problem:
  - a per-leg ceiling (ES can carry a wider stop than CL: same dollars, different ATR),
  - two simple regime filters on the entry (long only above the 200-day average; and
    only when ATR/price is in the lower half of its own last year),
  - the drift-adjusted null on the finalists: weekday-matched random long entries with
    the same stop and target, 100 draws, so index drift is paid out of the score.

    python3 risknorm.py              # policy tables, per leg and as one book
    python3 risknorm.py --selftest   # arithmetic only, no data

Paper only. Nothing here writes a ledger.
"""
from __future__ import annotations

import argparse
import statistics
from pathlib import Path

import edge_causal as E
from profitlock import walk
from riskcap import LEGS

ROOT = Path(__file__).resolve().parent
ERA = "2023-01-01"
LOCK = 400.0
CEILINGS = (None, 200, 250, 300, 350, 400, 450)
# the intraday order profitlock.py uses: market-at-open first, then the resting limits
ORDER = ["cl-open-gap", "es-pdlow1", "cl-pdlow1", "gc-pdlow1"]
# candidate legs the book does not trade yet, measured on the same terms
CANDIDATES = [
    ("nq-pdlow1", "NQ=F", {"family": "limit_low", "n": 1, "gap": "any"}, 0.5, "tp2", "proven"),
    ("es-break2", "ES=F", {"family": "nr_break", "n": 2, "gap": "any"}, 0.5, "tp2", "proven"),
    ("cl-break2", "CL=F", {"family": "nr_break", "n": 2, "gap": "any"}, 0.5, "tp2", "proven"),
]


# ------------------------------------------------------------------------ signals
def sma(D: dict, i: int, n: int = 200) -> float | None:
    if i - n < 0:
        return None
    return sum(D["c"][i - n:i]) / n


def atr_rank(D: dict, i: int, look: int = 250) -> float | None:
    """Where this session's ATR sits in its own trailing year, 0 (calm) .. 1 (wild)."""
    if i - look < 15:
        return None
    a = [D["atr"][j] for j in range(i - look, i) if D["atr"][j] > 0]
    if len(a) < 30:
        return None
    return sum(1 for x in a if x <= D["atr"][i - 1]) / len(a)


def passes(D: dict, i: int, filt: str) -> bool:
    if filt == "none":
        return True
    if filt == "trend":
        m = sma(D, i)
        return m is not None and D["c"][i - 1] > m
    if filt == "calm":
        r = atr_rank(D, i)
        return r is not None and r <= 0.5
    raise ValueError(filt)


def trades_risk(sym: str, fam: dict, stopk: float, exitname: str, resolution: str,
                policy: str = "skip", ceiling: float | None = 300.0,
                filt: str = "none") -> tuple[list[dict], dict]:
    """Every trade the rule takes under `policy`, with the dollars its stop risked."""
    D = E.load_csv(str(ROOT / "data" / f"{sym.replace('=F', '')}_F_1d.csv"))
    pv, tick = E.SPECS[sym]["mult"], E.SPECS[sym]["tick"]
    out: list[dict] = []
    for i in range(22, D["n"]):
        if fam.get("entry") == "open":
            sig = E.open_signal(D, i)
            if not sig:
                continue
            entry, kind, side = sig
        else:
            sig = E.signal(D, i, fam["family"], fam["n"], fam["gap"])
            if not sig:
                continue
            entry, kind = sig
            side = 1
        if not passes(D, i, filt):
            continue
        atr = D["atr"][i - 1]
        if atr <= 0:
            continue
        k = stopk
        if ceiling is not None:
            # the narrowest stop that keeps the dollars at the ceiling, never wider
            k_fixed = ceiling / (pv * atr)
            if policy == "skip":
                if stopk * atr * pv > ceiling:
                    continue
            else:
                k = min(stopk, k_fixed)
        risk = k * atr * pv
        usd = E.trade_pnl(D, i, entry, kind, k, E.EXITS[exitname], pv, tick,
                          resolution, side=side)
        if usd is None:
            continue
        out.append({"d": D["d"][i], "usd": usd, "risk": risk})
    return out, D


# -------------------------------------------------------------------- the account
def series(per: dict[str, dict[str, float]], dates: list[str],
           lock: float | None = LOCK) -> dict[str, float]:
    """date -> book profit with the session lock applied in trading order."""
    # Every leg in `per` must be counted: the first version iterated ORDER only, which
    # silently dropped any leg whose id was not on that list (NQ), and reported books
    # that looked identical to each other for a reason that had nothing to do with NQ.
    seq = [l for l in ORDER if l in per] + [l for l in per if l not in ORDER]
    day: dict[str, float] = {}
    for d in dates:
        s = 0.0
        for lid in seq:
            v = per.get(lid, {}).get(d)
            if v is None:
                continue
            if lock is not None and s >= lock:
                continue
            s += v
        if s:
            day[d] = s
    return day


def shape(day: dict[str, float]) -> dict:
    v = [x for d, x in day.items() if d >= ERA]
    eq = peak = dd = 0.0
    for x in v:
        eq += x
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    return {"net": sum(v), "best": max(v) if v else 0.0, "worst": min(v) if v else 0.0,
            "dd": dd, "days": len(v)}


def score(day: dict[str, float], dates: list[str]) -> dict:
    return {**shape(day), **walk(day, dates)}


def null_alpha(sym: str, fam: dict, stopk: float, exitname: str, resolution: str,
               policy: str, ceiling: float | None, draws: int = 100, seed: int = 11) -> dict:
    """Rule mean minus weekday-matched random long entries at the open, same stop/target."""
    import datetime as dt
    import numpy as np
    D = E.load_csv(str(ROOT / "data" / f"{sym.replace('=F', '')}_F_1d.csv"))
    pv, tick = E.SPECS[sym]["mult"], E.SPECS[sym]["tick"]
    tr, _ = trades_risk(sym, fam, stopk, exitname, resolution, policy, ceiling)
    rule = np.array([t["usd"] for t in tr if t["d"] >= ERA])
    if len(rule) < 30:
        return {"n": len(rule), "alpha": 0.0, "t": 0.0}
    dow = [dt.date.fromisoformat(x).weekday() for x in D["d"]]
    buckets: dict[int, list[int]] = {}
    for i in range(22, D["n"]):
        buckets.setdefault(dow[i], []).append(i)
    days = [dt.date.fromisoformat(t["d"]).weekday() for t in tr if t["d"] >= ERA]
    rng = np.random.default_rng(seed)
    means = np.empty(draws)
    for b in range(draws):
        vals = []
        for k in days:
            j = int(rng.choice(buckets[k]))
            atr = D["atr"][j - 1]
            if atr <= 0:
                continue
            kk = stopk
            if ceiling is not None:
                if policy == "skip" and stopk * atr * pv > ceiling:
                    continue
                kk = min(stopk, ceiling / (pv * atr))
            p = E.trade_pnl(D, j, D["o"][j], "open", kk, E.EXITS[exitname], pv, tick,
                            "proven", side=1)
            if p is not None:
                vals.append(p)
        means[b] = statistics.fmean(vals) if vals else 0.0
    alpha = rule.mean() - means.mean()
    return {"n": len(rule), "rule": rule.mean(), "null": means.mean(),
            "alpha": alpha, "t": alpha / means.std(ddof=1) if means.std(ddof=1) else 0.0}


def selftest() -> None:
    # a fixed-dollar stop on a $10/pt contract at 10 ATR points -> $100 a point? no:
    # 0.5 * 20 * 10 = $100 risk, a $60 ceiling means 6 points, i.e. $60 of risk exactly
    assert abs(min(0.5, 60 / (10.0 * 20.0)) * 20 * 10 - 60.0) < 1e-9
    # the skip policy refuses that same trade instead of narrowing it
    per = {"es-pdlow1": {"2026-01-02": 700.0}, "cl-pdlow1": {"2026-01-02": 200.0}}
    assert series(per, ["2026-01-02"])["2026-01-02"] == 700.0   # lock refuses the 200
    assert series(per, ["2026-01-02"], lock=None)["2026-01-02"] == 900.0
    print("selftest ok: a fixed stop risks exactly the ceiling, the lock stops the later leg")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--null", action="store_true", help="run the drift null on finalists")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return

    dates = E.load_csv(str(ROOT / "data" / "ES_F_1d.csv"))["d"]

    print("## Per leg: what the cap policy does to each rule (2023+, one micro)\n")
    print("| leg | policy | trades | win | $/trade | net | median risk | pass% | breach% |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    best: dict[str, tuple] = {}
    catalog: dict[str, tuple] = {}
    for lid, sym, fam, stopk, exitname, res, _ in LEGS + [
            (c[0], c[1], c[2], c[3], c[4], c[5], 1) for c in CANDIDATES]:
        catalog[lid] = (sym, fam, stopk, exitname, res)
        rows = []
        for policy in ("skip", "fixed"):
            for cap in (None, 250, 300, 350, 400, 450):
                if policy == "skip" and cap is None:
                    continue
                tr, D = trades_risk(sym, fam, stopk, exitname, res, policy, cap)
                near = [t for t in tr if t["d"] >= ERA]
                if len(near) < 20:
                    continue
                day = {}
                for t in near:
                    day[t["d"]] = day.get(t["d"], 0.0) + t["usd"]
                w = walk(day, D["d"])
                rows.append({"policy": policy, "cap": cap, "n": len(near),
                             "win": 100 * sum(1 for t in near if t["usd"] > 0) / len(near),
                             "mean": statistics.fmean(t["usd"] for t in near),
                             "net": sum(t["usd"] for t in near),
                             "risk": statistics.median(t["risk"] for t in near), **w})
        for r in rows:
            lab = "none" if r["cap"] is None else (
                f"{r['policy']} ${r['cap']:.0f}")
            print(f"| {lid} | {lab} | {r['n']} | {r['win']:.0f}% | ${r['mean']:+.2f} | "
                  f"${r['net']:+,.0f} | ${r['risk']:.0f} | {r['pass']:.1f}% | {r['breach']:.1f}% |")
        # the per-leg pick: best pass rate whose breach is no worse than the $300 skip
        base = next((r for r in rows if r["policy"] == "skip" and r["cap"] == 300), None)
        ok = [r for r in rows if base is None or r["breach"] <= base["breach"] + 0.5]
        if ok:
            best[lid] = max(ok, key=lambda r: r["pass"])
        print("|---|---|---:|---:|---:|---:|---:|---:|---:|")

    print("\n## The live book under each policy (ES, CL limit, GC; gap retired)\n")
    print("| policy | trades | net | best day | worst day | max DD | pass% | breach% | "
          "median sessions |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    book_legs = [l for l in LEGS if l[0] != "cl-open-gap"]
    for policy in ("skip", "fixed"):
        for cap in (300, 350, 400, 450):
            per = {}
            for lid, sym, fam, stopk, exitname, res, _ in book_legs:
                tr, _ = trades_risk(sym, fam, stopk, exitname, res, policy, cap)
                per[lid] = {t["d"]: t["usd"] for t in tr if t["d"] >= ERA}
            day = series(per, dates)
            s = score(day, dates)
            med = "-" if s["median"] is None else f"{s['median']:.0f}"
            print(f"| {policy} ${cap:.0f} | {sum(len(v) for v in per.values())} | "
                  f"${s['net']:+,.0f} | ${s['best']:+,.0f} | ${s['worst']:+.0f} | "
                  f"${s['dd']:+,.0f} | {s['pass']:.1f}% | {s['breach']:.1f}% | {med} |")

    print("\n## Per-leg ceilings, chosen one leg at a time (best pass, breach not worse)\n")
    print("| leg | policy | cap | pass% | breach% | $/trade |")
    print("|---|---|---:|---:|---:|---:|")
    per = {}
    for lid, r in best.items():
        print(f"| {lid} | {r['policy']} | ${r['cap']:.0f} | {r['pass']:.1f}% | "
              f"{r['breach']:.1f}% | ${r['mean']:+.2f} |")
    for lid, r in best.items():
        sym, fam, stopk, exitname, res = catalog[lid]
        tr, _ = trades_risk(sym, fam, stopk, exitname, res, r["policy"], r["cap"])
        per[lid] = {t["d"]: t["usd"] for t in tr if t["d"] >= ERA}
    # any leg the per-leg pick dropped keeps the flat $300 skip
    for lid, sym, fam, stopk, exitname, res, _ in book_legs:
        if lid in per:
            continue
        tr, _ = trades_risk(sym, fam, stopk, exitname, res, "skip", 300)
        per[lid] = {t["d"]: t["usd"] for t in tr if t["d"] >= ERA}
    day = series(per, dates)
    s = score(day, dates)
    med = "-" if s["median"] is None else f"{s['median']:.0f}"
    print(f"\nBook with those per-leg settings: net ${s['net']:+,.0f}, best day "
          f"${s['best']:+,.0f}, worst ${s['worst']:+.0f}, DD ${s['dd']:+,.0f}, "
          f"pass {s['pass']:.1f}%, breach {s['breach']:.1f}%, median {med} sessions.")

    print("\n## Regime filters on the prior-low legs (skip policy, $300 cap)\n")
    print("| leg | filter | trades | win | $/trade | pass% | breach% |")
    print("|---|---|---:|---:|---:|---:|---:|")
    for lid, sym, fam, stopk, exitname, res, _ in book_legs:
        for filt in ("none", "trend", "calm"):
            tr, D = trades_risk(sym, fam, stopk, exitname, res, "skip", 300, filt)
            near = [t for t in tr if t["d"] >= ERA]
            if len(near) < 20:
                continue
            day = {}
            for t in near:
                day[t["d"]] = day.get(t["d"], 0.0) + t["usd"]
            w = walk(day, D["d"])
            print(f"| {lid} | {filt} | {len(near)} | "
                  f"{100 * sum(1 for t in near if t['usd'] > 0) / len(near):.0f}% | "
                  f"${statistics.fmean(t['usd'] for t in near):+.2f} | {w['pass']:.1f}% | "
                  f"{w['breach']:.1f}% |")

    if a.null:
        print("\n## Drift null on the prior-low lines at the chosen policy (100 draws)\n")
        print("| leg | trades | $/trade | null $/trade | alpha | t |")
        print("|---|---:|---:|---:|---:|---:|")
        for lid in list(catalog):
            if "gap" in lid or "break" in lid:
                continue
            sym, fam, stopk, exitname, res = catalog[lid]
            r = best.get(lid, {"policy": "skip", "cap": 300})
            n = null_alpha(sym, fam, stopk, exitname, res, r["policy"], r["cap"])
            print(f"| {lid} | {n['n']} | ${n.get('rule', 0):+.2f} | ${n.get('null', 0):+.2f} | "
                  f"${n['alpha']:+.2f} | {n['t']:+.2f} |")

    print("\n## Books of those legs, one micro each, with the session lock\n")
    print("| book | trades | net | worst day | max DD | reached% | pass% | of reached, "
          "failed consistency | breach% | median | days two legs lose together |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    bookday: dict[str, dict[str, float]] = {}
    SPEC = {
        "es-pdlow1": {"policy": "skip", "cap": 300},
        "gc-pdlow1": {"policy": "fixed", "cap": 250},
        "nq-pdlow1": {"policy": "fixed", "cap": 250},
        "cl-pdlow1": {"policy": "skip", "cap": 250},
    }
    BOOKS = {
        "A current: ES+CL+GC (all skip $300)": [("es-pdlow1", "skip", 300),
                                                 ("cl-pdlow1", "skip", 300),
                                                 ("gc-pdlow1", "skip", 300)],
        "B ES + GC fixed $250": [("es-pdlow1", "skip", 300),
                                 ("gc-pdlow1", "fixed", 250)],
        "C ES + GC + NQ (fixed $250)": [("es-pdlow1", "skip", 300),
                                        ("gc-pdlow1", "fixed", 250),
                                        ("nq-pdlow1", "fixed", 250)],
        "D ES + NQ (fixed $250)": [("es-pdlow1", "skip", 300),
                                   ("nq-pdlow1", "fixed", 250)],
        "E ES fixed $250 + GC + NQ": [("es-pdlow1", "fixed", 250),
                                      ("gc-pdlow1", "fixed", 250),
                                      ("nq-pdlow1", "fixed", 250)],
        "F ES + CL $250 + GC": [("es-pdlow1", "skip", 300),
                                ("cl-pdlow1", "skip", 250),
                                ("gc-pdlow1", "fixed", 250)],
        "G NQ fixed $250 alone": [("nq-pdlow1", "fixed", 250)],
        "H ES skip $300 alone": [("es-pdlow1", "skip", 300)],
        "I ES + NQ (skip $300)": [("es-pdlow1", "skip", 300),
                                  ("nq-pdlow1", "skip", 300)],
        "J NQ skip $300 alone": [("nq-pdlow1", "skip", 300)],
        "K ES skip $300 + GC skip $350": [("es-pdlow1", "skip", 300),
                                           ("gc-pdlow1", "skip", 350)],
    }
    for name, legs in BOOKS.items():
        per_b: dict[str, dict[str, float]] = {}
        losses: dict[str, int] = {}
        for lid, policy, cap in legs:
            sym, fam, stopk, exitname, res = catalog[lid]
            tr, _ = trades_risk(sym, fam, stopk, exitname, res, policy, cap)
            per_b[lid] = {t["d"]: t["usd"] for t in tr if t["d"] >= ERA}
            for t in tr:
                if t["d"] >= ERA and t["usd"] < 0:
                    losses[t["d"]] = losses.get(t["d"], 0) + 1
            keep = [t for t in tr if t["d"] >= ERA]
        # duplicate-id books would overwrite each other; legs here are unique
        day = series(per_b, dates)
        s = score(day, dates)
        med = "-" if s["median"] is None else f"{s['median']:.0f}"
        together = sum(1 for d, n in losses.items() if n >= 2)
        ntr = sum(len(v) for v in per_b.values())
        bookday[name] = day
        cons_fail = 100.0 * (s["reached"] - s["pass"]) / s["reached"] if s["reached"] else 0.0
        print(f"| {name} | {ntr} | ${s['net']:+,.0f} | ${s['worst']:+.0f} | "
              f"${s['dd']:+,.0f} | {s['reached']:.1f}% | {s['pass']:.1f}% | "
              f"{cons_fail:.0f}% | {s['breach']:.1f}% | {med} | {together} |")

    print("\n## The session lock re-measured on the two best books (it was fixed at $400 "
          "when the book had a gap leg the size of a day)\n")
    print("| book | lock | net | best day | pass% | reached% | breach% | median |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for name in ("H ES skip $300 alone", "G NQ fixed $250 alone",
                 "I ES + NQ (skip $300)", "D ES + NQ (fixed $250)"):
        per_b = {}
        for lid, policy, cap in BOOKS[name]:
            sym, fam, stopk, exitname, res = catalog[lid]
            tr, _ = trades_risk(sym, fam, stopk, exitname, res, policy, cap)
            per_b[lid] = {t["d"]: t["usd"] for t in tr if t["d"] >= ERA}
        for lk in (None, 200.0, 300.0, 400.0, 600.0):
            day = series(per_b, dates, lock=lk)
            s = score(day, dates)
            med = "-" if s["median"] is None else f"{s['median']:.0f}"
            print(f"| {name} | {'none' if lk is None else f'${lk:.0f}'} | "
                  f"${s['net']:+,.0f} | ${s['best']:+,.0f} | {s['pass']:.1f}% | "
                  f"{s['reached']:.1f}% | {s['breach']:.1f}% | {med} |")


if __name__ == "__main__":
    main()
