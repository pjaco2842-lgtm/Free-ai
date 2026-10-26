# Security audit — FreeLLMAPI dashboard + agent

**Date:** 2026-10-26
**Scope:** the app in this folder (`client/`, `server/`, `shared/`, `cli/`) plus the
agent setup (`agent/`, `setup-cc-free.sh`, skills).
**Method:** read the code, grepped for the classic failure patterns, checked git
history, and ran a live dependency audit. Findings below quote the file and line so
you can verify each one yourself.

**What this audit is not:** I did not run the app, log in through a browser, or see
your deployed host, DNS, or TLS setup. Anything that only exists at runtime or on
your server is listed under "Not checked" at the bottom — don't read this as "the
running site was pen-tested".

---

## The short version

Of the 18 things on your list, **14 were already done properly**, **3 had real
gaps**, and **1 was a design decision worth knowing about**.

| # | What you asked | Status | Evidence |
|---|---|---|---|
1 | Hide API keys | Done | Provider keys are AES-256-GCM encrypted at rest (`server/src/lib/crypto.ts:7`); never returned in list responses, only via a rate-limited export |
2 | Check environment variables | Done | `.env` is gitignored (`.gitignore:14`), `.env.example` ships with empty values, `ENCRYPTION_KEY` is required in production (`crypto.ts:51`) |
3 | Protect admin routes | Done | All 20+ `/api` routers mount behind `requireAuth` (`server/src/app.ts:254-284`) |
4 | Add proper authentication | Done | Sessions are 32-byte random tokens, **only the SHA-256 hash is stored**, 30-day TTL, expired sessions deleted on use (`server/src/services/auth.ts:71-95`) |
5 | Users only access their own data | Done | Single-owner model: every `/api` route resolves the session user; `/v1` uses a separate API-key scheme (`routes/proxy.ts:73`) |
6 | Sanitize forms | Done | zod schemas on 21 route files; dynamic SQL only ever interpolates whitelisted column names (`routes/profiles.ts:400` uses `Object.hasOwn` on a fixed presets map) |
7 | Protect against XSS | Done | React escaping everywhere; the one `dangerouslySetInnerHTML` is highlight.js output, which escapes (`client/src/lib/highlight.ts:64`); CSP blocks inline script except one hashed bootstrap (`app.ts:62`) |
8 | Rate limiting | Done | Per-IP proxy limiter, per-route admin limiter, plus a per-email login lockout (`routes/auth.ts:48-91`) |
9 | Secure API endpoints | **Gap — fixed** | Endpoint auth was fine, but `proxy-addr` (the module that resolves your client IP) had a critical IP-spoofing CVE, which makes every IP-based rate limit forgeable. Patched — see below |
10 | Check CORS | Done | Explicit allowlist of localhost + `DASHBOARD_ORIGINS`, no wildcard (`app.ts:190`) |
11 | Security headers | Done | Helmet with CSP, COOP, Origin-Agent-Cluster; HSTS intentionally off for HTTP installs (`app.ts:138`) |
12 | Turn off debug mode | Done | 5xx message bodies are replaced in production; only `err.message` reaches the log (`middleware/errorHandler.ts:10-43`) |
13 | Update dependencies | **Gap — fixed** | 20 runtime CVEs → 1. Numbers below |
14 | Remove what you don't need | **Gap — fixed** | 47 unneeded packages dropped by the dependency fix; no features removed |
15 | Check for exposed files | Done | No source maps in the production build, `.env`/`*.db`/`.encryption-key` all ignored, Docker publishes to `127.0.0.1` only (`docker-compose.yml:25`) |
16 | Secure the database | Done | SQLite file and key file forced to `0600`, directories `0700` (`lib/file-permissions.ts:137`) |
17 | Hash passwords properly | Done | scrypt with per-password salt and `timingSafeEqual` comparison, no bcrypt/MD5 anywhere (`lib/password.ts:8-26`) |
18 | Check git history for leaks | Done | 15 commits total, none ever contained a `.env`, key, DB, or credential file |

---

## The three real gaps

### 1. Dependency CVEs — 20 runtime vulnerabilities, now 1

Measured with `npm audit`, before and after `npm audit fix --package-lock-only`
(a lockfile-only update; no `package.json` range was widened and nothing was forced
to a new major version):

| | Before | After |
|---|---|---|
Production dependencies | **20** — 1 critical, 14 high, 5 moderate | **1** — 1 high, 0 critical |
All dependencies (incl. dev) | 27 — 5 critical, 15 high, 7 moderate | 5 — 2 critical, 1 high, 2 moderate |

92 packages were updated inside their existing semver ranges, 47 duplicates removed,
8 added. The important one:

- **`proxy-addr` 2.0.7 → 2.0.8** (critical, CVSS 9.x): IPv4-mapped IPv6 addresses
  could satisfy a trusted subnet check. Your rate limiters, login lockout, and
  audit log all key off the client IP that this module computes — a spoofable IP
  means an attacker could look like a different client on every request and walk
  around the 429s. Now patched.

Also fixed: `body-parser` (DoS), `compression` (DoS, direct dep), `multer` (DoS on
multipart field names), `sharp`/libheif (image parsing — relevant because you accept
uploaded images), `qs`, `js-yaml`, `fast-uri`, `ip-address`, `source-map-js`,
`postcss-selector-parser`, `hono`, `glob`, `browserslist`, `@modelcontextprotocol/sdk`,
`brace-expansion`, `baseline-browser-mapping`, `shell-quote`, `vite`.

**Two are left on purpose**, because fixing them means a breaking major version:

- `zod` 3.25 → 4.6.7 (high, memory exhaustion on oversized collections). This one
  touches request validation across 21 route files — it's a planned upgrade, not a
  `--force` at 2am.
- `vitest` / `tinypool` / `@vitest/coverage-v8` (2 critical, 2 moderate) — **test
  tooling only**, not shipped, not reachable by an attacker. Fixing means vitest 4 → 5.

Run `npm audit` yourself any time; when you're ready for the zod 4 upgrade, do it as
its own task so the test suite can catch the fallout.

### 2. `HOST` binds to every interface by default

`server/src/lib/config.ts:84` — `host: process.env.HOST ?? '::'`.

`::` means *any* address, IPv4 included. So by default the dashboard is reachable
from every device on your Wi-Fi, not just your machine. It's deliberate upstream
(there's a comment about IPv6 Docker networks), and auth still stands in front of
it — but the machine holding all your provider keys is listening on the café Wi-Fi.

The fix, when you don't need phone/LAN access:

```bash
# in your .env
HOST=127.0.0.1
```

I did not change this for you, because if you *do* open the dashboard from your
phone, it would silently stop working. `docker-compose.yml` already defaults to
loopback; this only affects running the server directly.

### 3. The `/api/setup` window

First-run account creation is open on loopback, and requires a setup code from
anywhere else (`routes/auth.ts:221`, `lib/setup-code.ts`). That's correct — but it
means: **whoever loads the dashboard first owns it.** If you ever expose this on a
network before creating your account, or reset it back to zero users, create the
account immediately.

---

## Also worth doing, in priority order

1. **Delete the provider keys you aren't using.** Every key in this app is a live
   credential that the server will happily spend on a request. Fewer keys, smaller
   blast radius.
2. **Re-install on the machine that serves it** (`npm ci`) so the patched versions
   are actually on disk. I did verify here: `npm run build -w server` exits clean and
   the full server suite passes — **372/372 test files, 4599 tests** — on the updated
   lockfile. The browser client was not rebuilt.
3. **Put a strong dashboard password on it.** The lockout is per-email and slows
   guessing; it does not save you from `password123`.
4. **Rotate `ENCRYPTION_KEY` only via the provided script** —
   `npm run db:migration:*` and `server/src/scripts/rotate-encryption-key.ts` exist
   for exactly that. Rotating it by hand makes every stored provider key unreadable.

---

## Skills — your question, answered

You don't need to download skills. A skill is just a folder with a `SKILL.md` in it,
which is a file you write. `skills/nq-desk/SKILL.md` in this repo is one I wrote for
your desk: it declares exactly which commands the agent may run, which files it may
read and write, and what it must never do (live orders, credentials).

**Install it:**

```bash
mkdir -p ~/.claude/skills
ln -s ~/Free-ai/skills/nq-desk ~/.claude/skills/nq-desk
```

**Safety test re-run:**

| Target | Score | Verdict |
|---|---|---|
`skills/nq-desk` (mine) | 0 | **CLEAN** — no findings, declared tool scope, no scripts |
`ponytail` | 100 | 1 critical, 41 high, 66 medium — all false positives on review (an API call in its own benchmark code, the word "keychain" in config docs) |
`addyosmani/agent-skills` | 100 | 183 findings, overwhelmingly "this skill reads your `.claude/` folder", which is what a skill does |
`day-trader-skill` | 100 | 34 findings: `curl` in its news fetchers, prompt-injection matches in fixtures that *discuss* prompts |

None of the three contain malware on inspection, so there is nothing to "make safe"
in them — but none of them declare what they're allowed to touch either, which is
why the scanner can't tell the difference between a skill that reads your config
because it must and one that exfiltrates it. **That's the real difference between
your own skill and a downloaded one: yours says what it can do.**

If you stop using a pack, move it out of `~/.claude/plugins/marketplaces/<name>`
rather than leaving it installed "just in case". Every installed skill widens what
the agent can reach.

---

## Not checked (be honest about the edges)

- Your **live deployment**: TLS, DNS, reverse proxy, firewall, and whether the port
  is actually exposed. Those live on your host, not in this repo.
- The **real values** in your `.env` — I never read that file.
- **Runtime behaviour**: no live login flow and no browser session. The server was
  built and its full test suite run (372 files, 4599 tests, all passing) against the
  updated dependencies; the client bundle was not rebuilt.
- **Third-party providers** you point at: their security is theirs, not this app's.
- Your **other repositories** — the "check git history" result covers this repo.
  For any other repo, the one-line check is:
  `git log --all --name-only --pretty=format: | sort -u | grep -iE '\.env|secret|\.pem|\.key|credential'`

If a key was ever committed anywhere, rotating it is the only fix that matters —
deleting the commit does not.
