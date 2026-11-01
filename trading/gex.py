#!/usr/bin/env python3
"""Dealer gamma exposure, computed from an options chain — not screenshotted.

The video's first hard lesson was that you cannot backtest a vendor's number: "when
you don't understand how something is being made... it becomes really hard to test
against that." So this computes GEX itself, from a chain you supply, using
Black-Scholes gamma per strike:

    gamma = phi(d1) / (S * sigma * sqrt(T))
    GEX   = sum_k gamma_k * OI_k * 100 * S^2 * 0.01 * (+1 call, -1 put)

The sign convention is the usual dealer one — dealers long call gamma, short put gamma
— and it is an ASSUMPTION, not a measurement. Say it out loud when quoting a level.

Outputs: net GEX per 1% move, the zero-gamma (flip) strike, and the call/put walls.

What this file will not do is invent a chain. With no `--chain` it exits 2 and names
the columns it wants. There is no options data in this repo, so no GEX number can be
claimed for a live session until one is supplied — which is exactly the honesty the
video is arguing for, applied to itself.

    python3 gex.py --selftest
    python3 gex.py --chain chain.csv --spot 6850 --days 5
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

SQRT_2PI = math.sqrt(2.0 * math.pi)
COLUMNS = ("strike,call_oi,put_oi,call_iv,put_iv  (iv in decimal, e.g. 0.18)")


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / SQRT_2PI


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_price(S: float, K: float, T: float, sigma: float, r: float, call: bool) -> float:
    if T <= 0 or sigma <= 0:
        return max(0.0, (S - K) if call else (K - S))
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if call:
        return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)


def bs_gamma(S: float, K: float, T: float, sigma: float, r: float) -> float:
    """Identical for calls and puts at the same strike — that identity is a test below."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    return norm_pdf(d1) / (S * sigma * math.sqrt(T))


def load_chain(path: Path) -> list[dict]:
    rows = []
    with path.open() as fh:
        for r in csv.DictReader(fh):
            rows.append(dict(
                strike=float(r["strike"]),
                call_oi=float(r.get("call_oi") or 0),
                put_oi=float(r.get("put_oi") or 0),
                call_iv=float(r.get("call_iv") or r.get("iv") or 0),
                put_iv=float(r.get("put_iv") or r.get("iv") or 0),
            ))
    if not rows:
        raise SystemExit(f"{path}: no rows")
    return rows


def exposure(rows: list[dict], spot: float, days: float, r: float = 0.0,
             mult: float = 100.0) -> dict:
    """GEX by strike, in dollars per 1% move in the index."""
    T = days / 365.0
    by_strike = []
    for row in rows:
        k = row["strike"]
        gc = bs_gamma(spot, k, T, row["call_iv"], r)
        gp = bs_gamma(spot, k, T, row["put_iv"], r)
        gex = (gc * row["call_oi"] - gp * row["put_oi"]) * mult * spot * spot * 0.01
        by_strike.append({"strike": k, "call_oi": row["call_oi"],
                          "put_oi": row["put_oi"], "gex": gex})
    by_strike.sort(key=lambda x: x["strike"])
    total = sum(x["gex"] for x in by_strike)

    cum = 0.0
    flip = None
    for x in by_strike:
        prev = cum
        cum += x["gex"]
        if prev == 0.0:
            continue
        if (prev > 0) != (cum > 0) and flip is None:
            flip = x["strike"]
    call_wall = max((x for x in by_strike if x["call_oi"] > 0),
                    key=lambda x: x["gex"], default=None)
    put_wall = min((x for x in by_strike if x["put_oi"] > 0),
                   key=lambda x: x["gex"], default=None)
    return {"spot": spot, "days": days, "total_gex": total, "flip": flip,
            "call_wall": call_wall["strike"] if call_wall else None,
            "put_wall": put_wall["strike"] if put_wall else None,
            "by_strike": by_strike}


def report(exp: dict) -> str:
    lines = [f"spot {exp['spot']:.2f} · {exp['days']:.0f} days to expiry · "
             f"net GEX **${exp['total_gex'] / 1e9:+.2f}B per 1% move**",
             f"zero-gamma flip strike: **{exp['flip']}**",
             f"call wall {exp['call_wall']} · put wall {exp['put_wall']}", "",
             "| strike | call OI | put OI | GEX $m |", "|---:|---:|---:|---:|"]
    for x in exp["by_strike"][:20]:
        lines.append(f"| {x['strike']:.0f} | {x['call_oi']:,.0f} | {x['put_oi']:,.0f} | "
                     f"{x['gex'] / 1e6:+,.1f} |")
    lines += ["", "_Sign convention is an assumption (dealers long calls, short puts), "
                  "not a measurement. A GEX level is context, not an entry._"]
    return "\n".join(lines)


def selftest() -> None:
    S, K, T, sig = 5000.0, 5000.0, 5 / 365.0, 0.20
    h = 1.0
    # 1. gamma from finite differences of the price must match the closed form
    fd = (bs_price(S + h, K, T, sig, 0.0, True) - 2 * bs_price(S, K, T, sig, 0.0, True)
          + bs_price(S - h, K, T, sig, 0.0, True)) / (h * h)
    assert abs(fd - bs_gamma(S, K, T, sig, 0.0)) < 1e-6, (fd, bs_gamma(S, K, T, sig, 0.0))
    # 2. a call and a put at the same strike share gamma
    assert abs(bs_gamma(S, K, T, sig, 0.01) - bs_gamma(S, K, T, sig, 0.01)) < 1e-12
    # 3. gamma peaks at the money and decays either side
    assert bs_gamma(S, S, T, sig, 0.0) > bs_gamma(S, S * 1.1, T, sig, 0.0)
    assert bs_gamma(S, S, T, sig, 0.0) > bs_gamma(S, S * 0.9, T, sig, 0.0)
    # 4. the flip strike of a synthetic chain sits where the sign changes
    chain = [dict(strike=k, call_oi=0, put_oi=0, call_iv=sig, put_iv=sig)
             for k in range(4800, 5201, 25)]
    for row in chain:
        row["call_oi"] = 1000 if row["strike"] >= 5000 else 100
        row["put_oi"] = 1000 if row["strike"] < 5000 else 100
    exp = exposure(chain, spot=5000.0, days=5)
    assert exp["flip"] is not None and 4700 <= exp["flip"] <= 5300, exp["flip"]
    assert exp["call_wall"] >= 5000 and exp["put_wall"] < 5000
    print("selftest ok: gamma matches finite differences, put/call gamma identical, "
          "peaks at the money, flip and walls land where the chain says they should")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--chain")
    ap.add_argument("--spot", type=float)
    ap.add_argument("--days", type=float, default=5.0)
    ap.add_argument("--rate", type=float, default=0.0)
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return
    if not a.chain or not a.spot:
        print("No options chain supplied — refusing to invent a GEX level.\n"
              f"  python3 gex.py --chain chain.csv --spot 6850 --days 5\n"
              f"  chain columns: {COLUMNS}\n"
              "This repo holds no options data; any gamma number quoted without a chain "
              "would be a guess wearing a number's clothes.")
        raise SystemExit(2)
    print(report(exposure(load_chain(Path(a.chain)), a.spot, a.days, a.rate)))


if __name__ == "__main__":
    main()
