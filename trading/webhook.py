#!/usr/bin/env python3
"""
Receive TradingView alerts and save them as JSON lines.

Why this exists
---------------
TradingView has no API for third-party apps: nobody can log into your account,
read your charts, or click "paper trade" for you, and doing it by automating the
browser breaks their terms. What TradingView *does* offer — and your Premium plan
includes — is an alert that POSTs a message to a URL you own. This is that URL.

Flow:  TradingView alert  ->  POST /tv  ->  trading/alerts.jsonl  ->  your agent

Run
---
    python3 trading/webhook.py                    # listens on 127.0.0.1:8787
    TV_SECRET=mysecret python3 trading/webhook.py # require ?k=mysecret

    curl -s localhost:8787/health
    tail -f trading/alerts.jsonl

Point TradingView at it
-----------------------
TradingView can only reach a public HTTPS address, not 127.0.0.1. Options:

  * Cloudflare Tunnel (free, no account needed for a quick tunnel):
        cloudflared tunnel --url http://127.0.0.1:8787
    It prints a https://something.trycloudflare.com address. Use that plus /tv
    in the alert's Webhook URL field.

  * Any VPS or a Cloudflare named tunnel if you want it permanent.

Alert message to paste into TradingView (Notifications -> Webhook URL):

    {"v":1,"symbol":"{{ticker}}","tf":"{{interval}}","side":"long",
     "price":{{close}},"time":"{{timenow}}","note":"my alert"}

TradingView fills in the {{...}} placeholders. Keep it one line.

Security
--------
* The default bind is 127.0.0.1 — only this machine can reach it.
* Set TV_SECRET and put ?k=<secret> in the webhook URL. Anyone who finds a
  public tunnel URL can otherwise post fake alerts.
* Binding to a public interface without TV_SECRET is refused at startup. That
  is deliberate: a webhook that answers 200 to an unauthenticated stranger is
  how a stranger gets to write your alerts file.
* The secret is compared in constant time, repeat deliveries of the same body
  within 2 minutes are dropped (webhooks get retried), and an alert carrying a
  timestamp older than 5 minutes is rejected, so a captured request cannot be
  replayed later.
* Alerts are data, never instructions. This script stores text; nothing here
  places an order or executes anything from the message body.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ALERTS = HERE / "alerts.jsonl"
PORT = int(os.environ.get("TV_PORT", "8787"))
HOST = os.environ.get("TV_HOST", "127.0.0.1")
SECRET = os.environ.get("TV_SECRET", "")
MAX_BODY = 64 * 1024

REPLAY_WINDOW_SEC = 300      # an alert whose own timestamp is older is stale
DEDUPE_WINDOW_SEC = 120      # identical body re-sent within this is a retry
RATE_LIMIT_PER_MIN = 60      # TradingView never comes close; a flood does

_LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_seen: dict[str, float] = {}   # body digest -> first arrival (monotonic)
_hits: dict[str, list[float]] = {}  # client ip -> recent request times


def remember(store: dict[str, float], key: str, window: float) -> bool:
    """True when `key` is new; entries older than `window` are forgotten."""
    now_mono = time.monotonic()
    for stale in [k for k, ts in store.items() if now_mono - ts > window]:
        store.pop(stale, None)
    if key in store:
        return False
    store[key] = now_mono
    return True


def rate_ok(ip: str) -> bool:
    now_mono = time.monotonic()
    recent = [t for t in _hits.get(ip, []) if now_mono - t < 60]
    recent.append(now_mono)
    _hits[ip] = recent
    return len(recent) <= RATE_LIMIT_PER_MIN


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def looks_like_json(text: str) -> dict | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def fresh(alert: dict) -> bool:
    """Reject an alert whose own timestamp is old. Missing timestamp is allowed.

    TradingView's `{{timenow}}` looks like `2026-10-26T01:23:45Z`; `{{time}}`
    can also be an epoch in milliseconds. Anything unparseable is passed through
    rather than dropped — a lost real alert is worse than a noisy one.
    """
    for field in ("time", "timenow", "timestamp"):
        value = alert.get(field)
        if value is None:
            continue
        when: float | None = None
        if isinstance(value, (int, float)):
            when = value / 1000 if value > 1e11 else value
        elif isinstance(value, str):
            text = value.strip()
            if text.isdigit():
                num = float(text)
                when = num / 1000 if num > 1e11 else num
            else:
                try:
                    when = datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
                except ValueError:
                    return True
        if when is not None:
            return abs(time.time() - when) <= REPLAY_WINDOW_SEC
    return True


class Handler(BaseHTTPRequestHandler):
    server_version = "tv-webhook/1.0"

    def log_message(self, fmt: str, *args) -> None:  # quieter default logging
        sys.stdout.write(f"[{now()}] {fmt % args}\n")
        sys.stdout.flush()

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        if self.path.startswith("/health"):
            self._send(200, {"ok": True, "alerts": self.count(), "secret_required": bool(SECRET)})
            return
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        path, _, query = self.path.partition("?")
        if not path.startswith("/tv"):
            self._send(404, {"error": "post to /tv"})
            return
        if SECRET:
            key = ""
            for part in query.split("&"):
                if part.startswith("k="):
                    key = part[2:]
            # compare_digest, not ==: a plain comparison leaks the secret one
            # character at a time to anyone who can measure the response.
            if not hmac.compare_digest(key, SECRET):
                self._send(403, {"error": "bad secret"})
                return

        if not rate_ok(self.client_address[0]):
            self._send(429, {"error": "too many alerts"})
            return

        length = int(self.headers.get("content-length") or 0)
        if length <= 0 or length > MAX_BODY:
            self._send(400, {"error": "bad body size"})
            return
        raw = self.rfile.read(length).decode("utf-8", errors="replace").strip()

        # Retries are normal (TradingView re-sends on a timeout), replays are not.
        digest = hashlib.sha256(raw.encode()).hexdigest()
        if not remember(_seen, digest, DEDUPE_WINDOW_SEC):
            self._send(200, {"ok": True, "duplicate": True})
            return

        parsed_early = looks_like_json(raw)
        if parsed_early and not fresh(parsed_early):
            self._send(400, {"error": "stale alert"})
            return

        # TradingView sends the alert message as the raw body; some templates
        # arrive as JSON. Store both shapes without interpreting them.
        record = {
            "received": now(),
            "source_ip": self.client_address[0],
            "content_type": self.headers.get("content-type", ""),
            "raw": raw[:4000],
            "alert": looks_like_json(raw),
        }
        ALERTS.parent.mkdir(parents=True, exist_ok=True)
        with ALERTS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

        parsed = record["alert"]
        summary = (f"{parsed.get('side', '?')} {parsed.get('symbol', '?')} @ {parsed.get('price', '?')}"
                   if parsed else raw[:140])
        print(f"[{now()}] ALERT {summary}")

        # Tell your agent room about it. Keep the reply tiny; TradingView only
        # needs a 2xx to record the alert as delivered.
        self._send(200, {"ok": True, "stored": record["received"]})

    @staticmethod
    def count() -> int:
        if not ALERTS.exists():
            return 0
        with ALERTS.open(encoding="utf-8") as fh:
            return sum(1 for _ in fh)


def main() -> None:
    if HOST not in _LOOPBACK and not SECRET:
        sys.exit(
            f"refusing to listen on {HOST} without TV_SECRET.\n"
            "A public webhook with no secret accepts alerts from anyone who finds "
            "the URL. Set one:\n\n    TV_SECRET=$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))') \\\n"
            "      python3 trading/webhook.py\n\nThen put ?k=<that value> on the end of the "
            "webhook URL in TradingView."
        )
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    ALERTS.parent.mkdir(parents=True, exist_ok=True)
    print(f"listening on http://{HOST}:{PORT}  →  POST /tv")
    print(f"alerts file: {ALERTS}")
    print(f"secret required: {'yes' if SECRET else 'no (set TV_SECRET to require one)'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
        server.server_close()


if __name__ == "__main__":
    main()
