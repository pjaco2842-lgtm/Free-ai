# Skill audit — the three installed packs, read in full

**Date:** 2026-10-26
**Targets:** `ponytail`, `addy-agent-skills`, `day-trader-skill` in
`~/.claude/plugins/marketplaces/`
**Verdict: no malware. All three are safe to keep.** Two behaviours are worth
knowing about, both listed under "Not malware, but know this".

## What was covered

| Repo | Files | Lines | Code files | Docs |
|---|---|---|---|---|
`ponytail` | 214 | 89,498 | 61 | 60 |
`addy-agent-skills` | 216 | 23,573 | 45 | 113 |
`day-trader-skill` | 85 | 18,443 | 24 | 18 |
**Total** | **515** | **131,514** | **130** | **191** |

Reading 131k lines line-by-line isn't the useful shape of this job. What matters is
that every line that can *do* something was read, and that nothing was skipped by
sampling. So:

1. **Every file was enumerated** (515 files, no directory skipped except `.git`).
2. **Every call site** of a network request, a process spawn, a filesystem write, or
   an environment read was extracted and reviewed — the whole list, not a sample.
3. **Every host** mentioned in code was collected and classified.
4. **Every instruction file** (191 docs) was scanned for directives that would send
   data out, read credentials, or override the agent.
5. **Every hook registration** was read, because a hook with a command runs without
   anyone asking.
6. **Hidden Unicode** (zero-width, bidi overrides) was checked in every file.
7. Test fixtures and vendored code were separated from shipped code, and reviewed
   only for what they could do when *run*.

## Per-repo result

### ponytail — a coding-style plugin with a task board

**Hosts in code:** `api.anthropic.com`, `platform.claude.com` (both only in its own
benchmark harness), `github.com`, `www.w3.org` (XML namespaces), `board.example.com`
(test fixture only).

**Runs commands at:** only inside `benchmarks/` and `scripts/` — its own `git
ls-files` via `execFileSync` with fixed arguments, and `node` spawning its own
`ponytail-band-import.js`. **No shell string interpolation, so no command injection
surface.**

**Writes:** mode flags and a per-project CSV under `~/.config/ponytail/`, plus
`~/.claude` files it owns. Nothing outside those.

**Hooks — this is the part that matters:** it registers three hooks
(`SessionStart`, `SubagentStart`, `UserPromptSubmit`), each running one of its own
local Node scripts. They read the prompt only to spot `/ponytail` commands, and they
never touch the network.

**Verdict: clean.** The `critical` SkillSpector finding was an API call in
`benchmarks/agentic/judge.py` — its own evaluation code sending the user's own key to
Anthropic. Not exfiltration; that's how a benchmark talks to a model.

### addy-agent-skills — a library of skill documents

**Hosts in code:** `example.com`, `docs.example.com`, `owasp.org` — all in examples
or references.

**Exec:** only in its own validation scripts and their tests (`spawnSync` of `node`
and `git`).

**Writes:** test fixtures under temporary directories, plus a WebFetch cache under
`.claude/sdd-cache/` if you wire that hook up.

**Hooks:** the repo *ships* hooks (`sdd-cache-pre/post.sh`, `simplify-ignore.sh`,
`session-start.sh`) but the manifest has `"hooks": null` and there is no settings
file that installs them. **Nothing runs unless you copy them into your own config.**

**Verdict: clean.** Its 183 findings were the scanner noticing that a skill about
code review mentions `.claude/` paths — which is the subject matter.

### day-trader-skill — market data and trade planning

**Hosts in code:** `query1/query2.finance.yahoo.com`, `feeds.finance.yahoo.com`,
`stooq.com`, `www.sec.gov`, `data.sec.gov`, `disclosures-clerk.house.gov`,
`www.nasdaqtrader.com`, `www.nyse.com`, `github.com` (in its user-agent string).
**Every one is a public market-data or filing source, fetched with GET.**

**Environment reads:** exactly one — `SEC_USER_AGENT`, which SEC requires you to set
before it will answer. No API keys, no broker credentials, no `.env` access.

**Exec:** `pdftotext` on a PDF it downloaded, to read a filing. One call site.

**Writes:** JSON/CSV caches in the project directory.

**The broker module is a ticket printer, not a broker connection.** `trader-broker/`
contains zero network calls; it generates order tickets on disk, defaults to
`paper: true`, and labels a non-paper config as "LIVE ACCOUNT, REAL MONEY". Nothing
in this repo can place an order on its own.

**Verdict: clean.** Its 34 findings were `curl`-style fetches (read-only) and
prompt-injection matches inside sample filing text that *discusses* account activity.

## Not malware, but know this

1. **ponytail's task board is on by default.** `userConfig.ledger` defaults to
   `true`: after every turn it appends a row to `~/.config/ponytail/band/<project>.csv`
   with project name, cost, turns, tokens and reuse. Local file, no network — but it
   is a record of your work. Turn it off in the plugin's config if you don't want it.
   Its `webhookUrl` is empty by default and refuses plain HTTP, so nothing is sent
   anywhere unless you set it yourself.
2. **ponytail runs a Node process on every prompt** (its mode tracker). That's a
   small cost per turn, and it's the price of the `/ponytail` mode switching.

Neither is a reason to uninstall. Both are reasons to know what you installed.

## How to re-run this on any skill

```bash
./agent/scan-skill.sh --deep <folder|zip>       # code read + scanner verdict
./agent/scan-skill.sh --deep-only <folder>      # code read only (fast, big repos)
```

`--deep` prints the hosts a skill contacts, where it can run commands, where it
touches home or key directories, where it posts data, which hooks run automatically,
and whether it hides zero-width characters. Every conclusion above is reproducible
with those two lines.

The scanner's score answers "does this match a known bad pattern". `--deep` answers
"what will this do to my machine". Install nothing without both.
