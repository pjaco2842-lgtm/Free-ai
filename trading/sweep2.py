#!/usr/bin/env python3
"""Wide causal search: families, indicators and candles on daily futures bars.

The rules of evidence, applied uniformly to every configuration:

  * a decision at bar i uses bars <= i-1, plus bar i's own OPEN for market entries;
  * resolution is close-based. A daily bar has a high and a low but not their order,
    so a target or stop is booked only when the CLOSE is beyond it. This understates
    rules that spike through a level, and it cannot book a target that traded before
    the entry filled -- the error that produced every impressive number this project
    printed before RESEARCH-LOG (t).
  * in-sample (start..2022) and out-of-sample (2023..) are shown side by side. A rule
    is only interesting if it survives the split;
  * a random-entry control runs the identical exit grid, because a grid this wide will
    manufacture high win rates out of nothing and the control shows how high;
  * the best configuration's t-stat is compared with sqrt(2 ln N), the expected maximum
    of N draws from a null. Anything below that line is indistinguishable from luck.

usage
    python3 sweep2.py --csv data/ES_F_1d.csv --sym ES=F --out desk/sweep-es.md
    python3 sweep2.py --csv data/NQ_F_1d.csv --sym NQ=F --out desk/sweep-nq.md
    python3 sweep2.py --selftest
"""
from __future__ import annotations

import argparse
import math
import statistics
import zlib
from pathlib import Path

import edge_causal as E

TARGET_USD = 1_250.0
IS_END = "2022-12-31"
OS_START = "2023-01-01"


# ------------------------------------------------------------------- indicators
def sma(v: list[float], i: int, n: int):
    if i + 1 < n:
        return None
    return sum(v[i - n + 1:i + 1]) / n


def rsi(v: list[float], i: int, n: int = 2):
    """Simple-average RSI over n changes (Connors' RSI(2) convention, not Wilder)."""
    if i < n:
        return None
    gain = loss = 0.0
    for k in range(i - n + 1, i + 1):
        ch = v[k] - v[k - 1]
        gain += ch if ch > 0 else 0.0
        loss -= ch if ch < 0 else 0.0
    if loss == 0:
        return 100.0
    if gain == 0:
        return 0.0
    rs = (gain / n) / (loss / n)
    return 100.0 - 100.0 / (1.0 + rs)


# --------------------------------------------------------------------- families
# each returns (side, entry_price, kind) or None. side 1 = long, -1 = short.

def f_pd_low(D, i, p):
    n = p["n"]
    lvl = min(D["l"][i - n:i])
    o = D["o"][i]
    if p["gap"] == "with" and o <= D["c"][i - 1]:
        return None
    if o <= lvl:
        return (1, o, "open")
    if D["l"][i] <= lvl:
        return (1, lvl, "limit")
    return None


def f_pd_high(D, i, p):
    n = p["n"]
    lvl = max(D["h"][i - n:i])
    o = D["o"][i]
    if p["gap"] == "with" and o >= D["c"][i - 1]:
        return None
    if o >= lvl:
        return (-1, o, "open")
    if D["h"][i] >= lvl:
        return (-1, lvl, "limit")
    return None


def f_nr_break(D, i, p):
    n = p["n"]
    rng = [D["h"][k] - D["l"][k] for k in range(i - n, i)]
    if rng[-1] > min(rng):
        return None
    lvl, o = D["h"][i - 1], D["o"][i]
    if o > lvl:
        return (1, o, "open")
    if D["h"][i] >= lvl:
        return (1, lvl, "stop")
    return None


def f_inside(D, i, p):
    k = i - 1
    if not (D["h"][k] <= D["h"][k - 1] and D["l"][k] >= D["l"][k - 1]):
        return None
    lvl, o = D["h"][k], D["o"][i]
    if o > lvl:
        return (1, o, "open")
    if D["h"][i] >= lvl:
        return (1, lvl, "stop")
    return None


def f_engulf(D, i, p):
    k = i - 1
    bull = (D["c"][k] > D["o"][k] and D["c"][k - 1] < D["o"][k - 1]
            and D["c"][k] >= D["o"][k - 1] and D["o"][k] <= D["c"][k - 1])
    bear = (D["c"][k] < D["o"][k] and D["c"][k - 1] > D["o"][k - 1]
            and D["c"][k] <= D["o"][k - 1] and D["o"][k] >= D["c"][k - 1])
    if p["side"] == "long" and bull:
        return (1, D["o"][i], "open")
    if p["side"] == "short" and bear:
        return (-1, D["o"][i], "open")
    return None


def f_hammer(D, i, p):
    k = i - 1
    o, h, l, c = D["o"][k], D["h"][k], D["l"][k], D["c"][k]
    body, rng = abs(c - o), h - l
    if rng <= 0 or body <= 0:
        return None
    lower = min(o, c) - l
    upper = h - max(o, c)
    if lower < 2 * body or upper > body:
        return None
    return (1, D["o"][i], "open")


def f_rsi2(D, i, p):
    r = rsi(D["c"], i - 1, p.get("rsi_n", 2))
    m = sma(D["c"], i - 1, 200)
    if r is None or m is None:
        return None
    if p["side"] == "long" and r <= p["thr"] and D["c"][i - 1] > m:
        return (1, D["o"][i], "open")
    if p["side"] == "short" and r >= 100.0 - p["thr"] and D["c"][i - 1] < m:
        return (-1, D["o"][i], "open")
    return None


def f_pullback(D, i, p):
    m = sma(D["c"], i - 1, 200)
    if m is None or D["c"][i - 1] <= m:
        return None
    if all(D["c"][k] < D["c"][k - 1] for k in range(i - p["n"], i)):
        return (1, D["o"][i], "open")
    return None


def f_gapfade(D, i, p):
    atr = D["atr"][i - 1]
    if atr <= 0:
        return None
    o, pc = D["o"][i], D["c"][i - 1]
    if o < pc - p["k"] * atr:
        return (1, o, "open")
    if o > pc + p["k"] * atr:
        return (-1, o, "open")
    return None


def f_random(D, i, p):
    """Deterministic pseudo-random entry: the null control, reproducible on every run."""
    if zlib.crc32(D["d"][i].encode()) % 1000 < p["per_mille"]:
        side = 1 if zlib.crc32((D["d"][i] + "side").encode()) % 2 else -1
        return (side, D["o"][i], "open")
    return None


FAMILIES = [
    ("pd_low", f_pd_low, [{"n": n, "gap": g} for n in (1, 2, 3, 5) for g in ("with", "any")]),
    ("pd_high", f_pd_high, [{"n": n, "gap": g} for n in (1, 2, 3, 5) for g in ("with", "any")]),
    ("nr_break", f_nr_break, [{"n": n} for n in (3, 5, 7)]),
    ("inside_break", f_inside, [{}]),
    ("engulf", f_engulf, [{"side": "long"}, {"side": "short"}]),
    ("hammer", f_hammer, [{}]),
    ("rsi2", f_rsi2, [{"side": "long", "thr": t} for t in (2, 5, 10)]
             + [{"side": "short", "thr": 5}]),
    ("pullback", f_pullback, [{"n": n} for n in (2, 3)]),
    ("gapfade", f_gapfade, [{"k": k} for k in (0.25, 0.5, 1.0)]),
]

STOPS = (0.5, 0.75, 1.0, 1.5)
TARGETS = (0.25, 0.33, 0.5, 0.75, 1.0, 1.5, None)
HORIZONS = (1, 2, 3, 5)
WARM = 200                                     # SMA200 needs 200 bars of history


# ------------------------------------------------------------------- simulate
def resolve(D, i, side, entry, stop, tgt, horizon):
    """Close-based resolution. Returns (exit_price, days_held)."""
    last = min(D["n"], i + horizon)
    for j in range(i, last):
        c = D["c"][j]
        if side > 0:
            if c <= stop:
                return stop, j - i + 1
            if tgt is not None and c >= tgt:
                return tgt, j - i + 1
        else:
            if c >= stop:
                return stop, j - i + 1
            if tgt is not None and c <= tgt:
                return tgt, j - i + 1
    return D["c"][last - 1], last - i


def run(D, famfn, p, stopk, target_r, horizon, mult, tick):
    cost = 2 * E.COMM_SIDE + 2 * tick * mult
    out = []
    for i in range(max(WARM, 21), D["n"] - 1):
        atr = D["atr"][i - 1]
        if atr <= 0:
            continue
        sig = famfn(D, i, p)
        if not sig:
            continue
        side, entry, _kind = sig
        risk = stopk * atr
        stop = entry - side * risk
        tgt = None if target_r is None else entry + side * target_r * risk
        px, days = resolve(D, i, side, entry, stop, tgt, horizon)
        gross = (px - entry) * side * mult
        # Drift adjustment. ES roughly doubled between 2023 and 2026, so a long rule
        # collects index beta whether or not it has an edge -- that is why random
        # entries scored 71% through the same exit grid. `bench` is what simply being
        # positioned that way for the same number of sessions would have paid, and
        # alpha is what is left over.
        bench = side * (D["c"][i + days - 1] - entry) * mult
        out.append({"date": D["d"][i], "usd": gross - cost, "alpha": gross - cost - bench,
                    "r": (px - entry) * side / risk, "days": days})
    return out


def stats(tr):
    if not tr:
        return None
    v = [t["usd"] for t in tr]
    a = [t["alpha"] for t in tr]
    n = len(v)
    mean = statistics.fmean(v)
    sd = statistics.pstdev(v) or 1e-9
    am = statistics.fmean(a)
    asd = statistics.pstdev(a) or 1e-9
    return {"n": n, "win": 100.0 * sum(1 for x in v if x > 0) / n, "mean": mean,
            "net": sum(v), "t": mean / (sd / math.sqrt(n)),
            "alpha": am, "alpha_t": am / (asd / math.sqrt(n)),
            "r": statistics.fmean(t["r"] for t in tr),
            "days": statistics.fmean(t["days"] for t in tr)}


def label(fam, p):
    bits = [fam]
    for k in ("n", "gap", "side", "thr", "k", "per_mille"):
        if k in p:
            bits.append(f"{k}={p[k]}")
    return " ".join(bits)


# ----------------------------------------------------------------------- report
def build_grid(with_random: bool):
    grid = []
    for fam, fn, params in FAMILIES:
        for p in params:
            for stopk in STOPS:
                for target_r in TARGETS:
                    for horizon in HORIZONS:
                        grid.append((label(fam, p), fn, p, stopk, target_r, horizon))
    if with_random:
        for p in ({"per_mille": 200},):
            for stopk in STOPS:
                for target_r in TARGETS:
                    for horizon in HORIZONS:
                        grid.append((label("random", p), f_random, p, stopk, target_r, horizon))
    return grid


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--sym", default="ES=F")
    ap.add_argument("--out", default="desk/sweep.md")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    if not args.csv:
        print("No bars. Pass --csv date,open,high,low,close. Nothing was written.")
        raise SystemExit(2)

    spec = E.SPECS[args.sym]
    mult, tick = spec["mult"], spec["tick"]
    D = E.load_csv(args.csv)
    sessions = D["n"] - max(WARM, 21)
    print(f"{args.sym}: {D['n']} sessions {D['d'][0]} -> {D['d'][-1]}")

    grid = build_grid(with_random=False)
    rows = []
    for name, fn, p, stopk, target_r, horizon in grid:
        tr = run(D, fn, p, stopk, target_r, horizon, mult, tick)
        ins = [t for t in tr if t["date"] <= IS_END]
        oos = [t for t in tr if t["date"] >= OS_START]
        a, b = stats(ins), stats(oos)
        if not a or not b or a["n"] < 40 or b["n"] < 25:
            continue
        rows.append({"name": name, "stop": stopk, "target": target_r, "hold": horizon,
                     "ins": a, "oos": b, "all": stats(tr)})

    # rank by out-of-sample dollars per trade, but never let a rule in on sample size alone
    # Ranked on alpha, not dollars: dollars include the market's own rise.
    rows.sort(key=lambda r: -r["oos"]["alpha"])
    robust = [r for r in rows if r["ins"]["alpha"] > 0 and r["oos"]["alpha"] > 0
              and r["oos"]["win"] >= 60.0]
    N = len(grid)
    thr = math.sqrt(2.0 * math.log(max(N, 2)))
    best_t = max((r["oos"]["alpha_t"] for r in robust), default=0.0)

    # null control
    null = []
    for p in ({"per_mille": 200},):
        for stopk in STOPS:
            for target_r in TARGETS:
                for horizon in HORIZONS:
                    tr = run(D, f_random, p, stopk, target_r, horizon, mult, tick)
                    oos = stats([t for t in tr if t["date"] >= OS_START])
                    if oos and oos["n"] >= 25:
                        null.append(oos)
    null_win = max((x["win"] for x in null), default=0.0)
    null_mean = max((x["mean"] for x in null), default=0.0)
    null_alpha = max((x["alpha"] for x in null), default=0.0)
    os_idx = [i for i, d in enumerate(D["d"]) if d >= OS_START]
    drift = (D["c"][-1] / D["c"][os_idx[0]] - 1.0) * 100.0 if os_idx else 0.0

    L = [f"# Wide causal search — {args.sym}", "",
         f"{D['n']} sessions, {D['d'][0]} to {D['d'][-1]}. One micro (${mult:.0f}/pt), "
         f"${2 * E.COMM_SIDE + 2 * tick * mult:.2f} round trip assumed on every trade.",
         f"Decision at bar i sees bars <= i-1; resolution is close-based; the split is "
         f"in-sample (to {IS_END}) and out-of-sample ({OS_START} on).", "",
         f"**{N} configurations tested.** With that many, the best of a pure-luck search "
         f"tends to reach |t| ~ {thr:.2f}, so the best t here is **{best_t:.2f}**. "
         + ("It clears the line." if best_t > thr else
            "It does **not** clear the line, which means nothing here is distinguishable "
            "from luck yet."),
         "",
         f"**Drift:** the index moved **{drift:+.0f}%** across the out-of-sample window, "
         f"and a long trade held for that long collects it. Both dollar columns are "
         f"therefore also reported as **alpha** — dollars minus what simply being "
         f"positioned that way over the same sessions paid.", "",
         f"**Null control:** random entries through the same exit grid reached "
         f"**{null_win:.0f}% win rate**, **${null_mean:+.2f}/trade** and "
         f"**${null_alpha:+.2f} alpha** out-of-sample. A rule has to beat that row, "
         f"not zero.", ""]

    def table(rs, title):
        out = [f"## {title}", "",
               "| rule | stop | target | hold | IS n | IS win | OS n | OS win | OS $/tr | "
               "IS alpha | OS alpha | OS alpha t | tr/sess | $/sess |",
               "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for r in rs:
            a, b = r["ins"], r["oos"]
            tgt = "close" if r["target"] is None else f"{r['target']}R"
            out.append(f"| {r['name']} | {r['stop']}A | {tgt} | {r['hold']} | {a['n']} | "
                       f"{a['win']:.0f}% | {b['n']} | {b['win']:.0f}% | "
                       f"${b['mean']:+.2f} | ${a['alpha']:+.2f} | ${b['alpha']:+.2f} | "
                       f"{b['alpha_t']:+.2f} | {b['n'] / sessions:.3f} | "
                       f"${b['alpha'] * b['n'] / sessions:+.2f} |")
        return out

    L += table(robust[:15], "Survives both halves (positive IS and OS, >=60% OS win)")
    if not robust:
        L.append("(nothing survived: no configuration was positive in both halves)")
    L += [""]

    high_win = [r for r in rows if r["oos"]["win"] >= 70.0 and r["oos"]["n"] >= 40]
    high_win.sort(key=lambda r: -r["oos"]["alpha"])
    L += table(high_win[:10], "Everything at 70%+ out-of-sample win rate, ranked by alpha")
    if not high_win:
        L.append("(no configuration reached 70% out-of-sample win rate with 40+ trades)")

    if robust:
        best = robust[0]
        per_sess = best["oos"]["alpha"] * best["oos"]["n"] / sessions
        L += ["", f"### What the best surviving line implies", "",
              f"`{best['name']}`, {best['stop']} ATR stop, "
              f"{'close exit' if best['target'] is None else str(best['target']) + 'R target'}, "
              f"{best['hold']}-session hold: **${per_sess:+.2f} per session at one micro, "
              f"${2 * per_sess:+.2f} at two** (costs double with size, so this is close).",
              f"At ${2 * per_sess:+.2f} a session, +$1,250 takes "
              f"**{TARGET_USD / (2 * per_sess):.0f} sessions**."
              if per_sess > 0 else
              "It does not pay, so the sessions-to-target question does not arise."]

    Path(args.out).write_text("\n".join(L) + "\n")
    print("\n".join(L[:14]))
    print(f"\nwrote {args.out}")


def selftest() -> None:
    """The resolver must never book a target a close did not reach."""
    D = {"d": ["a", "b", "c"], "o": [100.0] * 3, "h": [120.0] * 3,
         "l": [95.0] * 3, "c": [100.0, 101.0, 106.0], "atr": [10.0] * 3, "n": 3}
    # target 104 is never a close; holding 1 session must exit on the close, not the high
    px, days = resolve(D, 1, 1, 100.0, 90.0, 104.0, 1)
    assert (px, days) == (101.0, 1), (px, days)
    # a close beyond the target fills AT the target, never at the better close
    px, days = resolve(D, 0, 1, 100.0, 90.0, 104.0, 3)
    assert px == 104.0 and days == 3, (px, days)
    # no close ever reached 96, so the short exits on the horizon close two bars later
    px, days = resolve(D, 1, -1, 100.0, 110.0, 96.0, 3)
    assert (px, days) == (106.0, 2), (px, days)
    # a short stop is above entry and must trigger on a close through it
    px, days = resolve(D, 0, -1, 100.0, 100.5, 90.0, 3)
    assert px == 100.5 and days == 2, (px, days)
    assert rsi([1, 2, 3, 4], 3, 2) > 99.0
    print("selftest ok: close-only resolution, horizons, shorts, RSI bounds")


if __name__ == "__main__":
    main()
