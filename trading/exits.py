#!/usr/bin/env python3
"""Take the profit early, or hold for the target? Measure both.

"Take what you have if it looks like it will not reach" is a rule, not a feeling, and a
rule can be scored. On daily bars there is no intrabar path to look at, so the honest
versions of that instinct are all *close-based*:

  tp05        hold for the 0.5R target; stop on a close; give up at the horizon close
  tp_any      take the first close that is in profit for more than costs ("what you have")
  be025       hold for the target, but once a close shows +0.25R move the stop to entry,
              so a trade that fades exits as a scratch instead of a loss
  time2/time5 hold a fixed number of closes, then take the close whatever it is
  trail025    hold for the target, trailing the stop half a risk behind the best close

The catch the tables make obvious: an early exit shrinks the average win, and a smaller
average win needs a *higher* win rate to break even. Cutting winners is not free caution.

    python3 exits.py --csv es.csv          # the comparison
    python3 exits.py --selftest            # fixtures, no data needed
"""
from __future__ import annotations

import argparse
import statistics
from pathlib import Path

import edge_causal as E

SYM = "ES=F"
MULT = E.SPECS[SYM]["mult"]
TICK = E.SPECS[SYM]["tick"]
COST = 2 * E.COMM_SIDE + 2 * TICK * MULT        # round trip, dollars per micro
COST_PTS = COST / MULT
N, STOPK, HOLD, TARGET_M = 1, 1.0, 5, 0.5       # the live book's parameters


# ------------------------------------------------------------------ exit policies
def _tp_m(entry, risk, closes, m=TARGET_M, af=None):
    """Hold for m×risk. With `af`, arm a breakeven stop once a close shows +af×risk."""
    tgt, stop, armed = entry + m * risk, entry - risk, False
    for k, c in enumerate(closes):
        if c <= stop:
            return stop, k, "breakeven" if armed else "stop"
        if c >= tgt:
            return tgt, k, "target"
        if af and not armed and c >= entry + af * risk:
            armed, stop = True, entry
    return closes[-1], len(closes) - 1, "clock"


def _tp_any(entry, risk, closes):
    """First close that clears entry plus costs. This is 'take what you have'."""
    stop = entry - risk
    for k, c in enumerate(closes):
        if c <= stop:
            return stop, k, "stop"
        if c > entry + COST_PTS:
            return c, k, "early-profit"
    return closes[-1], len(closes) - 1, "clock"


def _time(entry, risk, closes, n):
    stop = entry - risk
    for k, c in enumerate(closes[:n]):
        if c <= stop:
            return stop, k, "stop"
    k = min(n, len(closes)) - 1
    return closes[k], k, "clock"


def _trail(entry, risk, closes, af=0.25):
    tgt, stop = entry + TARGET_M * risk, entry - risk
    for k, c in enumerate(closes):
        if c <= stop:
            return stop, k, "trail"
        if c >= tgt:
            return tgt, k, "target"
        if c >= entry + af * risk:
            stop = max(stop, c - af * risk)
    return closes[-1], len(closes) - 1, "clock"


POLICIES = {
    "tp05": lambda e, r, cs: _tp_m(e, r, cs),
    "tp_any": _tp_any,
    "be025": lambda e, r, cs: _tp_m(e, r, cs, af=0.25),
    "time2": lambda e, r, cs: _time(e, r, cs, 2),
    "time5": lambda e, r, cs: _time(e, r, cs, 5),
    "trail025": _trail,
}


# ------------------------------------------------------------------------ simulate
def simulate(D: dict, name: str) -> list[dict]:
    """Every entry the book would take, resolved by one exit policy, causally."""
    out = []
    for i in range(21, D["n"]):
        sig = E.signal(D, i, "limit_low", N, "with")
        if not sig or D["atr"][i - 1] <= 0:
            continue
        entry, _ = sig
        risk = STOPK * D["atr"][i - 1]
        closes = D["c"][i:i + HOLD]
        px, k, tag = POLICIES[name](entry, risk, closes)
        out.append({"date": D["d"][i], "entry": entry, "exit": px, "days": k + 1,
                    "tag": tag, "usd": (px - entry) * MULT - COST,
                    "r": (px - entry) / risk})
    return out


def stats(rows: list[dict], sessions: int) -> dict:
    if not rows:
        return {"n": 0}
    usd = [r["usd"] for r in rows]
    wins = [x for x in usd if x > 0]
    losses = [x for x in usd if x <= 0]
    aw = statistics.fmean(wins) if wins else 0.0
    al = abs(statistics.fmean(losses)) if losses else 0.0
    return {"n": len(usd), "win": 100.0 * len(wins) / len(usd),
            "mean": statistics.fmean(usd), "net": sum(usd),
            "avg_win": aw, "avg_loss": al,
            # break-even win rate for THIS trade shape, costs already inside the dollars.
            # With no wins or no losses it is undefined, not zero.
            "p_star": 100.0 * al / (aw + al) if (aw and al) else None,
            "r_mean": statistics.fmean(r["r"] for r in rows),
            "days": statistics.fmean(r["days"] for r in rows),
            "session": sum(usd) / sessions if sessions else float("nan")}


def report(D: dict) -> list[str]:
    days = D["n"] - 21
    res = {k: stats(simulate(D, k), days) for k in POLICIES}
    base = res["tp05"]
    L = ["# Exit policy: take the profit early, or hold?", "",
         f"{D['n']} sessions ({D['d'][0]} → {D['d'][-1]}), {SYM} close-resolution, one micro, "
         f"${COST:.2f} round trip. Entry: buy limit at the prior {N}-session low, gap-with, "
         f"{STOPK} ATR stop, target {TARGET_M}R, {HOLD}-session horizon.", "",
         "| policy | trades | win% | avg win | avg loss | break-even | $/trade | $/session | avg days |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, s in res.items():
        if not s["n"]:
            continue
        ps = f"{s['p_star']:.1f}%" if s["p_star"] is not None else "n/a"
        L.append(f"| {name} | {s['n']} | {s['win']:.0f}% | ${s['avg_win']:+,.0f} | "
                 f"${-s['avg_loss']:,.0f} | {ps} | ${s['mean']:+,.2f} | "
                 f"${s['session']:+,.2f} | {s['days']:.1f} |")
    if base.get("n"):
        t, a = base, res["tp_any"]
        f2 = lambda v: f"{v:.1f}%" if v is not None else "n/a"
        L += ["", "## What taking the profit early costs", "",
              "| | hold for 0.5R | take the first profitable close |",
              "|---|---:|---:|",
              f"| average win | ${t['avg_win']:,.0f} | ${a['avg_win']:,.0f} |",
              f"| average loss | ${-t['avg_loss']:,.0f} | ${-a['avg_loss']:,.0f} |",
              f"| break-even win rate | {f2(t['p_star'])} | {f2(a['p_star'])} |",
              f"| $/trade | ${t['mean']:+,.2f} | ${a['mean']:+,.2f} |", ""]
        if t["p_star"] is None or a["p_star"] is None:
            L.append("One side of this sample has no losing trades, so the break-even "
                     "comparison says nothing yet — it needs a sample containing both "
                     "outcomes.")
        else:
            worse = "higher" if a["p_star"] > t["p_star"] else "lower"
            L.append(f"Taking the profit early needs a **{worse}** win rate "
                     f"({a['p_star']:.1f}% vs {t['p_star']:.1f}%), because the average win is "
                     f"${a['avg_win']:,.0f} instead of ${t['avg_win']:,.0f}. It pays only if it "
                     "turns enough losses into scratches to cover that.")
        if base["n"] < 30:
            L.append(f"\n**Sample: {base['n']} trades** — far too few to prefer one policy over "
                     "another. Run the full history before believing any row.")
    L += ["", "## Why this cannot be done from a feeling", "",
          "A daily bar has a low, a high and a close, but not the order they happened in. "
          "'It started to tank' is invisible here; only closes are safe. Every policy above "
          "therefore acts on closes, and a close beyond the stop fills at the stop. Anything "
          "that claims to scalp the intrabar reversal needs intraday bars and a fill model, "
          "and this repo has neither.", "",
          "**Paper only. Not a forecast.**", ""]
    return L


# ------------------------------------------------------------------------ selftest
def _fixture() -> dict:
    """20 flat bars, then a gap-up day that fills the limit, then a day that reaches target."""
    rows = []
    for _ in range(20):
        rows.append(["2025-01-01", 4300.0, 4305.0, 4295.0, 4300.0])
    rows.append(["2025-01-02", 4301.0, 4302.0, 4294.0, 4296.0])   # fills 4295, closes +0.1R
    rows.append(["2025-01-03", 4296.0, 4302.0, 4295.0, 4301.0])   # closes +0.6R
    return E.build(rows)


def _selftest() -> None:
    D = _fixture()
    sig = E.signal(D, 20, "limit_low", N, "with")
    assert sig and sig[0] == 4295.0, f"entry should be the prior low, got {sig}"
    risk = D["atr"][19]
    assert risk > 0, "ATR must be warm by bar 20"

    px, k, tag = _tp_m(4295.0, risk, D["c"][20:25])
    assert (px, k, tag) == (4295.0 + TARGET_M * risk, 1, "target"), (px, k, tag)

    px, k, tag = _tp_any(4295.0, risk, D["c"][20:25])
    assert tag == "early-profit" and k == 0 and px == 4296.0, (px, k, tag)

    usd_early = (4296.0 - 4295.0) * MULT - COST
    usd_hold = (4295.0 + TARGET_M * risk - 4295.0) * MULT - COST
    assert usd_hold > usd_early, "holding to target must beat the early exit in this fixture"

    # arming breakeven can only ever change a loss into a scratch, never a win into a loss
    for closes in (D["c"][20:25], [4295.0 + 0.3 * risk, 4295.0 - 0.2 * risk],
                   [4294.0], [4300.0]):
        plain = _tp_m(4295.0, risk, closes)[0]
        armed = _tp_m(4295.0, risk, closes, af=0.25)[0]
        assert armed >= plain, f"breakeven made it worse: {armed} < {plain}"

    assert _time(4295.0, risk, [4296.0, 4301.0, 4290.0], 2)[1] == 1, "time stop exits early"
    print("selftest ok: early exit prices, target fill, breakeven never hurts, time stop")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="offline bars: date,open,high,low,close")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        _selftest()
        return
    if not args.csv:
        print("No bars. Pass --csv date,open,high,low,close. Nothing was invented and "
              "nothing was written.")
        raise SystemExit(2)
    D = E.load_csv(args.csv)
    if D["n"] < 30:
        print(f"Only {D['n']} bars — ATR(14), a prior low and a 5-session horizon need 30.")
        raise SystemExit(2)
    print("\n".join(report(D)))


if __name__ == "__main__":
    main()
