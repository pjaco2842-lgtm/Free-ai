# Security checklist — all 70 items, with verdicts

Living document. Every row is a claim about this repo, and each one says where to
look so you can check it instead of trusting it. Your original numbers are kept
(including the duplicates you have) so you can tick them off one by one.

Re-run the whole audit any time:

```bash
npm audit --omit=dev                     # dependencies
grep -rnE 'sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{20,}' --include='*.ts' --include='*.py' . | grep -v node_modules
git log --all --name-only --pretty=format: | sort -u | grep -iE '\.env|secret|\.pem|\.key'
./agent/scan-skill.sh --all              # installed skills
npm run build -w server && npx -w server vitest run
```

**Legend**

| Mark | Meaning |
|---|---|
| ✅ | Done, verified in code |
| 🔧 | Was broken, fixed — see "What changed" |
| ⚠️ | Reviewed, risk accepted knowingly (reason given) |
| ➖ | Does not apply (reason given) |
| ⬜ | Open — needs your decision or work you haven't asked for |

---

## Secrets and configuration

| # | Item | Verdict | Where |
|---|---|---|---|
| 1 | Exposed DB credentials | ➖ | SQLite file — no database server, so no DB password exists to expose |
| 2 | Public `.env` files | ✅ | `.gitignore:14`; `.env.example` ships with every value empty |
| 3 | Hardcoded secrets | ✅ | Full pattern sweep (provider keys, tokens, private-key blocks): no hits in source |
| 4 | Weak auth | ✅ | scrypt + per-password salt + `timingSafeEqual` (`lib/password.ts`); 8-char minimum (`routes/auth.ts:32`) |
| 5 | Missing authz check | ✅ | All 20+ `/api` routers behind `requireAuth` (`app.ts:254-284`) |
| 6 | Cross-user access | ➖ | One account per install; no tenancy to cross |
| 7 | Open DB permissions | ✅ | DB, WAL and keyfile `0600`, dirs `0700` (`lib/file-permissions.ts:137`) |
| 8 | Cloud service misconfig | ⚠️ | Not visible from this repo — your host, DNS, TLS and firewall live on your machine. `docker-compose.yml:25` publishes to `127.0.0.1` only |
| 9 | Unprotected admin route | ✅ | Same gate as #5; `/api/auth/*` is the only open surface, by design |
| 9b | Secrets in git | ✅ | 15 commits total; no `.env`, key, `.db` or credential file ever committed |
| 10 | Exposed prod debug tools | ✅ | No `/debug`, `/metrics` or `__debug` route exists |
| 11 | Logs leak secrets | ✅ | `lib/log-redaction.ts` scrubs keys before any log write; `/api/logs` sits behind auth |
| 12 | Verbose prod errors | ✅ | 5xx bodies replaced in production (`middleware/errorHandler.ts:41`) |
| 12b | Secrets in JS | ✅ | No provider key in `client/`; the browser only holds its own session token |
| 12c | Client-only security | ✅ | Every check is server-side; the client only renders |
| 29 | Rate limits | ✅ | Per-IP proxy limiter, admin limiter, export limiter (10/min), per-email login lockout (`middleware/rateLimit.ts`, `routes/auth.ts:48-91`) |
| 29b | Exposed environments | ⚠️ | `HOST` defaults to `::` — every interface. See "Decide" |
| 30 | Default credentials | ✅ | No shipped account. First-run setup requires a code unless it comes from loopback (`routes/auth.ts:221`); the desktop session gets a random 24-byte password |
| 48 | Unencrypted data | ✅ | Provider keys AES-256-GCM at rest (`lib/crypto.ts:7`). The SQLite file is plaintext, protected by file mode — normal for a local tool |

## Web application

| # | Item | Verdict | Where |
|---|---|---|---|
| 12d | Input validation | ✅ | zod schemas in 21 route files; body limits 10–25 MB by surface (`app.ts:216`) |
| 12e | SQL injection | ✅ | Prepared statements throughout; the few dynamic identifiers are whitelisted (`routes/profiles.ts:400` uses `Object.hasOwn`) |
| 12f | NoSQL injection | ➖ | No document store |
| 19 | XSS | ✅ | React escaping; the single `dangerouslySetInnerHTML` is highlight.js output, which escapes (`client/src/lib/highlight.ts:64`); CSP forbids inline script except one hash-pinned bootstrap (`app.ts:62`) |
| 20 | CSRF | ➖ | Bearer token in a header, never a cookie — a cross-site form post cannot carry it |
| 21 | Insecure file uploads | ✅ | `multer` memory storage, 5 MB / 10 files, extension allowlist; transcription 1 file; image parsing via the patched `sharp` |
| 22 | Path traversal | ✅ | No route builds a filesystem path from user input (grepped `path.join/resolve` against `req.*`: no hits) |
| 23 | SSRF | ✅ | `lib/url-guard.ts` guards media, proxy, ratelimit and key fetches |
| 24 | Broken password reset | ✅ | One-time codes with expiry (`lib/reset-code.ts`), generic failures, inside the login lockout |
| 25 | Weak session management | ✅ | 32-byte random token, only its SHA-256 stored, 30-day TTL, expired rows deleted on use (`services/auth.ts:71-95`) |
| 26 | JWT secrets | ➖ | No JWT anywhere — opaque tokens only |
| 27 | Permissive CORS | ✅ | Explicit allowlist, no wildcard (`app.ts:190`) |
| 33 | IDOR / BOLA | ✅ | Resources resolve through the session, never from a client-supplied owner id |
| 34 | APIs + user input | ✅ | Same as #12d |
| 35 | Exposed logs | ✅ | Authenticated, and redacted at write time |
| 36 | Exposed source maps | ✅ | No `sourcemap` in the Vite build — production ships no maps |
| 45 | Exposed internal dashboards | ⚠️ | The dashboard *is* the app, behind auth — but see #29b for who can reach the port |
| 46 | Missing security headers | ✅ | Helmet: CSP, COOP, Origin-Agent-Cluster, frame/sniff/referrer policies (`app.ts:138`) |
| 47 | Insecure cookie settings | ➖ | Zero cookies set or read |
| 51 | Mass assignment | ✅ | Updates build explicit column lists from allowlists (`routes/keys.ts:792`, `routes/models.ts:295`, `routes/profiles.ts:262`) |
| 54 | Misconfigured OAuth | ➖ | No OAuth provider |
| 55 | No MFA | ⚠️ | Single-user local tool with no identity provider; the login lockout stands in. Add TOTP if this ever faces the internet |
| 56 | Account enumeration | ✅ | Login answers "Invalid email or password" for both cases (`routes/auth.ts:264`) |
| 57 | Business logic abuse | ⚠️ | `lib/budget.ts` and `lib/guardrails.ts` are cost controls, not an authorization boundary |
| 58 | Race conditions | ⚠️ | SQLite serialises writes; login state is per-process memory, so a multi-process deploy would need a shared store |
| 69 | Open redirects | ➖ | No `res.redirect()` exists |
| 70 | Unsecured endpoints | ✅ | Only `/health`, `/api/ping` and the docs surface are open, by design |

## Agent, AI and skills

| # | Item | Verdict | Where |
|---|---|---|---|
| 38 | Malicious packages | ⚠️ | Lockfile integrity hashes + `npm ci` in CI; nothing scans for typosquats. Skills *are* scanned: `agent/scan-skill.sh` |
| 39 | Prompt injection | ⚠️ | Alerts and file contents are data, never instructions — but the worker cannot tell a malicious README from a task. Deny-lists and step limits reduce it; nothing eliminates it |
| 40 | Unpermissioned AI access | 🔧 | The worker handed every model-chosen command your whole environment, `GEMINI_API_KEY` included. Now a scrubbed child env (paths and locale only) |
| 41 | Excessive DB permissions | ✅ | One local file, one process, no shared DB user |
| 42 | Missing audit logs | ✅ | `journal.jsonl` per step, request log per call, decision log for routing |
| 43 | No security monitoring | ⚠️ | Logs exist, no alerting. Local install, nobody on call — say the word and I'll add a daily digest |
| 44 | No backups / restore | ✅ | `/api/backups` plus `lib/db-backup.ts` |
| 49 | Poor tenant isolation | ➖ | Single-tenant |
| 50 | Unreviewed code | ⚠️ | 863 TypeScript files. I read the security-relevant paths, not all of it; the 4599-test suite is the broader net |
| 52 | Command injection | 🔧 | Worker: credential deny-list, a fixed workspace-prefix bypass in `safe_path`, scrubbed env. Server: `execFile` with constant args only (`routes/update.ts:399`) |
| 53 | Insecure deserialisation | ✅ | JSON only; no `eval`, no `new Function`, no pickle |
| 63 | Checks fail open | 🔧 | The webhook now refuses to start on a public interface without a secret, instead of answering 200 to strangers |
| 64 | Missing timeouts | ✅ | `CMD_TIMEOUT`, task time limit, `lib/provider-timeout.ts` |
| 65 | Sensitive info leak | ✅ | Redaction in logs and errors (#11, #12) |
| 66 | Invalid AI output | ✅ | `parse_action` recovers JSON or fails the step; `lib/tool-validate.ts` validates tool args |
| 67 | Excessive AI permissions | 🔧 | The desk skill declares its tool scope; the worker refuses credential paths and scrubbed its env |
| 68 | Sensitive browser storage | ⚠️ | The dashboard token lives in `localStorage` (`client/src/lib/api.ts:4`) — any XSS steals a 30-day session. Accepted: Bearer is required by the CLI/desktop clients, CSP blocks inline script, and the token is hashed server-side. Fixing it means an httpOnly cookie, which breaks those clients |

## Webhooks and delivery

| # | Item | Verdict | Where |
|---|---|---|---|
| 31 | Unsigned webhooks | 🔧 | `trading/webhook.py`: constant-time secret compare, replay window, dedupe, per-IP rate limit |
| 32 | FE payment checks | ➖ | No payments in this app |
| 59 | Webhook replay | 🔧 | Identical body within 2 min dropped as a retry; alert timestamps older than 5 min rejected |
| 60 | Insecure CI/CD | ✅ | 4 workflows, `npm ci`, no secrets in them |
| 61 | Untrusted build actions | ✅ | Every action pinned by commit SHA (e.g. `actions/checkout@3d3c42e…`) |
| 62 | Unpinned build dependencies | ✅ | Lockfile committed; CI installs from it |

## Dependencies

| # | Item | Verdict | Where |
|---|---|---|---|
| 37 | Vulnerable dependencies | 🔧 | Runtime CVEs **20 → 1**; all deps 27 → 5; 92 packages updated in-range, 47 removed. Server builds clean, 372/372 test files, 4599 tests pass |

Left open on purpose: `zod` 3→4 (high severity, breaking, touches 21 route files) and
`vitest`/`tinypool` (critical, **test-only**, never shipped).

---

## What changed in this round

1. **`agent/worker.py`** — model-chosen commands no longer inherit your environment,
   so `printenv` in a task cannot leak `GEMINI_API_KEY`. Credential files and
   directories (`.env`, `.ssh`, `.aws`, `.llm-gateway`, `*.pem`, `*.key`) are refused
   for read *and* write, and `safe_path` now uses `relative_to` — a string prefix let
   a sibling directory through. Verified: 6 path cases, 8 command cases, env scrub.
2. **`trading/webhook.py`** — refuses a public bind without a secret, compares it in
   constant time, drops retried duplicates, rejects stale timestamps, limits 60/min
   per IP. Verified live: 403 / 403 / 200 / duplicate / 400 / 429.
3. **Dependencies** — `npm audit fix --package-lock-only`, measured before and after.

## Decide

1. **`HOST=127.0.0.1`** in `.env` — otherwise the dashboard, and every provider key
   behind it, answers to any device on your Wi-Fi. One line; breaks phone access.
2. **`zod` 4** — its own task, so the 4599 tests can catch the fallout.
3. **MFA / monitoring** — only worth it if this stops being a laptop tool.

## The three rules from that screenshot story, checked

| Rule | Status |
|---|---|
| "Keys live in `.env`" | ✅ provider keys sit encrypted in the DB, sealed by a key from `.env` or a `0600` keyfile |
| "`.env` goes in gitignore" | ✅ line 14, and never committed |
| "The browser never sees a secret" | ✅ the browser holds only its own session token; provider keys stay server-side and the server makes every upstream call |
| "New key" when one leaks | → rotate at the provider, then re-enter it in the dashboard |
| "Spending cap" | → set it at the provider. Free tiers cap themselves; a paid key does not |
