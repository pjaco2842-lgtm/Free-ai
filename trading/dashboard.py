#!/usr/bin/env python3
"""
The dashboard — one static HTML file, no server, no JavaScript, no framework.

Why static
----------
It has to be readable from a phone, from GitHub, and from a Codespace that sleeps.
A static file generated from the ledgers does that. There is no process to keep
alive, no port to expose, no auth to get wrong, and nothing that can be reached
from the internet unless you publish it.

Security, because this page renders text from twenty news feeds
--------------------------------------------------------------
* every string is passed through `html.escape` — a headline containing
  `<script>` renders as characters, not as code
* a Content-Security-Policy with `default-src 'none'` and inline styles only
* no inline event handlers, no external fonts, no CDN, no iframes
* feed URLs are never rendered as links, so a headline cannot become a redirect

The alerts below are the ones that actually mean something has gone wrong: a
breached limit, a stale feed, a strategy that has gone silent, or a simulated
fill that cost more slippage than the plan assumes.

    python3 trading/dashboard.py             # write trading/desk/dashboard.html
    python3 trading/dashboard.py --print     # also print the alerts
"""

from __future__ import annotations

import argparse
import html
import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from account import ACCOUNT  # the firm's rules live in desk/account.json

HERE = Path(__file__).resolve().parent
DESK = HERE / "desk"
OUT = DESK / "dashboard.html"
ALERTS = DESK / "alerts.jsonl"

TARGET = float(ACCOUNT["profit_target"])
MAX_LOSS = float(ACCOUNT["max_loss"])
EQUITY_START = float(ACCOUNT["start_balance"])
CONSISTENCY = float(ACCOUNT["consistency"]["rule"])
SILENT_DAYS = 21


def e(value) -> str:
    return html.escape(str(value), quote=True)


def read_jsonl(name: str) -> list[dict]:
    path = DESK / name
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def read_json(name: str) -> dict:
    path = DESK / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def age_hours(stamp: str | None) -> float | None:
    if not stamp:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            when = datetime.strptime(stamp[:len(fmt) + 2].replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
        return (datetime.now(timezone.utc).replace(tzinfo=None) - when).total_seconds() / 3600
    return None


# --------------------------------------------------------------------- alerts
def build_alerts(state: dict, ledger: list[dict], orders: list[dict],
                 swarm: dict, monte: dict) -> list[dict]:
    """Only conditions that would change what a person does."""
    out: list[dict] = []

    def add(level: str, what: str, detail: str) -> None:
        out.append({"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "level": level, "what": what, "detail": detail})

    equity = float(state.get("equity", EQUITY_START))
    pnl = equity - EQUITY_START
    if pnl <= -MAX_LOSS * 0.8:
        add("high", "drawdown limit near", f"${pnl:+,.0f} against a ${-MAX_LOSS:,.0f} limit")
    best_day = max([float(r.get("usd", 0)) for r in ledger] + [float(state.get("best_day", 0))] or [0])
    if best_day > TARGET * CONSISTENCY:
        add("high", "consistency rule already broken",
            f"best day ${best_day:,.0f} exceeds ${TARGET * CONSISTENCY:,.0f} — "
            "a pass would be voided")
    if (DESK / "KILL").exists():
        add("high", "kill switch engaged", "no orders will be submitted")
    if not ledger:
        add("info", "no forward trades yet",
            "the forward ledger starts when the desk first runs; this is expected early")
    else:
        last = ledger[-1].get("date", "")
        try:
            days = (datetime.now(timezone.utc) -
                    datetime.strptime(last, "%Y-%m-%d").replace(tzinfo=timezone.utc)).days
            if days > SILENT_DAYS:
                add("medium", "strategy has been silent",
                    f"{days} days since the last signal — check the feed and the roll date")
        except ValueError:
            pass

    if swarm.get("degraded"):
        add("medium", "news swarm degraded",
            f"{swarm.get('feeds_ok', 0)}/{swarm.get('feeds_total', 0)} feeds reachable")
    elif swarm.get("age_min") and swarm["age_min"] > 180:
        add("medium", "news swarm stale",
            f"last read {swarm['age_min']:.0f} min ago")

    filled = [o for o in orders if o.get("state") == "FILLED"]
    if filled:
        add("info", "fills recorded", f"{len(filled)} simulated fill(s) in the order log")
    rejects = [o for o in orders if o.get("state") == "REJECTED"]
    if len(rejects) >= 3:
        add("low", "orders being rejected",
            f"{len(rejects)} rejections — the last said: {rejects[-1].get('note', '')[:100]}")

    if monte.get("p_target") is not None and monte.get("p_target") < 5:
        add("low", "goal is statistically remote",
            f"{monte['p_target']}% of replays reach +${TARGET:,.0f} before "
            f"-${MAX_LOSS:,.0f} at the current trade distribution")
    return out


# ---------------------------------------------------------------------- render
CSS = """
:root{--bg:#0f1216;--card:#171c22;--ink:#e6edf3;--dim:#8b98a5;--line:#242c35;
--green:#3fb950;--red:#f85149;--amber:#d29922;--blue:#58a6ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:20px}
h1{font-size:20px;margin:0 0 4px}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.09em;color:var(--dim);
margin:26px 0 10px;font-weight:600}
.sub{color:var(--dim);font-size:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.k{color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.07em}
.v{font-size:21px;font-weight:600;margin-top:3px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:var(--dim);font-weight:600;font-size:11px;
text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--line);
padding:7px 8px}
td{padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.num{font-variant-numeric:tabular-nums;text-align:right}
.g{color:var(--green)}.r{color:var(--red)}.a{color:var(--amber)}.b{color:var(--blue)}
.pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;
font-weight:600;border:1px solid var(--line)}
.buy{background:rgba(63,185,80,.15);color:var(--green);border-color:rgba(63,185,80,.4)}
.sell{background:rgba(248,81,73,.15);color:var(--red);border-color:rgba(248,81,73,.4)}
.wait{background:rgba(210,153,34,.15);color:var(--amber);border-color:rgba(210,153,34,.4)}
.skip{background:rgba(139,152,165,.12);color:var(--dim)}
.note{color:var(--dim);font-size:12px;margin-top:6px}
.bar{height:6px;border-radius:3px;background:var(--line);overflow:hidden;margin-top:5px}
.bar>span{display:block;height:100%;background:var(--blue)}
ul{margin:6px 0 0;padding-left:18px}li{margin:3px 0}
footer{margin:34px 0 10px;color:var(--dim);font-size:11px;border-top:1px solid var(--line);
padding-top:12px}
"""


def _pill(call: str) -> str:
    cls = {"BUY": "buy", "SELL": "sell", "WAIT": "wait", "SKIP": "skip"}.get(call, "skip")
    return f'<span class="pill {cls}">{e(call)}</span>'


def _sign(value: float) -> str:
    return "g" if value > 0 else "r" if value < 0 else ""


def render(state: dict, ledger: list[dict], shadow: list[dict], decisions: list[dict],
           orders: list[dict], swarm: dict, monte: dict, board: dict, alerts: list[dict]) -> str:
    equity = float(state.get("equity", EQUITY_START))
    pnl = equity - EQUITY_START
    traded = [r for r in ledger if r.get("tradeable")]
    rs = [r.get("net_r", 0) for r in traded]
    wins = sum(1 for r in rs if r > 0)
    win = 100 * wins / len(rs) if rs else 0

    parts: list[str] = [
        "<!doctype html><html lang=en><head><meta charset=utf-8>",
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        'style-src \'unsafe-inline\'; img-src data:">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        "<title>the desk</title>", f"<style>{CSS}</style></head><body><div class=wrap>",
        "<h1>the desk</h1>",
        f"<div class=sub>five December contracts · generated "
        f"{e(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%MZ'))} · "
        "nothing here places an order</div>",
    ]

    # -- top line
    parts += ["<h2>account</h2><div class=grid>"]
    for label, value, cls in (
        ("equity (paper)", f"${equity:,.0f}", _sign(pnl)),
        ("net P&L", f"${pnl:+,.0f}", _sign(pnl)),
        ("forward signals", f"{len(traded)}", ""),
        ("win rate", f"{win:.0f}%" if rs else "—", ""),
        ("open positions", f"{len(state.get('open_positions', []))}", ""),
        ("goal", f"${TARGET:,.0f}", ""),
    ):
        parts.append(f"<div class=card><div class=k>{e(label)}</div>"
                     f"<div class='v {cls}'>{e(value)}</div></div>")
    parts.append("</div>")

    # -- alerts
    parts.append("<h2>alerts</h2>")
    if not alerts:
        parts.append("<div class=note>nothing needs attention</div>")
    else:
        parts.append("<div class=card><ul>")
        for a in alerts[-12:]:
            colour = {"high": "r", "medium": "a", "low": "b"}.get(a["level"], "")
            parts.append(f"<li><span class='{colour}'>{e(a['level'].upper())}</span> "
                         f"<b>{e(a['what'])}</b> — {e(a['detail'])}</li>")
        parts.append("</ul></div>")

    # -- the six bots
    rows = board.get("rows") or []
    parts.append("<h2>the six bots — right now</h2>")
    if not rows:
        parts.append("<div class=note>no board yet — run <code>python3 trading/desk.py --board</code></div>")
    else:
        parts.append("<table><tr><th>market</th><th>bot 1 opportunity</th>"
                     "<th>bot 2 catalyst</th><th>bot 3 sentiment</th>"
                     "<th>bot 5 risk</th><th>call</th></tr>")
        for r in rows:
            if r.get("error"):
                parts.append(f"<tr><td>{e(r['symbol'])}</td><td colspan=5 class=note>"
                             f"{e(r['error'])}</td></tr>")
                continue
            b = r["bots"]
            opp, cat, sent, risk = (b["1_opportunity"], b["2_catalyst"],
                                    b["3_sentiment"], b["5_risk"])
            parts.append(
                f"<tr><td><b>{e(r['symbol'])}</b><div class=sub>{e(r.get('as', ''))}</div></td>"
                f"<td>{e(opp['score'])}/100<div class=sub>{e(opp['setup'])}</div></td>"
                f"<td>{e(cat['verdict'])}<div class=sub>{e(cat['fresh'])} fresh</div></td>"
                f"<td>{e(sent['label'])}<div class=sub>hype {e(sent['hype'])}</div></td>"
                f"<td>{e(risk['action'])}<div class=sub>{e(risk['contracts'])} lot</div></td>"
                f"<td>{_pill(r['call'])}<div class=sub>{e(r['confidence'])}/100</div></td></tr>")
        parts.append("</table>")
        parts.append("<div class=note>The call is a decision, not a fill. BOT 5 can "
                     "reject any trade; BOT 2 can only delay one.</div>")

    # -- levels for the live calls
    plans = [r for r in rows if r.get("bots", {}).get("4_levels", {}).get("ok")]
    if plans:
        parts.append("<h2>levels for the two sized markets</h2><table>"
                     "<tr><th>market</th><th>side</th><th class=num>entry</th>"
                     "<th class=num>stop</th><th class=num>target</th>"
                     "<th class=num>R:R</th><th class=num>risk $</th></tr>")
        for r in plans:
            pl = r["bots"]["4_levels"]
            risk = r["bots"]["5_risk"]
            parts.append(
                f"<tr><td>{e(r['symbol'])}</td><td>{e(pl['side'])}</td>"
                f"<td class=num>{pl['entry']:,.2f}</td><td class=num>{pl['stop']:,.2f}</td>"
                f"<td class=num>{pl['target']:,.2f}</td><td class=num>{pl['rr']:.1f}</td>"
                f"<td class=num>${risk['stop_usd']:,.0f}</td></tr>")
        parts.append("</table>")

    # -- risk dashboard
    parts.append("<h2>risk dashboard</h2><div class=grid>")
    used = max(0.0, min(1.0, abs(min(pnl, 0)) / MAX_LOSS))
    parts.append(f"<div class=card><div class=k>loss budget used</div>"
                 f"<div class=v>{100 * used:.0f}%</div>"
                 f"<div class=bar><span style='width:{100 * used:.0f}%'></span></div>"
                 f"<div class=note>${-MAX_LOSS:,.0f} limit</div></div>")
    cons = max(0.0, min(1.0, (max([float(r.get('usd', 0)) for r in traded] + [0])) /
                       (TARGET * CONSISTENCY)))
    parts.append(f"<div class=card><div class=k>consistency used</div>"
                 f"<div class=v>{100 * cons:.0f}%</div>"
                 f"<div class=bar><span style='width:{100 * cons:.0f}%'></span></div>"
                 f"<div class=note>best day may not exceed ${TARGET * CONSISTENCY:,.0f}</div></div>")
    dd = 0.0
    eq = 0.0
    peak = 0.0
    for r in traded:
        eq += float(r.get("usd", 0))
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    parts.append(f"<div class=card><div class=k>max drawdown</div>"
                 f"<div class=v>${dd:,.0f}</div><div class=note>peak to trough, paper</div></div>")
    if monte:
        parts.append(f"<div class=card><div class=k>10k replays → goal</div>"
                     f"<div class=v>{monte.get('p_target', 0):.0f}%</div>"
                     f"<div class=note>{monte.get('p_breach', 0):.0f}% breach first · "
                     f"{monte.get('paths', 0):,} paths</div></div>")
    parts.append("</div>")

    # -- system health
    parts.append("<h2>system health</h2><div class=grid>")
    for label, value, ok in (
        ("data feed", "reachable" if swarm.get("feeds_ok") else "unknown",
         bool(swarm.get("feeds_ok"))),
        ("news swarm", f"{swarm.get('feeds_ok', 0)}/{swarm.get('feeds_total', 0)} feeds",
         not swarm.get("degraded")),
        ("desk cycles", str(state.get("cycles", 0)), True),
        ("kill switch", "engaged" if (DESK / "KILL").exists() else "clear",
         not (DESK / "KILL").exists()),
        ("orders logged", str(len(orders)), True),
    ):
        colour = "g" if ok else "a"
        parts.append(f"<div class=card><div class=k>{e(label)}</div>"
                     f"<div class='v {colour}' style='font-size:15px'>{e(value)}</div></div>")
    parts.append("</div>")

    # -- forward ledger
    parts.append("<h2>forward record</h2>")
    if not traded:
        parts.append("<div class=note>the forward ledger starts the day the desk first "
                     "ran and is never back-filled. Empty is the honest state of a "
                     "system that just started.</div>")
    else:
        parts.append("<table><tr><th>date</th><th>market</th><th>rule</th><th>side</th>"
                     "<th class=num>entry</th><th class=num>exit</th><th>why</th>"
                     "<th class=num>R</th><th class=num>USD</th></tr>")
        for r in traded[-20:]:
            cls = _sign(float(r.get("net_r", 0)))
            parts.append(
                f"<tr><td>{e(r.get('date'))}</td><td>{e(r.get('symbol'))}</td>"
                f"<td>{e(r.get('rule'))}</td><td>{e(r.get('side'))}</td>"
                f"<td class=num>{float(r.get('entry', 0)):,.2f}</td>"
                f"<td class=num>{float(r.get('exit', 0)):,.2f}</td>"
                f"<td>{e(r.get('exit_reason', ''))}</td>"
                f"<td class='num {cls}'>{float(r.get('net_r', 0)):+.2f}</td>"
                f"<td class='num {cls}'>${float(r.get('usd', 0)):+,.0f}</td></tr>")
        parts.append("</table>")

    # -- committee audit
    if decisions:
        took = [d for d in decisions if d.get("verdict", {}).get("decision") == "TRADE"]
        skip = [d for d in decisions if d.get("verdict", {}).get("decision") == "PASS"]
        parts.append("<h2>did the committee add anything?</h2><table>"
                     "<tr><th></th><th class=num>decisions</th><th class=num>avg outcome R</th>"
                     "<th class=num>USD</th></tr>")
        for group, label in ((took, "chair said TRADE"), (skip, "chair said PASS")):
            if group:
                avg = statistics.mean(float(d.get("outcome_r", 0)) for d in group)
                usd = sum(float(d.get("outcome_usd", 0)) for d in group)
                parts.append(f"<tr><td>{e(label)}</td><td class=num>{len(group)}</td>"
                             f"<td class='num {_sign(avg)}'>{avg:+.2f}</td>"
                             f"<td class='num {_sign(usd)}'>${usd:+,.0f}</td></tr>")
        parts.append("</table>")
        if took and skip:
            a = statistics.mean(float(d.get("outcome_r", 0)) for d in took)
            b = statistics.mean(float(d.get("outcome_r", 0)) for d in skip)
            parts.append("<div class=note>" +
                         ("The chair is separating good signals from bad so far. "
                          "Small samples lie." if a > b else
                          "<b>The chair is not adding value yet</b> — it is rejecting "
                          "trades that did better than the ones it approved.") +
                         "</div>")

    # -- analytics: which rule and which agent actually earn their keep
    ana = read_json("analytics.json")
    if ana.get("by_rule"):
        parts.append("<h2>which rule earns its keep</h2><table><tr><th>rule</th>"
                     "<th class=num>trades</th><th class=num>win</th>"
                     "<th class=num>avg R</th></tr>")
        for rule, s in ana["by_rule"].items():
            parts.append(f"<tr><td>{e(rule)}</td><td class=num>{e(s['n'])}</td>"
                         f"<td class=num>{e(s['win'])}%</td>"
                         f"<td class='num {_sign(s['avg'])}'>{s['avg']:+.2f}</td></tr>")
        parts.append("</table>")
        parts.append(f"<div class=note>{e(ana.get('sample_note', ''))}</div>")
    agents = ana.get("agents") or {}
    if agents:
        parts.append("<h2>which agent is actually right</h2><table><tr><th>agent</th>"
                     "<th class=num>calls</th><th class=num>right</th>"
                     "<th class=num>conclusive</th></tr>")
        for name, s in agents.items():
            parts.append(f"<tr><td>{e(name)}</td><td class=num>{e(s['n'])}</td>"
                         f"<td class=num>{e(s['right_pct'])}%</td>"
                         f"<td class=num>{'yes' if s['conclusive'] else 'not yet'}</td></tr>")
        parts.append("</table>")
    cal = ana.get("calibration") or {}
    if cal.get("note"):
        parts.append(f"<div class=note>{e(cal['note'])}</div>")

    # -- shadow
    if shadow:
        srs = [float(r.get("net_r", 0)) for r in shadow if r.get("tradeable")]
        parts.append("<h2>shadow replay (not forward)</h2>")
        parts.append(f"<div class=note>{len(shadow)} replayed signal(s), "
                     f"{len(srs)} sized. Useful for judging fills and finding bugs — "
                     "it is not evidence, those sessions already happened.</div>")

    parts.append("<footer>paper only · no broker connection · no API key in this repo · "
                 "generated by trading/dashboard.py from files in trading/desk/</footer>")
    parts.append("</div></body></html>")
    return "".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", dest="show", action="store_true")
    args = ap.parse_args()

    state = read_json("state.json")
    ledger = read_jsonl("ledger.jsonl")
    shadow = read_jsonl("shadow.jsonl")
    decisions = read_jsonl("decisions.jsonl") + read_jsonl("shadow_decisions.jsonl")
    orders = read_jsonl("orders.jsonl")
    swarm = read_json("swarm.json")
    monte = read_json("montecarlo.json")
    board = read_json("board.json")

    if swarm.get("last"):
        swarm["age_min"] = age_hours(swarm["last"]) * 60 if age_hours(swarm["last"]) else None
    alerts = build_alerts(state, ledger, orders, swarm, monte)

    DESK.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(state, ledger, shadow, decisions, orders, swarm, monte, board, alerts))

    # Alerts are append-only, and only new ones are written, so the file is a
    # history rather than a snapshot that overwrites the interesting part.
    prior = {(a.get("what"), a.get("detail")) for a in read_jsonl("alerts.jsonl")}
    fresh = [a for a in alerts if (a["what"], a["detail"]) not in prior]
    if fresh:
        with ALERTS.open("a") as fh:
            for a in fresh:
                fh.write(json.dumps(a) + "\n")

    print(f"  dashboard written to {OUT}  ({len(alerts)} active alert(s))")
    if args.show:
        for a in alerts:
            print(f"    {a['level'].upper():<7}{a['what']}: {a['detail']}")


if __name__ == "__main__":
    main()
