#!/usr/bin/env python3
"""Exploratory independent audit: pre-open features and one-contract open entries.

Data: Yahoo continuous daily futures, not specific December contracts. Freeze one rule
per market on 2009-2019 only. 2020+ has already been repeatedly inspected in earlier
research, so it is a reused validation sample, NOT a clean holdout. No book is written.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from lab import atr_series, fetch_daily
from scalp import MARKETS

HERE = Path(__file__).resolve().parent
OUT = HERE / 'desk' / 'audit-search.md'
STOPS = [0.25, 0.5, 0.75, 1.0, 1.5]
TARGETS = [0.25, 0.5, 1.0, 2.0, None]
THRESHOLDS = [-1.0, -0.5, 0.0, 0.5, 1.0]
COMMISSION_SIDE = {'ES=F': 0.50, 'NQ=F': 0.50, 'GC=F': 0.80,
                   'CL=F': 0.50, 'NKD=F': 1.75}


def shift(a, n):
    r = np.full(len(a), np.nan)
    r[n:] = a[:-n]
    return r


def feature_arrays(o, h, l, c, atr):
    p = lambda a, n=1: shift(a, n)
    a = p(atr)
    r = h - l
    # Every feature refers exclusively to bars completed before the entry session.
    with np.errstate(divide='ignore', invalid='ignore'):
        features = {
            'prior_body_atr': (p(c) - p(o)) / a,
            'prior_close_location': 2 * (p(c) - p(l)) / p(r) - 1,
            'prior_return_1': (p(c) - p(c, 2)) / a,
            'prior_return_2': (p(c) - p(c, 3)) / a,
            'prior_return_3': (p(c) - p(c, 4)) / a,
            'prior_return_5': (p(c) - p(c, 6)) / a,
            'prior_return_10': (p(c) - p(c, 11)) / a,
            'prior_gap': (p(o) - p(c, 2)) / a,
            'prior_range_minus_atr': p(r) / a - 1,
            'prior_lower_wick': (np.minimum(p(o), p(c)) - p(l)) / a,
            'prior_upper_wick': (p(h) - np.maximum(p(o), p(c))) / a,
            'prior_body_vs_prev': ((p(c) - p(o)) - (p(c, 2) - p(o, 2))) / a,
        }
    return {k: np.where(np.isfinite(v), v, np.nan) for k, v in features.items()}


def outcomes(o, h, l, c, atr_prev, tick, pv, commission, stop_k, target_k, side):
    # Whole ticks, rounded against the trader. Brackets relative to quoted open;
    # one tick each side is deducted separately. No price chronology after entry
    # is known when both exits touch: loss takes priority.
    span = np.ceil(stop_k * atr_prev / tick) * tick
    target = None if target_k is None else np.floor(target_k * span / tick) * tick
    if side == 1:
        hit = l <= o - span
        target_hit = np.zeros(len(o), bool) if target is None else h >= o + target
    else:
        hit = h >= o + span
        target_hit = np.zeros(len(o), bool) if target is None else l <= o - target
    gross = (c - o) * side
    if target is not None:
        gross = np.where(target_hit, target, gross)
    gross = np.where(hit, -span, gross)
    return gross * pv - 2 * (tick * pv + commission)


def stats(pnl, mask):
    x = pnl[mask]
    return {'trades': len(x), 'wins': int(np.sum(x > 0)),
            'win_pct': float(100 * np.mean(x > 0)) if len(x) else 0.,
            'net': float(np.sum(x)), 'per': float(np.mean(x)) if len(x) else 0.}


def walk_sessions(pnl, traded, dates, indices):
    """Close-only floor sensitivity, including non-trading sessions; censored attempts.

    Trades continue after first target if consistency fails. A breach is evaluated
    at session close using the floor established by the previous close. Intraday
    equity breaches, early closes and stop gaps are not modeled; rates are not live odds.
    """
    counts = {'pass': 0, 'breach': 0, 'unfinished': 0, 'pass3': 0}
    durations = []
    for start in indices:
        equity = 25000.0
        high = 25000.0
        best = 0.0
        result = 'unfinished'
        for j in range(start, len(dates)):
            daily = float(pnl[j]) if traded[j] else 0.0
            equity += daily
            best = max(best, daily)
            floor = max(24000.0, min(high - 1000.0, 25100.0))
            if equity <= floor:
                result = 'breach'
                break
            high = max(high, equity)
            if equity >= 26250 and best <= 0.4 * (equity - 25000):
                result = 'pass'
                days = j - start + 1
                durations.append(days)
                if days <= 3:
                    counts['pass3'] += 1
                break
        counts[result] += 1
    return {**counts, 'starts': len(indices),
            'median_pass_sessions': float(np.median(durations)) if durations else None}


def main():
    rng = np.random.default_rng(20261031)
    lines = ['# Independent open-entry research audit', '',
             'Experimental research only; **no strategy is approved or installed**.', '',
             'Signal features use only completed prior bars; enter one contract at the next '
             'daily-bar open. 12 features × 5 thresholds × 2 comparisons × 2 sides × '
             '5 stops × 5 exits = 6,000 configurations per market, 30,000 total. '
             'No filters are tuned using the open. Signals may be duplicates or overlap.', '',
             'For each market, select the highest training dollars/trade among rules '
             'with at least 150 2009–2019 trades, without inspecting later returns. '
             'Then evaluate that one frozen rule in 2020–2024 and 2025 onward. '
             '**Those periods have already been mined in this project and are not an '
             'independent holdout**. Random-side comparison is conditional on the same '
             'pre-open selected days and identical stop, exit and costs, 500 draws; '
             'it is not a multiple-testing-corrected proof.', '',
             'Entry is approximated at the daily open with one tick of entry and exit '
             'slippage, plus published per-side commissions. Stops round up and targets '
             'down to the tick. If both are touched, the stop wins. Stops assume no '
             'gap through the stop. Dollar outcomes use micro specifications except '
             'NKD, which is a full contract. Yahoo =F is a continuous proxy, not '
             'GCZ2026/ESZ2026/NQZ2026/CLZ2026/NKDZ2026 actual fills; roll adjustments, '
             'liquidity, session timestamps, holidays and executable open fills remain '
             'unverified. Exclude incomplete sessions. Do not use as a paper fill engine.', '']
    for sym, (_, pv, tick) in MARKETS.items():
        bars = fetch_daily(sym)
        # No same-date bar is considered complete; intentionally conservative.
        today = datetime.now(timezone.utc).date()
        bars = [b for b in bars if datetime.fromtimestamp(b.t, timezone.utc).date() < today]
        if not bars:
            raise RuntimeError(f'No completed bars for {sym}')
        dates = [datetime.fromtimestamp(b.t, timezone.utc).strftime('%Y-%m-%d') for b in bars]
        years = np.array([int(s[:4]) for s in dates])
        raw = [[b.t, b.o, b.h, b.l, b.c, b.v] for b in bars]
        digest = hashlib.sha256(json.dumps(raw, separators=(',', ':')).encode()).hexdigest()
        o, h, l, c = (np.array([getattr(b, k) for b in bars], float) for k in ('o', 'h', 'l', 'c'))
        atr = np.array([np.nan if x is None else x for x in atr_series(bars)])
        a = shift(atr, 1)
        features = feature_arrays(o, h, l, c, atr)
        train = (years <= 2019) & np.isfinite(a)
        test = (years >= 2020) & (years <= 2024) & np.isfinite(a)
        recent = (years >= 2025) & np.isfinite(a)
        comm = COMMISSION_SIDE[sym]
        results = {(stop, target, side): outcomes(o,h,l,c,a,tick,pv,comm,stop,target,side)
                   for stop in STOPS for target in TARGETS for side in (1, -1)}
        best = None
        qualified = 0
        for name, feature in features.items():
            for threshold in THRESHOLDS:
                for cmp in ('>', '<'):
                    select = np.isfinite(feature) & ((feature > threshold) if cmp == '>' else (feature < threshold)) & np.isfinite(a)
                    tm = select & train
                    n = int(tm.sum())
                    if n < 150:
                        continue
                    for side in (1, -1):
                        for stop in STOPS:
                            for target in TARGETS:
                                p = results[stop, target, side]
                                value = float(p[tm].mean())
                                qualified += 1
                                if best is None or value > best[0]:
                                    best = (value, name, threshold, cmp, side, stop, target, select)
        if best is None:
            raise RuntimeError(f'No qualified training rules for {sym}')
        _, name, threshold, cmp, side, stop, target, selected = best
        pnl = results[stop, target, side]
        tr, te, re = (stats(pnl, selected & m) for m in (train, test, recent))
        ix = np.flatnonzero(selected & test)
        opposite = results[stop, target, -side]
        if len(ix):
            draws = rng.integers(0, 2, (500, len(ix)), dtype=np.int8).astype(bool)
            random_totals = np.where(draws, pnl[ix], opposite[ix]).sum(axis=1)
            exceed = int(np.sum(random_totals >= pnl[ix].sum()))
            random_p = (exceed + 1) / 501
        else:
            random_p = None
        starts = np.flatnonzero((years >= 2023) & np.isfinite(a))
        acct = walk_sessions(pnl, selected, dates, starts)
        lines += [f'## {sym} ({MARKETS[sym][0]})', '',
                  f'- Data: {len(bars)} completed bars, {dates[0]} through {dates[-1]}; SHA-256 of fetched OHLCV {digest}.',
                  f'- 6,000 candidate configurations; {qualified:,} satisfy the training sample minimum.',
                  f'- Frozen training choice: {name} {cmp} {threshold:g}; {"long" if side == 1 else "short"}; stop {stop:g} ATR; exit {"close" if target is None else str(target) + "R"}.',
                  '| period | trades | win | net | per trade |', '|---|---:|---:|---:|---:|']
        for label, s in [('Train 2009–2019', tr), ('Reused 2020–2024', te), ('Reused 2025+', re)]:
            lines.append(f'| {label} | {s["trades"]} | {s["win_pct"]:.1f}% | ${s["net"]:+,.2f} | ${s["per"]:+,.2f} |')
        ptext = f'{random_p:.3f}' if random_p is not None else 'not available'
        lines += [f'- 2020–2024 random-side Monte Carlo p-value: {ptext} (unadjusted, {len(ix)} selected days; not a probability of profitability).',
                  f'- Illustrative 2023+ close-only account walk from every market session: {acct["pass"]} pass, {acct["breach"]} breach, {acct["unfinished"]} unfinished of {acct["starts"]} overlapping starts; {acct["pass3"]} within 3 sessions; median completed-pass time {acct["median_pass_sessions"]} sessions. Intraday breaches and fill uncertainty omitted; not a pass forecast.', '']
    OUT.write_text('\n'.join(lines) + '\n')
    print(f'Wrote {OUT}')


if __name__ == '__main__':
    main()
