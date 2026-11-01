#!/usr/bin/env python3
"""Intraday engine: opening-range breakout and gap fade, resolved bar by bar.

Daily bars cannot answer "can this make $500 in a day" -- they cannot even see the
intraday reversal that the exit question is about. This script uses the intraday pull
(5-minute and hourly ES) and resolves each trade on the bars that followed it:

  * the session is defined in New York time, so daylight saving cannot slide the
    opening range by an hour (the earlier naive UTC filter would have done exactly that
    for every winter session);
  * the opening range is the first N bars of the regular session (09:30-16:00 ET);
  * entry is CLOSE-confirmed: the first bar that closes beyond the range, entered at
    that close. That is the only intrabar entry a bar-close model can defend;
  * afterwards, if a bar contains both the stop and the target, the stop is assumed to
    have been hit first. Pessimistic on purpose;
  * a filtered set of sessions (range too wide) is skipped, as the published versions
    of this rule do.

usage
    python3 orb.py --csv data/ES_F_5m.csv --or-bars 6 --sym ES=F
    python3 orb.py --csv data/ES_F_1h.csv --or-bars 2 --sym ES=F
    python3 orb.py --selftest
"""
from __future__ import annotations

import argparse
import csv
import statistics
from collections import OrderedDict
from datetime import datetime, timedelta, timezone

import edge_causal as E

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:                              # noqa: BLE001 - tzdata missing
    ET = None

RTH_OPEN, RTH_CLOSE = (9, 30), (16, 0)
OS_START = "2026-01-01"


# ------------------------------------------------------------------------- loading
def _et(stamp: datetime) -> datetime:
    return stamp.astimezone(ET) if ET else stamp


def load_intraday(path: str):
    """Return OrderedDict{ET date: [(utc stamp, o,h,l,c), ...]} for regular hours."""
    out: OrderedDict = OrderedDict()
    skipped_tz = 0
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                stamp = datetime.strptime(row["date"].strip(), "%Y-%m-%d %H:%M")
                o, h, l, c = (float(row[k]) for k in ("open", "high", "low", "close"))
            except (KeyError, ValueError):
                continue
            stamp = stamp.replace(tzinfo=timezone.utc)
            loc = _et(stamp)
            if ET is None:
                skipped_tz += 1
                loc = stamp
            minutes = loc.hour * 60 + loc.minute
            if not (RTH_OPEN[0] * 60 + RTH_OPEN[1] <= minutes < RTH_CLOSE[0] * 60):
                continue                            # pre-market, overnight, after the bell
            out.setdefault(loc.strftime("%Y-%m-%d"), []).append(
                (stamp, o, h, l, c))
    if skipped_tz:
        print(f"warning: no tzdata, sessions keyed on UTC for {skipped_tz} bars")
    return OrderedDict((k, v) for k, v in out.items() if len(v) >= 3)


# ------------------------------------------------------------------------ families
def orb_trades(sessions, or_bars, stop_mult, target_mult, max_range_pct=None):
    """One close-confirmed breakout per session, stop at the far side of the range."""
    out = []
    for day, bars in sessions.items():
        if len(bars) <= or_bars + 1:
            continue
        rng = bars[:or_bars]
        hi = max(b[2] for b in rng)
        lo = min(b[3] for b in rng)
        width = hi - lo
        if width <= 0:
            continue
        if max_range_pct is not None and width / bars[0][1] > max_range_pct:
            continue
        side = entry = None
        start = 0
        for k in range(or_bars, len(bars)):
            c = bars[k][4]
            if c > hi:
                side, entry, start = 1, c, k + 1
                break
            if c < lo:
                side, entry, start = -1, c, k + 1
                break
        if side is None:
            continue
        stop = lo if side > 0 else hi
        risk = abs(entry - stop) * stop_mult
        if risk <= 0:
            continue
        stop_px = entry - side * risk
        tgt_px = entry + side * target_mult * risk
        px, k_end = _walk(bars, start, side, stop_px, tgt_px)
        out.append({"day": day, "side": side, "entry": entry, "exit": px,
                    "days": k_end, "risk_pts": risk})
    return out


def gap_trades(sessions, stop_mult, target_mult, min_gap_frac=0.3):
    """Fade a session gap toward the prior close; stop beyond the opening extreme."""
    days = list(sessions)
    out = []
    for i in range(1, len(days)):
        prev, cur = sessions[days[i - 1]], sessions[days[i]]
        prev_close = prev[-1][4]
        open_px = cur[0][1]
        gap = open_px - prev_close
        prev_range = max(b[2] for b in prev) - min(b[3] for b in prev)
        if prev_range <= 0 or abs(gap) < min_gap_frac * prev_range:
            continue
        side = -1 if gap > 0 else 1                # fade
        entry = open_px
        risk = stop_mult * abs(gap)
        stop_px = entry - side * risk
        tgt_px = prev_close
        px, k_end = _walk(cur, 0, side, stop_px, tgt_px)
        out.append({"day": days[i], "side": side, "entry": entry, "exit": px,
                    "days": k_end, "risk_pts": risk})
    return out


def _walk(bars, start, side, stop_px, tgt_px):
    """Bar-by-bar from `start`: stop wins ties, then target, else the session close."""
    for k in range(start, len(bars)):
        _, _o, h, l, _c = bars[k]
        if side > 0:
            if l <= stop_px:
                return stop_px, k + 1
            if h >= tgt_px:
                return tgt_px, k + 1
        else:
            if h >= stop_px:
                return stop_px, k + 1
            if l <= tgt_px:
                return tgt_px, k + 1
    return bars[-1][4], len(bars)


# --------------------------------------------------------------------------- stats
def summarise(trades, mult, tick, session_count):
    if not trades:
        return None
    cost = 2 * E.COMM_SIDE + 2 * tick * mult
    usd = [(t["exit"] - t["entry"]) * t["side"] * mult - cost for t in trades]
    wins = [x for x in usd if x > 0]
    losses = [x for x in usd if x <= 0]
    mean = statistics.fmean(usd)
    sd = statistics.pstdev(usd) or 1e-9
    aw = statistics.fmean(wins) if wins else 0.0
    al = abs(statistics.fmean(losses)) if losses else 0.0
    return {"n": len(usd), "win": 100.0 * len(wins) / len(usd), "mean": mean,
            "t": mean / (sd / len(usd) ** 0.5), "aw": aw, "al": al,
            "p_star": 100.0 * al / (aw + al) if (aw and al) else None,
            "session": mean * len(usd) / session_count if session_count else 0.0,
            "bars": statistics.fmean(t["days"] for t in trades)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--sym", default="ES=F")
    ap.add_argument("--or-bars", type=int, default=6)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    if not args.csv:
        print("No intraday bars. Pass --csv with date,open,high,low,close. Nothing written.")
        raise SystemExit(2)

    spec = E.SPECS[args.sym]
    mult, tick = spec["mult"], spec["tick"]
    sessions = load_intraday(args.csv)
    n_sess = len(sessions)
    first, last = next(iter(sessions)), next(reversed(sessions))
    print(f"{args.sym}: {n_sess} regular sessions, {first} -> {last}, "
          f"{sum(len(v) for v in sessions.values())} bars")

    L = [f"# Intraday: opening-range breakout and gap fade — {args.sym}", "",
         f"{n_sess} regular-hours sessions ({first} to {last}), "
         f"{args.or_bars}-bar opening range, one micro (${mult:.0f}/pt), "
         f"${2 * E.COMM_SIDE + 2 * tick * mult:.2f} round trip. "
         "Entry is close-confirmed; stops win ties inside a bar.", "",
         "| family | stop | target | trades | win% | avg win | avg loss | break-even | "
         "$/trade | t | $/session |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]

    rows = []
    for stop_mult in (0.5, 0.75, 1.0):
        for target_mult in (0.5, 0.75, 1.0, 1.5, 2.0):
            for fam, tr in (
                    ("orb", orb_trades(sessions, args.or_bars, stop_mult, target_mult, 0.0055)),
                    ("orb-wide", orb_trades(sessions, args.or_bars, stop_mult, target_mult)),
                    ("gapfade", gap_trades(sessions, stop_mult, target_mult))):
                s = summarise(tr, mult, tick, n_sess)
                if not s or s["n"] < 15:
                    continue
                rows.append((fam, stop_mult, target_mult, s))
    rows.sort(key=lambda r: -r[3]["mean"])
    for fam, stop_mult, target_mult, s in rows:
        ps = f"{s['p_star']:.1f}%" if s["p_star"] is not None else "n/a"
        L.append(f"| {fam} | {stop_mult} | {target_mult}R | {s['n']} | {s['win']:.0f}% | "
                 f"${s['aw']:+,.0f} | ${s['al']:,.0f} | {ps} | ${s['mean']:+,.2f} | "
                 f"{s['t']:+.2f} | ${s['session']:+,.2f} |")

    L += ["", f"**Sessions in the file: {n_sess}.** "
          + ("That is far too few to prefer one row: at 40-60 trades a 70% win rate has a "
             "standard error near 7 points, so treat every line as a hypothesis, not a "
             "result." if n_sess < 250 else
             "Enough sessions to compare rows, still short of a settled answer."), "",
          "**Paper only. Not a forecast.**", ""]
    text = "\n".join(L)
    print(text)
    out = f"desk/orb-{args.sym.replace('=', '_')}.md"
    open(out, "w").write(text + "\n")
    print(f"wrote {out}")


def _synth_session(day, path):
    """A session in New York time, expressed as UTC stamps the loader will read back."""
    out = []
    t = datetime(2026, 9, 14, 9, 30, tzinfo=timezone.utc)   # fake; ET offset applied below
    for i, (o, h, l, c) in enumerate(path):
        stamp = t + timedelta(minutes=5 * i)
        out.append((stamp, o, h, l, c))
    return out


def selftest() -> None:
    # six flat bars 100-101, then a close above the range at 102, then the session runs up
    bars = [(0, 100, 101, 99.5, 100.5)] * 3 + [(0, 100.5, 101, 100, 101)] * 3
    bars += [(0, 102, 102.5, 101.5, 102.5), (0, 102.5, 104, 102, 103.5)]
    sessions = OrderedDict([("s", bars)])          # loader shape: (stamp, o, h, l, c)
    tr = orb_trades(sessions, 6, 1.0, 1.5)
    assert len(tr) == 1, tr
    t = tr[0]
    assert t["side"] == 1 and t["entry"] == 102.5, t     # entry at the confirming close
    # stop is the range low 99.5, so risk is 3.0 and the target 1.5R away is 107
    assert abs(t["risk_pts"] - 3.0) < 1e-9, t
    assert t["exit"] == 103.5, t                          # never reached 107 -> session close
    # a gap down that fills to the prior close
    prev = [(None, 100, 101, 99, 100)] * 3
    cur = [(None, 98, 98.5, 97, 98.5), (None, 98.5, 100.5, 98, 100)]
    g = gap_trades(OrderedDict([("a", prev), ("b", cur)]), 1.0, 1.0, 0.3)
    assert len(g) == 1 and g[0]["side"] == 1 and g[0]["exit"] == 100.0, g
    print("selftest ok: close-confirmed entry, far-side stop, gap fade to prior close")


if __name__ == "__main__":
    main()
