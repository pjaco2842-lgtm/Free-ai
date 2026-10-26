# Skill safety — check before you install

A **skill** is a folder with a `SKILL.md` in it. That file is a set of instructions
your agent will follow **with your permissions** — it can read your API keys, open
your folders, and run the scripts that ship next to it.

Skills also arrive as **`.zip` (or `.skill`) files with scripts inside**. That is the
riskier form: nobody reads the twenty lines of shell in a zip, and the `SKILL.md` can
tell the agent to run them. NVIDIA built this scanner after auditing a large set of
public skills and reported hostile code in a meaningful share of them — the exact
number I can't verify, but you don't need it: scanning costs seconds.

So: one command before you install anything.

```bash
./agent/scan-skill.sh ~/Downloads/some-skill.zip
```

The first run installs the scanner (free, open source, from NVIDIA). After that it
takes a few seconds.

---

## The commands

| You want | Run |
|---|---|
Check a zip you downloaded | `./agent/scan-skill.sh ~/Downloads/skill.zip` |
Check a folder | `./agent/scan-skill.sh ~/Downloads/skill-folder` |
Check straight from GitHub | `./agent/scan-skill.sh https://github.com/user/skill` |
Audit everything already installed | `./agent/scan-skill.sh --all` |
Keep a written report | `./agent/scan-skill.sh --save ~/Downloads/skill.zip` |
Also fail on *high* findings | `./agent/scan-skill.sh --strict ~/Downloads/skill.zip`| Deeper read using your free model | `./agent/scan-skill.sh --llm ~/Downloads/skill.zip` |
| Read what the code actually does | `./agent/scan-skill.sh --deep ~/Downloads/skill.zip` |
| Code read only (fast, big repos) | `./agent/scan-skill.sh --deep-only ~/.claude/skills/x` |

Exit codes: **0** nothing critical · **1** something critical · **2** the scan failed or
the target was not a skill. `--save` writes a table of every finding to
`agent/scans/<name>-<date>.md`.

One behaviour worth knowing: if the target has no `SKILL.md` in it, the wrapper
**refuses to give you a green light** and exits 2. The raw scanner would call that
folder `SAFE` because it found nothing bad in the three files it happened to read —
that is the one result you should never trust. Usually it means you pointed at the
folder *above* the skill, so aim one level down or at the zip itself.

`--llm` reuses the local gateway from `setup-cc-free.sh` (start `ccg` once so the
gateway is up). Without it you get static rule matching, which is what catches the
obvious attacks anyway.

---

**`--deep` is the one to run on anything you didn't write.** The scanner answers "does
this match a known bad pattern"; `--deep` answers "what will this do to my machine" —
the hosts it contacts, where it can run commands, where it touches home or key
directories, where it posts data, and **which hooks run automatically on every
prompt**. A hook with a command runs whether or not you remember installing it.

## How to read the result

The report gives a score out of 100 and a verdict. **Do not treat the score as a
pass/fail.** Here is what the same scanner said about things I scanned while wiring
this up:

| What I scanned | Score | Reality |
|---|---|---|
A skill I wrote myself (`echo hi`) | 0 — SAFE | Correct |
A deliberately malicious test skill | 100 — DO NOT INSTALL | Correct: caught a YARA signature in `scripts/setup.sh` |
`ponytail` (a real, widely used plugin) | 100 — DO NOT INSTALL | Flagged an **API call in its own benchmark code** and the word `keychain` in its config docs |
`addyosmani/agent-skills` (real, popular pack) | 100 — DO NOT INSTALL | 183 findings, mostly "this skill reads your `.claude/` folder" — which is literally its job |
`day-trader-skill` (real, popular pack) | 100 — DO NOT INSTALL | 21 "prompt injection" hits — text that *talks about* prompts |

**Everything real scores 100.** The scanner is a smoke alarm that would rather wake
you up ten times than miss a fire. So the number tells you *where to look*, and the
findings tell you *what it actually is*. Read them.

### Signal — treat as real until you understand it

- **YARA Match** on a `.sh`, `.py`, `.js` — a known malware signature. Stop here.
- A script that reads `~/.ssh`, `~/.aws`, `.env`, wallet files, browser cookie stores.
- `curl` / `wget` / `fetch` sending anything *out*, especially to a webhook, pastebin,
  or an IP address instead of a known domain.
- `base64` on a file followed by a network call. That is packaging data to ship out.
- `rm -rf` outside the skill's own folder, `chmod +x` on a downloaded blob, `eval` on
  remote content.
- An executable hidden inside a document: a `.png`, `.md` or `.json` that is really code.

### Noise — common in harmless skills

- "reads agent configuration directories (`.claude/`, `.codex/`)" — that is how a skill
  reads its own settings.
- "mentions `keychain` / `credentials` / `token`" in a `description` field.
- "env var flows to a network sink" inside `benchmarks/`, `tests/`, or `examples/`.
- "declares no tool scope" — a missing `permissions:` block, not an attack.
- prompt-injection matches in text that merely *discusses* prompts.

Rule of thumb: **a finding in a file that runs is signal; a finding in a file that is
read is usually noise.** `scripts/x.sh` runs. `README.md` is read.

---

## The invisible-instructions trick

Bad instructions can hide in characters you cannot see — zero-width spaces, or a
right-to-left override that makes a line display in a different order than it runs.
SkillSpector looks for this; this is the manual double-check, and it costs two seconds:

```bash
python3 - <<'PY'
import pathlib, unicodedata
BAD = {0x200b,0x200c,0x200d,0x200e,0x200f,0x202a,0x202b,0x202c,0x202d,0x202e,
       0x2060,0x2066,0x2067,0x2068,0xfeff}
for p in pathlib.Path('.').rglob('*'):
    if p.is_file() and p.suffix in {'.md', '.txt', '.json', '.yaml', '.yml', '.sh', '.py', '.js'}:
        for n, line in enumerate(p.read_text(errors='replace').splitlines(), 1):
            hits = sorted({c for c in line if ord(c) in BAD})
            if hits:
                print(f"{p}:{n}: {', '.join(unicodedata.name(c, hex(ord(c))) for c in hits)}")
PY
```

Run it inside the skill's folder (the one you unzipped). No output means clean.

---

## If you already installed something you now distrust

1. **Turn it off first.** Move the folder out of the way rather than deleting it, so
   the scanner can still look at it:
   ```bash
   mv ~/.claude/skills/<name> ~/Desktop/quarantine-<name>
   ```
   Plugins live in `~/.claude/plugins/marketplaces/<name>` — disable the plugin in
   Claude Code, don't just edit files.
2. **Assume any key the machine could read is burned.** Rotate the ones that live on
   that Mac: the Gemini key, the Groq key, anything in `~/.llm-gateway/env.sh`.
3. **Check what the wallet can see.** Skills only touch files; they cannot sign a
   transaction on their own. But if a seed phrase or private key was ever on that
   machine, move the funds to a fresh wallet.
4. **Then** run `./agent/scan-skill.sh --all` and read the findings before turning
   anything back on.

---

## Two habits that beat any scanner

1. **Scan the zip before you unzip it, not after.** Once it is unzipped into
   `~/.claude/skills` the agent can already read it.
2. **Install fewer skills.** Every skill you add widens what your agent can reach.
   You do not need twenty of them; you need the two that do the job.

The set of skills you actually use lives in two places: `~/.claude/skills` (folders you
added yourself, which is what `--all` audits) and `~/.claude/plugins/marketplaces`
(things you installed from a marketplace — point the command at that folder directly,
e.g. `./agent/scan-skill.sh ~/.claude/plugins/marketplaces/some-plugin`).
