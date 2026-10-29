#!/usr/bin/env python3
"""
Can $200-500 a day fit inside a $1,000 end-of-day buffer?

The answer is not about the signal, it is about the stop. On one contract:

    risk per stop = ATR * stop multiple * dollars per point

Gold's MGC is $10 a point and a 15-minute ATR of ~6 points, so one stop is ~$60.
That is 6% of the entire $1,000 buffer on every entry — which is why the gold desk
reached -$942 in nine sessions and why no amount of size fixes it.

MES is $5 a point and MCL is $100 a point per full dollar of crude. The claim to
test is that their stops are small enough for the same rule to survive a losing
streak on this account. This file measures that instead of asserting it: the same
aggressive sweep (six signal families, four exits, chosen on the first half,
scored on the second), but reporting median risk per trade alongside the P&L, plus
the sizing arithmetic for a daily target.

    python3 trading/sizing.py
    python3 trading/sizing.py --symbols ES=F,CL=F --floor 2
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aggressive import BASE, EXITS, STRATS, VARIANTS, build, run  # noqa: E402
from lab import COMMISSION  # noqa: E402
from scalp import MARKETS, day, load  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "desk" / "mes-mcl.md"
RAW = HERE / "desk" / "mes-mcl.json"

BUFFER = 1000.0          # Lucid Flex end-of-day drawdown
US_HOURS = set(range(13, 21))
SLIP_TICKS = 1


def measure(trades: list[dict], sessions: int) -> dict:
    if not trades:
        return {"trades": 0, "per_day": 0.0, "usd": 0.0, "med_risk": 0.0,
                "win": 0.0, "avg_r": 0.0, "dd": 0.0}
    usd = [t["usd"] for t in trades]
    eq = peak = dd = 0.0
    for u in usd:
        eq += u
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    return {"trades": len(trades), "per_day": len(trades) / max(sessions, 1),
            "usd": sum(usd), "med_risk": statistics.median(t["risk_usd"] for t in trades),
            "win": 100 * sum(1 for u in usd if u > 0) / len(usd),
            "avg_r": statistics.mean(t["r"] for t in trades), "dd": dd}


def sizing(med_risk: float, per_session: float, target: float) -> dict:
    """What it takes to clear `target` a day, and what that does to the buffer."""
    if per_session <= 0:
        return {"contracts": None, "risk": None, "stops": None}
    n = target / per_session
    risk = n * med_risk
    return {"contracts": n, "risk": risk, "stops": BUFFER / risk if risk else None}


def sweep(symbol: str, tf: str, floor: float) -> tuple[list[dict], dict | None]:
    name, pv, tick = MARKETS[symbol]
    bars = load(symbol, tf)
    if len(bars) < 400:
        return [], None
    cut = len(bars) // 2
    train, test = bars[:cut], bars[cut:]
    sess = (len({day(b.t) for b in train}), len({day(b.t) for b in test}))

    rows: list[dict] = []
    for strat in STRATS:
        for var in VARIANTS[strat]:
            p0 = {**BASE, **var, **EXITS[0]}
            S = build(bars, p0)                  # indicators only; exits/hours don't affect it
            for ex in EXITS:
                pp = {**p0, **ex}
                tr = measure(run(train, S, strat, pp, pv, tick), sess[0])
                if tr["trades"] < max(6, floor * sess[0] * 0.6):
                    continue
                rows.append({"symbol": symbol, "contract": name, "tf": tf,
                             "strat": strat, "params": pp, "train": tr, "S_cut": cut,
                             "test": measure(run(test, S, strat, pp, pv, tick), sess[1]),
                             "test_best": measure(run(test, S, strat, pp, pv, tick,
                                                      "target_first"), sess[1]),
                             "test_hours": measure(run(test, S, strat, {**pp, "hours": US_HOURS},
                                                       pv, tick), sess[1]),
                             "sessions_test": sess[1], "pv": pv, "tick": tick})
    ok = [r for r in rows if r["train"]["per_day"] >= floor] or rows
    if not ok:
        return rows, None
    return rows, max(ok, key=lambda r: r["train"]["total_r"] if "total_r" in r["train"]
                     else r["train"]["usd"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="ES=F,CL=F")
    ap.add_argument("--tf", default="15m,5m")
    ap.add_argument("--floor", type=float, default=2.0)
    args = ap.parse_args()

    syms = [s for s in args.symbols.split(",") if s]
    tfs = [t for t in args.tf.split(",") if t]

    print("=" * 104)
    print("  SIZING TEST — same aggressive sweep, micro contracts, $1,000 end-of-day buffer")
    print(f"  ${COMMISSION:.2f}/side + {SLIP_TICKS} tick slippage/side"
          f" · frequency floor {args.floor}/session")
    print("=" * 104)

    chosen: list[dict] = []
    population: list[dict] = []
    for tf in tfs:
        for sym in syms:
            try:
                rows, best = sweep(sym, tf, args.floor)
            except Exception as err:  # noqa: BLE001
                print(f"  {sym:7}{tf:5} data unavailable: {err}")
                continue
            population += rows
            if not rows:
                print(f"  {sym:7}{tf:5} no candidate")
                continue
            for r in rows:
                if best is not None and r is best:
                    chosen.append(r)
            if best is None:
                continue
            t, h, b = best["test"], best["test_hours"], best["test_best"]
            print(f"\n  {sym:7}{tf:5} chosen {best['strat']:12}"
                  f" {best['params']['stop']}A/{best['params']['target']}A"
                  f" {best['params']['hold']}b")
            print(f"    {'':9}{'trades':>7}{'/day':>7}{'win':>7}{'med risk':>10}"
                  f"{'net $':>10}{'$/session':>11}{'DD':>9}")
            for label, st in (("train", best["train"]), ("TEST", t),
                              ("test US", h), ("test best", b)):
                print(f"    {label:9}{st['trades']:7d}{st['per_day']:7.1f}{st['win']:7.0f}"
                      f"{st['med_risk']:10,.0f}{st['usd']:+10,.0f}"
                      f"{st['usd'] / max(best['sessions_test'], 1):+11,.0f}{st['dd']:9,.0f}")

    if not chosen:
        print("\n  nothing qualified.")
        return

    # ---------------------------------------------------------- sizing table
    print("\n" + "=" * 104)
    print("  WHAT $200 AND $500 A DAY WOULD REQUIRE (measured rate, one contract)")
    print("=" * 104)
    print(f"  {'market':8}{'tf':5}{'rule':13}{'$sess':>8}{'risk/stop':>11}"
          f"{'n for 200':>11}{'risk there':>12}{'stops to $1k':>14}")
    rows_out = []
    for r in chosen:
        t = r["test"]
        per_sess = t["usd"] / max(r["sessions_test"], 1)
        s200 = sizing(t["med_risk"], per_sess, 200)
        s500 = sizing(t["med_risk"], per_sess, 500)
        def fmt(x, spec):
            return "—" if x is None else format(x, spec)
        print(f"  {r['symbol']:8}{r['tf']:5}{r['strat']:13}{per_sess:+8,.0f}"
              f"{t['med_risk']:11,.0f}{fmt(s200['contracts'], ',.1f'):>11}"
              f"{fmt(s200['risk'], ',.0f'):>12}{fmt(s200['stops'], ',.2f'):>14}")
        rows_out.append({"symbol": r["symbol"], "tf": r["tf"], "strat": r["strat"],
                         "params": {k: v for k, v in r["params"].items() if k != "hours"},
                         "test": t, "test_hours": r["test_hours"],
                         "per_session": per_sess, "s200": s200, "s500": s500,
                         "sessions_test": r["sessions_test"]})

    # what size the buffer allows at all, regardless of target
    print("\n" + "=" * 104)
    print("  THE OTHER DIRECTION — the largest size a $1,000 buffer can carry")
    print("=" * 104)
    print("  A 5-stop run is ordinary at a 30-40% win rate, so the cap below keeps")
    print("  five stops inside the buffer. $/day is that size at the measured rate.")
    print(f"  {'market':8}{'tf':5}{'rule':13}{'risk/stop':>11}{'max contracts':>15}"
          f"{'$/day there':>13}{'5 stops':>10}")
    for r in chosen:
        t = r["test"]
        per_sess = t["usd"] / max(r["sessions_test"], 1)
        cap = int(BUFFER / (5 * t["med_risk"])) if t["med_risk"] else 0
        print(f"  {r['symbol']:8}{r['tf']:5}{r['strat']:13}{t['med_risk']:11,.0f}"
              f"{cap:15d}{per_sess * cap:+13,.0f}{5 * t['med_risk'] * cap:10,.0f}")

    # ------------------------------------------------------- population view
    print("\n" + "=" * 104)
    print("  WHOLE POPULATION — every config, out of sample (is the pick lucky?)")
    print("=" * 104)
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for r in population:
        groups.setdefault((r["symbol"], r["tf"], r["strat"]), []).append(r)
    print(f"  {'market':8}{'tf':5}{'strategy':13}{'configs':>8}{'positive':>10}"
          f"{'median $/sess':>15}{'median risk':>13}{'median /day':>13}")
    pop_rows = []
    for (sym, tf, strat), rs in sorted(groups.items(),
                                       key=lambda kv: -statistics.median(
                                           [x["test"]["usd"] / max(x["sessions_test"], 1)
                                            for x in kv[1]])):
        ps = [x["test"]["usd"] / max(x["sessions_test"], 1) for x in rs]
        rk = [x["test"]["med_risk"] for x in rs]
        pd = [x["test"]["per_day"] for x in rs]
        share = 100 * sum(1 for x in ps if x > 0) / len(ps)
        print(f"  {sym:8}{tf:5}{strat:13}{len(rs):8d}{share:9.0f}%"
              f"{statistics.median(ps):+15,.0f}{statistics.median(rk):13,.0f}"
              f"{statistics.median(pd):13.1f}")
        pop_rows.append({"symbol": sym, "tf": tf, "strat": strat, "configs": len(rs),
                         "pct_positive": share, "median_per_session": statistics.median(ps),
                         "median_risk": statistics.median(rk),
                         "median_per_day": statistics.median(pd)})

    # --------------------------------------------------------------- the file
    lines = ["# MES and MCL — can $200 a day fit a $1,000 buffer?", "",
             f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')} · "
             f"one micro contract · ${COMMISSION:.2f}/side + 1 tick slippage per side", "",
             "Same aggressive sweep as `aggressive.md` (six signal families, four exits, chosen on",
             "the first half of the sample, scored on the second half it never saw). The difference",
             "is that risk per stop is measured, because on this account that is the binding limit.", "",
             "## The chosen rule, and what one stop costs", "",
             "| market | tf | rule | test trades | /day | win | median risk/stop | net $ | $/session | max DD |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows_out:
        t = r["test"]
        lines.append(f"| {r['symbol']} | {r['tf']} | {r['strat']} | {t['trades']} | "
                     f"{t['per_day']:.1f} | {t['win']:.0f}% | ${t['med_risk']:,.0f} | "
                     f"${t['usd']:+,.0f} | ${r['per_session']:+,.0f} | ${t['dd']:,.0f} |")
    lines += ["", "With the US-session filter the paper rule uses (13:00-20:00 UTC):", "",
              "| market | tf | rule | trades | $/session (US hours only) |", "|---|---|---|---|---|"]
    for r in rows_out:
        h = r["test_hours"]
        lines.append(f"| {r['symbol']} | {r['tf']} | {r['strat']} | {h['trades']} | "
                     f"${h['usd'] / max(r['sessions_test'], 1):+,.0f} |")

    lines += ["", "## What $200 and $500 a day would need", "",
              "| market | tf | rule | $/session | risk/stop | contracts for $200 | risk at that size | stops until the buffer is gone |",
              "|---|---|---|---|---|---|---|---|"]
    for r in rows_out:
        s = r["s200"]
        lines.append(f"| {r['symbol']} | {r['tf']} | {r['strat']} | ${r['per_session']:+,.0f} | "
                     f"${r['test']['med_risk']:,.0f} | "
                     + ("—" if s["contracts"] is None else f"{s['contracts']:.1f}") + " | "
                     + ("—" if s["risk"] is None else f"${s['risk']:,.0f}") + " | "
                     + ("—" if s["stops"] is None else f"{s['stops']:.2f}") + " |")

    lines += ["", "## The largest size the buffer can carry", "",
              "A five-stop run is ordinary at a 30-40% win rate. This is the size that keeps five",
              "stops inside $1,000, and what that size earns at the measured rate.", "",
              "| market | tf | rule | risk/stop | max contracts | $/day at that size | five stops |",
              "|---|---|---|---|---|---|---|"]
    for r in rows_out:
        t = r["test"]
        cap = int(BUFFER / (5 * t["med_risk"])) if t["med_risk"] else 0
        lines.append(f"| {r['symbol']} | {r['tf']} | {r['strat']} | ${t['med_risk']:,.0f} | "
                     f"{cap} | {r['per_session'] * cap:+,.0f} | ${5 * t['med_risk'] * cap:,.0f} |")

    lines += ["", "## The whole population, not just the pick", "",
              "| market | tf | strategy | configs | positive out of sample | median $/session | median risk | median trades/day |",
              "|---|---|---|---|---|---|---|---|"]
    for p in pop_rows:
        lines.append(f"| {p['symbol']} | {p['tf']} | {p['strat']} | {p['configs']} | "
                     f"{p['pct_positive']:.0f}% | ${p['median_per_session']:+,.0f} | "
                     f"${p['median_risk']:,.0f} | {p['median_per_day']:.1f} |")
    lines += ["", "Chosen on `train`, measured on `test` (second half). `stop_first` throughout:",
              "when a bar held both stop and target, the stop was assumed to fill.", ""]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines))
    RAW.write_text(json.dumps({"floor": args.floor, "rows": rows_out,
                               "population": pop_rows}, indent=2, default=str))
    print(f"\n  written to {OUT}")


if __name__ == "__main__":
    main()
