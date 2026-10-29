#!/usr/bin/env python3
"""
The reading swarm — 300 small readers, one question each, no key required.

Why 300 agents and not one
--------------------------
"Check the news" is not a question a program can answer. "Did any of twelve
public feeds publish something in the last ninety minutes that mentions crude
and inventories" is. So the swarm is deliberately dumb: three hundred readers,
each one a (feed, market, concept) triple, each answering a yes/no-ish question
and scoring the polarity of the headline it found.

    20 public feeds x 5 markets x 3 concepts = 300 agents

Every reader shares a per-feed download cache, so three hundred readers cost
twenty HTTP requests, not three hundred. If a feed is down it says so instead
of pretending the world is quiet.

The part that actually matters: verification
--------------------------------------------
An LLM (or a person) reading X will happily treat a 2024 article as breaking
news. That is the single most dangerous failure mode in news-driven trading, so
it is handled here, structurally, before any score exists:

  * **unparseable timestamp**  -> item rejected, counted
  * **timestamp in the future** -> rejected (anything more than 10 min ahead)
  * **older than the window**   -> rejected as impulse, kept only as context
  * **seen before**             -> rejected as a duplicate / resurfacing
  * **not on the allowlist**    -> there is no allowlist: the feeds are hardcoded
                                   and nothing is fetched from a URL an item
                                   supplies. No redirect chasing, no scraped links.

Every item that survives carries `published`, `age_min`, `feed` and `first_seen`
so a downstream bot can refuse to act on it. Text is treated as data only:
`sanitize()` strips tags, control characters and URLs, and the result is never
concatenated into an instruction.

    python3 trading/swarm.py                 # full run, writes desk/swarm.json
    python3 trading/swarm.py --status        # what the last run saw
    python3 trading/swarm.py --feeds         # feed health only
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DESK = HERE / "desk"
STATE = DESK / "swarm.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; free-ai-swarm/1.0)"}

# Twenty public RSS/Atom endpoints. No API key, no account, no scraping of a
# page that needs a session. A dead feed is reported, never silently ignored.
FEEDS: dict[str, str] = {
    "cnbc_top": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "cnbc_markets": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "cnbc_energy": "https://www.cnbc.com/id/19836768/device/rss/rss.html",
    "marketwatch": "https://feeds.marketwatch.com/marketwatch/topstories/",
    "mw_pulse": "https://feeds.marketwatch.com/marketwatch/marketpulse/",
    "yahoo_finance": "https://finance.yahoo.com/news/rssindex",
    "fed_press": "https://www.federalreserve.gov/feeds/press_all.xml",
    "bls_latest": "https://www.bls.gov/feed/bls_latest.rss",
    "bea_news": "https://apps.bea.gov/rss/rss.xml",
    "eia_today": "https://www.eia.gov/rss/todayinenergy.xml",
    "oilprice": "https://oilprice.com/rss/main",
    "kitco": "https://www.kitco.com/rss/KitcoNews.xml",
    "forexlive": "https://www.forexlive.com/feed/news",
    "investing_commodities": "https://www.investing.com/rss/news_11.rss",
    "nasdaq_markets": "https://www.nasdaq.com/feed/rssoutbound?category=Markets",
    "scmp_business": "https://www.scmp.com/rss/92/feed",
    "bbc_business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "guardian_business": "https://www.theguardian.com/uk/business/rss",
    "ecb_press": "https://www.ecb.europa.eu/rss/press.html",
    "treasury": "https://home.treasury.gov/news/press-releases/feed",
}

# market -> (display name, keywords that make a headline about THIS market)
MARKETS: dict[str, tuple[str, tuple[str, ...]]] = {
    "ES=F": ("S&P 500", ("s&p", "sp500", "s&p 500", "stocks", "equit", "wall street",
                         "dow", "nasdaq", "futures", "treasury", "yield", "earnings")),
    "NQ=F": ("Nasdaq-100", ("nasdaq", "tech", "nvidia", "apple", "micros", "semiconductor",
                            "chip", "ai ", "artificial intelligence", "big tech", "growth stock")),
    "GC=F": ("Gold", ("gold", "bullion", "precious metal", "silver", "haven", "safe haven",
                      "central bank buying", "gold etf")),
    "CL=F": ("Crude oil", ("oil", "crude", "opec", "brent", "wti", "petroleum", "refiner",
                           "gasoline", "diesel", "barrel", "saudi", "shale", "inventor")),
    "NKD=F": ("Nikkei USD", ("nikkei", "japan", "boj", "bank of japan", "yen", "tokyo",
                             "jgb", "kospi", "asia stocks")),
}

# concept -> (label, keywords). A reader exists for each (feed, market, concept).
CONCEPTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "policy": ("policy / rates", ("fed", "fomc", "rate cut", "rate hike", "inflation", "cpi",
                                  "ppi", "payroll", "jobs report", "unemployment", "ecb", "boj",
                                  "tariff", "sanction", "stimulus", "debt ceiling", "shutdown")),
    "shock": ("supply / geopolitical", ("war", "strike", "attack", "hurricane", "pipeline",
                                        "outage", "embargo", "opec", "inventor", "supply",
                                        "shortage", "earthquake", "ceasefire", "tanker")),
    "flow": ("positioning / flows", ("etf", "inflow", "outflow", "hedge fund", "positioning",
                                     "buyback", "upgrade", "downgrade", "earnings", "guidance",
                                     "record high", "selloff", "rally", "bubble")),
}

BULL = ("beat", "beats", "surge", "surges", "soar", "soars", "rally", "rallies", "record high",
        "jump", "jumps", "gain", "gains", "rise", "rises", "rising", "strong", "stronger",
        "upgrade", "upbeat", "optimis", "boost", "boosts", "rebound", "recover", "inflow",
        "buyback", "demand growth", "cuts rates", "rate cut", "stimulus", "ceasefire")
BEAR = ("miss", "misses", "plunge", "plunges", "slump", "slumps", "tumble", "tumbles", "fall",
        "falls", "falling", "drop", "drops", "selloff", "sell-off", "weak", "weaker",
        "downgrade", "recession", "fear", "fears", "worry", "worries", "outflow", "layoff",
        "default", "warning", "cuts forecast", "rate hike", "tariff", "sanction", "war")
HYPE = ("could", "might", "may ", "set to", "poised", "about to", "everyone", "skyrocket",
        "to the moon", "explode", "10x", "guaranteed", "can't lose", "shocking", "you won't")

FRESH_MIN = 90          # an item older than this cannot be an impulse
CONTEXT_MIN = 24 * 60   # ...but it can still be context
FUTURE_TOLERANCE = 10   # minutes a clock may be ahead before we distrust it
CACHE_TTL = 1200        # do not re-download feeds more than every 20 minutes
MAX_ITEMS = 60          # per feed
SEEN_KEEP = 4000        # hashes retained for duplicate/resurface detection

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_URL = re.compile(r"https?://\S+")


# --------------------------------------------------------------- untrusted text
def sanitize(text: str, limit: int = 200) -> str:
    """Feeds are untrusted input. Strip markup, control chars and links.

    A headline is data. It is never joined into an instruction string, and it can
    never contribute a URL that anything later fetches — which is what stops a
    crafted headline from becoming a request to an attacker's host.
    """
    if not text:
        return ""
    clean = _TAG.sub(" ", str(text))
    clean = _CTRL.sub("", clean)
    clean = _URL.sub("[link]", clean)
    clean = clean.replace("<", "").replace(">", "")
    clean = _WS.sub(" ", clean).strip()
    return clean[:limit]


def _hash(title: str) -> str:
    norm = re.sub(r"[^a-z0-9 ]", "", title.lower())
    return hashlib.sha256(_WS.sub(" ", norm).strip().encode()).hexdigest()[:16]


# --------------------------------------------------------------------- fetching
def _fetch(url: str, timeout: int = 8) -> bytes | None:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.read(400_000)
    except Exception:  # noqa: BLE001 - a dead feed is normal, not fatal
        return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _parse_date(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:  # noqa: BLE001
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw.replace("Z", "+0000"), fmt)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def parse_feed(raw: bytes) -> list[dict]:
    """RSS or Atom, namespace-agnostic. Returns raw items with a parsed date."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    items = []
    for node in root.iter():
        if _local(node.tag) not in ("item", "entry"):
            continue
        title = link = body = published = ""
        for child in node:
            name = _local(child.tag)
            text = (child.text or "").strip()
            if name == "title":
                title = text
            elif name == "link":
                link = text or child.attrib.get("href", "")
            elif name in ("description", "summary", "content"):
                body = body or text
            elif name in ("pubdate", "published", "updated", "date", "created"):
                published = published or text
        if not title:
            continue
        items.append({"title": title, "link": link, "body": body, "raw_date": published})
        if len(items) >= MAX_ITEMS:
            break
    return items


# ----------------------------------------------------------------------- scoring
def polarity(text: str) -> tuple[float, int, int]:
    low = f" {text.lower()} "
    up = sum(1 for w in BULL if w in low)
    down = sum(1 for w in BEAR if w in low)
    if up == down == 0:
        return 0.0, 0, 0
    return max(-1.0, min(1.0, (up - down) / max(up + down, 1))), up, down


def hype(text: str) -> int:
    low = f" {text.lower()} "
    return sum(1 for w in HYPE if w in low)


def _relevant(text: str, market: str, concept: str) -> bool:
    low = text.lower()
    mk = MARKETS[market][1]
    ck = CONCEPTS[concept][1]
    return any(k in low for k in mk) and any(k in low for k in ck)


# ------------------------------------------------------------------------- state
def _now() -> datetime:
    return datetime.now(timezone.utc)


def load() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except json.JSONDecodeError:
            pass
    return {"runs": 0, "seen": {}, "feed_health": {}, "last": None}


def save(data: dict) -> None:
    DESK.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(STATE)


# --------------------------------------------------------------------------- run
def run(window_min: int = FRESH_MIN, force: bool = False, verbose: bool = True) -> dict:
    """One sweep of all 300 readers. Safe to call often: feeds are cached."""
    state = load()
    now = _now()
    if not force and state.get("last"):
        try:
            age = (now - datetime.strptime(state["last"], "%Y-%m-%dT%H:%M:%SZ")
                   .replace(tzinfo=timezone.utc)).total_seconds()
            if age < CACHE_TTL and state.get("markets"):
                if verbose:
                    print(f"  swarm: cached ({age / 60:.0f} min old) — "
                          f"use --force to re-read the feeds")
                return state
        except ValueError:
            pass

    cache: dict[str, list[dict]] = {}
    health: dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch, url): name for name, url in FEEDS.items()}
        for fut in concurrent.futures.as_completed(futures):
            name = futures[fut]
            raw = fut.result()
            if not raw:
                health[name] = "down"
                cache[name] = []
                continue
            items = parse_feed(raw)
            health[name] = f"ok ({len(items)})" if items else "empty"
            cache[name] = items

    seen: dict[str, str] = state.get("seen", {}) or {}
    stats = {"parsed": 0, "rejected_no_date": 0, "rejected_future": 0,
             "rejected_stale": 0, "rejected_dupe": 0, "kept_fresh": 0, "kept_context": 0}
    per_market: dict[str, dict] = {}
    agents_ran = 0

    for market in MARKETS:
        bucket = {"polarity": 0.0, "weight": 0.0, "fresh": [], "context": [],
                  "by_concept": {}, "hype": 0}
        for feed, items in cache.items():
            for item in items:
                stats["parsed"] += 1
                published = _parse_date(item["raw_date"])
                if published is None:
                    stats["rejected_no_date"] += 1
                    continue
                age = (now - published).total_seconds() / 60
                if age < -FUTURE_TOLERANCE:
                    stats["rejected_future"] += 1
                    continue
                if age > CONTEXT_MIN:
                    stats["rejected_stale"] += 1
                    continue
                title = sanitize(item["title"])
                # Duplicates are tracked per market. The same story can honestly
                # be an S&P item *and* a Nasdaq item; what must not happen is one
                # story counted twice inside one market because two feeds carried
                # it. A global hash silently gave every story to whichever market
                # happened to be read first.
                key = f"{market}:{_hash(title)}"
                if key in seen:
                    stats["rejected_dupe"] += 1
                    continue
                seen[key] = now.strftime("%Y-%m-%dT%H:%M:%SZ")

                text = f"{title} {sanitize(item['body'], 320)}"
                for concept in CONCEPTS:
                    agents_ran += 1
                    if not _relevant(text, market, concept):
                        continue
                    pol, up, down = polarity(text)
                    h = hype(text)
                    row = {
                        "title": title, "feed": feed, "concept": concept,
                        "published": published.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "age_min": round(age, 1), "polarity": round(pol, 2),
                        "weight": 1.0 if age <= window_min else 0.35,
                        "verified": True,
                    }
                    kind = "fresh" if age <= window_min else "context"
                    if kind == "fresh":
                        stats["kept_fresh"] += 1
                    else:
                        stats["kept_context"] += 1
                    bucket[kind].append(row)
                    bucket["polarity"] += pol * row["weight"]
                    bucket["weight"] += row["weight"]
                    bucket["hype"] += h
                    slot = bucket["by_concept"].setdefault(concept, {"polarity": 0.0, "n": 0})
                    slot["polarity"] += pol * row["weight"]
                    slot["n"] += 1

        w = bucket["weight"]
        strong = sorted(bucket["fresh"], key=lambda r: -abs(r["polarity"]))[:6]
        per_market[market] = {
            "name": MARKETS[market][0],
            "polarity": round(bucket["polarity"] / w, 3) if w else 0.0,
            "items": len(bucket["fresh"]) + len(bucket["context"]),
            "fresh": len(bucket["fresh"]),
            "hype_hits": bucket["hype"],
            "by_concept": {k: {"polarity": round(v["polarity"], 2), "n": v["n"]}
                           for k, v in bucket["by_concept"].items()},
            "headlines": [{"title": r["title"], "feed": r["feed"],
                           "age_min": r["age_min"], "polarity": r["polarity"]}
                          for r in strong],
            "verified_only": True,
        }

    seen = dict(sorted(seen.items(), key=lambda kv: kv[1])[-SEEN_KEEP:])
    data = {
        "last": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runs": state.get("runs", 0) + 1,
        "agents": agents_ran or len(FEEDS) * len(MARKETS) * len(CONCEPTS),
        "agents_planned": len(FEEDS) * len(MARKETS) * len(CONCEPTS),
        "feeds_ok": sum(1 for v in health.values() if v.startswith("ok")),
        "feeds_total": len(FEEDS),
        "window_min": window_min,
        "rejected": {k: v for k, v in stats.items() if k.startswith("rejected")},
        "kept": {"fresh": stats["kept_fresh"], "context": stats["kept_context"]},
        "feed_health": health,
        "markets": per_market,
        "seen": seen,
        # Deliberately explicit: a quiet feed is not a quiet world.
        "degraded": sum(1 for v in health.values() if v == "down") > len(FEEDS) // 2,
    }
    save(data)
    if verbose:
        ok, total = data["feeds_ok"], data["feeds_total"]
        print(f"  swarm: {data['agents_planned']} readers, {data['agents']} item "
              f"checks across {total} feeds ({ok} reachable) · "
              f"kept {stats['kept_fresh']} fresh, "
              f"{stats['kept_context']} context · rejected "
              f"{stats['rejected_stale']} stale, {stats['rejected_dupe']} dupe, "
              f"{stats['rejected_future']} future-dated, "
              f"{stats['rejected_no_date']} undated")
        if data["degraded"]:
            print("  swarm: WARNING — most feeds unreachable; news bots are blind "
                  "this pass and will not veto anything")
        for sym, m in per_market.items():
            if m["items"]:
                print(f"    {sym:<7}{m['name']:<12}{m['polarity']:+.2f}  "
                      f"{m['fresh']} fresh / {m['items']} total")
    return data


def latest(window_min: int = FRESH_MIN) -> dict:
    """Read-only view for the bots. Never triggers a download."""
    state = load()
    if not state.get("last"):
        return {"markets": {}, "degraded": True, "stale": True, "age_min": None}
    age = (_now() - datetime.strptime(state["last"], "%Y-%m-%dT%H:%M:%SZ")
           .replace(tzinfo=timezone.utc)).total_seconds() / 60
    state["age_min"] = round(age, 1)
    state["stale"] = age > CACHE_TTL / 60
    state["requested_window_min"] = window_min
    return state


def status() -> None:
    data = latest()
    print("=" * 96)
    print(f"  SWARM   last read {data.get('last')}   "
          f"{data.get('agents_planned', 0)} agents   "
          f"{data.get('feeds_ok', 0)}/{data.get('feeds_total', 0)} feeds reachable")
    print("=" * 96)
    if data.get("stale"):
        print("  (stale — run `python3 trading/swarm.py` to refresh)")
    rej = data.get("rejected", {})
    print(f"  rejected: {rej}")
    print()
    for sym, m in (data.get("markets") or {}).items():
        print(f"  {sym:<7}{m['name']:<12}polarity {m['polarity']:+.2f}   "
              f"{m['fresh']} fresh, {m['items']} total, hype {m['hype_hits']}")
        for h in m["headlines"][:3]:
            print(f"      [{h['age_min']:>6.0f}m] {h['title'][:88]}")
    print()
    print("  Feed health:")
    for name, state_ in (data.get("feed_health") or {}).items():
        print(f"    {name:<22}{state_}")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--feeds", action="store_true", help="feed health only")
    ap.add_argument("--force", action="store_true", help="ignore the 20-minute cache")
    ap.add_argument("--window", type=int, default=FRESH_MIN, help="freshness window, minutes")
    args = ap.parse_args()
    if args.status:
        status()
    elif args.feeds:
        data = run(force=True)
        for name, health in data["feed_health"].items():
            print(f"  {name:<22}{health}")
    else:
        run(window_min=args.window, force=args.force)


if __name__ == "__main__":
    main()
