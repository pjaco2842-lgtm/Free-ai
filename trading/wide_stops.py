#!/usr/bin/env python3
"""The wide-stop breakouts, re-measured causally, with the account in the room.

The claim from the other project: narrow-range and prior-day breakouts at 1.0-2.5 ATR
stops win 56-79% and earn $60-64 a trade, with 2.0 ATR the peak of the curve. None
of it was measured through this repo's causal exits, and none of it was priced
against a $1,000 buffer. Both are done here.

Why wide stops look wonderful and are not
-----------------------------------------
`edge_causal.trade_pnl(..., engine="proven")` resolves exits on closes only, which is
the only causal reading of a daily bar. With a 2.0 ATR stop and a 2R target, almost
nothing is ever closed out — the trade drifts to the close and books the drift. That
is why the stop-out count collapses to nearly zero and why the dollars look large:
the rule has quietly become buy-and-hold. Two controls are printed to show it:

  * drift     — dollars from simply being long on the same days, open to close;
  * null      — random long entries, same count, same stop, same exit, same costs.

A rule earns its keep only on the column that survives both.

    python3 wide_stops.py
    python3 wide_stops.py --symbols ES=F,NQ=F
"""
from __future__ import annotations

import argparse
import random
import statistics
from pathlib import Path

import edge_causal as E

ROOT = Path(__file__).resolve().parent
DESK = ROOT / "desk"
STOPS = [1.0, 1.5, 2.0, 2.5]
EXITS = ["tp2", "close"]
NR_RATIO = 0.7          # "narrow" = prior range below 70% of the ten before it
BUFFER = E.MAX_LOSS


# ------------------------------------------------------------------------ rules
def narrow_prior(D: dict, i: int) -> bool:
    """Was the session before this one a narrow range day?"""
    if i < 13:
        return False
    prior = D["h"][i - 1] - D["l"][i - 1]
    window = [D["h"][j] - D["l"][j] for j in range(i - 11, i - 1)]
    return prior < NR_RATIO * statistics.fmean(window)


def signal(D: dict, i: int, fam: str, n: int):
    """Long breakout of a prior high, causal: the level is known before the open."""
    if fam == "nday_break":
        lvl = max(D["h"][i - n:i])
    elif fam == "nr_break":
        if not narrow_prior(D, i):
            return None
        lvl = D["h"][i - 1]
    else:
        return None
    if D["o"][i] >= lvl:
        return D["o"][i], "stop"          # gapped through: fill at the open
    if D["h"][i] >= lvl:
        return lvl, "stop"
    return None


def record(D: dict, fam: str, n: int, stop: float, exitname: str,
           mult: float, tick: float) -> list[tuple[str, float, float]]:
    """(date, dollars at one micro, drift dollars on that day)."""
    out = []
    for i in range(21, D["n"]):
        sig = signal(D, i, fam, n)
        if not sig:
            continue
        entry, kind = sig
        pnl = E.trade_pnl(D, i, entry, kind, stop, E.EXITS[exitname], mult, tick, "proven")
        if pnl is None:
            continue
        drift = (D["c"][i] - D["o"][i]) * mult - (2 * E.COMM_SIDE + 2 * tick * mult)
        out.append((D["d"][i], pnl, drift))
    return out


def null(D: dict, count: int, stop: float, exitname: str, mult: float, tick: float,
         trials: int = 300, seed: int = 23) -> float:
    """Random long entries on the same instrument, same bracket, same costs."""
    rng = random.Random(seed)
    means = []
    for _ in range(trials):
        idx = rng.sample(range(21, D["n"]), min(count, D["n"] - 21))
        tot = 0.0
        for i in idx:
            pnl = E.trade_pnl(D, i, D["o"][i], "open", stop, E.EXITS[exitname],
                              mult, tick, "proven")
            tot += pnl or 0.0
        means.append(tot / max(len(idx), 1))
    return statistics.fmean(means)


def drawdown(pnls: list[float]) -> float:
    peak = run = 0.0
    for p in pnls:
        run += p
        peak = max(peak, run)
    dd = 0.0
    run = 0.0
    peak = 0.0
    for p in pnls:
        run += p
        peak = max(peak, run)
        dd = min(dd, run - peak)
    return dd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="ES=F")
    ap.add_argument("--trials", type=int, default=300)
    a = ap.parse_args()

    lines = ["# Wide stops, re-measured causally", "",
             "Causal exits only (closes decide), one micro, costs inside every dollar.",
             f"Narrow range means the prior session's range was below {NR_RATIO:.0%} of the "
             "ten before it. `drift` is the dollars from simply being long open-to-close on "
             "the same days; `null` is random long entries with the identical bracket.", ""]
    keepers = []

    for sym in [s.strip() for s in a.symbols.split(",") if s.strip()]:
        name = f"{sym.replace('=F', '')}_F_1d.csv"
        path = ROOT / "data" / name
        if not path.exists():
            print(f"  {name} missing — run fetch_bars.py")
            continue
        D = E.load_csv(str(path))
        mult, tick = E.SPECS[sym]["mult"], E.SPECS[sym]["tick"]
        last_atr = next((x for x in reversed(D["atr"]) if x > 0), 0.0)
        lines += [f"## {sym} — last ATR {last_atr:.2f} pts (one ATR = "
                  f"${last_atr * mult:,.0f}/micro)", "",
                  "| rule | stop | exit | trades | win | $/trade | net $ | risk $ | "
                  "of buffer | drift $/trade | null $/trade | alpha |",
                  "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        rows = []
        for fam, n in (("nr_break", 1), ("nday_break", 1), ("nday_break", 2),
                       ("nday_break", 5)):
            for stop in STOPS:
                for ex in EXITS:
                    rec = record(D, fam, n, stop, ex, mult, tick)
                    if len(rec) < 30:
                        continue
                    pnls = [r[1] for r in rec]
                    drift = statistics.fmean(r[2] for r in rec)
                    nullm = null(D, len(rec), stop, ex, mult, tick, a.trials)
                    risk = stop * last_atr * mult
                    row = dict(sym=sym, fam=fam, n=n, stop=stop, exit=ex,
                               trades=len(rec), win=100 * sum(1 for p in pnls if p > 0) / len(pnls),
                               avg=statistics.fmean(pnls), net=sum(pnls),
                               risk=risk, share=100 * risk / BUFFER,
                               drift=drift, null=nullm, alpha=statistics.fmean(pnls) - nullm,
                               dd=drawdown(pnls), first=rec[0][0], last=rec[-1][0])
                    rows.append(row)
                    lines.append(
                        f"| {fam}-{n} | {stop} ATR | {ex} | {row['trades']} | "
                        f"{row['win']:.0f}% | ${row['avg']:+.2f} | ${row['net']:+,.0f} | "
                        f"${risk:,.0f} | {row['share']:.0f}% | ${drift:+.2f} | "
                        f"${nullm:+.2f} | **${row['alpha']:+.2f}** |")
        lines.append("")
        best = sorted((r for r in rows if r["alpha"] > 0), key=lambda r: -r["avg"])[:6]
        for r in best:
            if r["share"] <= 40:
                keepers.append(r)

        # the honest comparison the screenshots made: dollars by stop distance
        lines += [f"### Does a wider stop earn more? ({sym}, nday_break-1, tp2)", "",
                  "| stop | trades | win | $/trade | net $ | drift $/trade | alpha | risk $ |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for r in sorted((x for x in rows if x["fam"] == "nday_break" and x["n"] == 1
                         and x["exit"] == "tp2"), key=lambda x: x["stop"]):
            lines.append(f"| {r['stop']} ATR | {r['trades']} | {r['win']:.0f}% | "
                         f"${r['avg']:+.2f} | ${r['net']:+,.0f} | ${r['drift']:+.2f} | "
                         f"${r['alpha']:+.2f} | ${r['risk']:,.0f} |")
        lines.append("")

    lines += ["## What is affordable", "",
              f"One micro with a ${BUFFER:,.0f} buffer: a stop costing more than 40% of it "
              f"(${0.4 * BUFFER:,.0f}) cannot be taken even once.", ""]
    if keepers:
        lines += ["| rule | stop | exit | $/trade | alpha | risk $ | trades |",
                  "|---|---:|---|---:|---:|---:|---:|"]
        for r in sorted(keepers, key=lambda r: -r["avg"]):
            lines.append(f"| {r['fam']}-{r['n']} | {r['stop']} ATR | {r['exit']} | "
                         f"${r['avg']:+.2f} | ${r['alpha']:+.2f} | ${r['risk']:,.0f} | "
                         f"{r['trades']} |")
    else:
        lines.append("Nothing kept a positive alpha at a stop the buffer can pay for.")

    DESK.mkdir(exist_ok=True)
    (DESK / "wide-stops.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nwrote desk/wide-stops.md ({len(keepers)} affordable positive-alpha configs)")


if __name__ == "__main__":
    main()
