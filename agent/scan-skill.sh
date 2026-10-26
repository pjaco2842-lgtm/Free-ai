#!/usr/bin/env bash
# scan-skill.sh — check an AI agent skill for malware BEFORE you install it.
#
# A "skill" is a folder with a SKILL.md inside. That file is instructions the
# agent will follow with YOUR permissions: it can read your keys, open your
# folders, and run scripts. A skill can also arrive as a .zip (or .skill) with
# scripts inside — this script unpacks nothing, SkillSpector reads the archive.
#
# This wrapper:
#   * installs NVIDIA SkillSpector the first time you run it (free, open source)
#   * accepts a folder, a .zip, a .skill file, or an https://github.com/... URL
#   * prints the score AND the findings, in plain English
#   * exits 1 when something critical was found, so you can use it in a script
#
# Usage:
#   ./scan-skill.sh ~/Downloads/some-skill.zip
#   ./scan-skill.sh ~/.claude/skills/my-skill
#   ./scan-skill.sh https://github.com/user/some-skill
#   ./scan-skill.sh --all              audit everything already installed
#   ./scan-skill.sh --save <target>    also write a markdown report
#   ./scan-skill.sh --strict <target>  also fail on HIGH findings
#   ./scan-skill.sh --llm <target>     use your free local model, not just static rules
#
# Exit codes: 0 nothing critical · 1 critical (or HIGH with --strict) · 2 error

set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="$REPO_DIR/agent/scans"
SKILLS_DIR="$HOME/.claude/skills"
TOOL=""

STRICT=0
USE_LLM=0
SAVE=0
SCAN_ALL=0
TARGET=""

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m%s\033[0m\n' "$*"; }
die()  { printf '\n\033[1;31m%s\033[0m\n' "$*" >&2; exit 2; }

usage() {
  sed -n '3,25p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 0
}

# --- arguments --------------------------------------------------------------
while [ $# -gt 0 ]; do
  case "$1" in
    --all)     SCAN_ALL=1 ;;
    --save)    SAVE=1 ;;
    --strict)  STRICT=1 ;;
    --llm)     USE_LLM=1 ;;
    -h|--help) usage ;;
    -*)        die "Unknown option: $1" ;;
    *)         TARGET="$1" ;;
  esac
  shift
done

[ "$SCAN_ALL" -eq 1 ] || [ -n "$TARGET" ] || usage
command -v python3 >/dev/null 2>&1 || die "python3 is not installed. Run: brew install python@3.12"

# --- find or install the scanner --------------------------------------------
find_tool() {
  if command -v skillspector >/dev/null 2>&1; then TOOL="$(command -v skillspector)"; return 0; fi
  for candidate in "$HOME/.local/bin/skillspector" "$HOME/.skillspector/venv/bin/skillspector"; do
    if [ -x "$candidate" ]; then TOOL="$candidate"; return 0; fi
  done
  return 1
}

ensure_tool() {
  find_tool && return 0
  say "First run: installing SkillSpector (one time, 1-3 minutes, needs internet)"
  local src="git+https://github.com/NVIDIA/SkillSpector.git"
  if command -v uv >/dev/null 2>&1; then
    uv tool install --quiet "$src" >/dev/null 2>&1
    find_tool && return 0
  fi
  if command -v pipx >/dev/null 2>&1; then
    pipx install --quiet "$src" >/dev/null 2>&1
    find_tool && return 0
  fi
  mkdir -p "$HOME/.skillspector"
  python3 -m venv "$HOME/.skillspector/venv" >/dev/null 2>&1
  "$HOME/.skillspector/venv/bin/pip" install -q --upgrade pip >/dev/null 2>&1
  "$HOME/.skillspector/venv/bin/pip" install -q "$src" >/dev/null 2>&1
  find_tool && return 0
  die "Could not install SkillSpector. Check your internet connection and try again."
}

# Optional free LLM layer: reuse the local gateway from setup-cc-free.sh.
# Without it the scan is static rules only — still catches the obvious attacks.
llm_env_note() {
  [ "$USE_LLM" -eq 1 ] || return 0
  if [ -z "${SKILLSPECTOR_PROVIDER:-}" ] && [ -f "$HOME/.llm-gateway/env.sh" ]; then
    PORT_LINE="$(grep -o '127\.0\.0\.1:[0-9]*' "$HOME/.llm-gateway/env.sh" 2>/dev/null | head -1)"
    TOKEN="$(sed -n 's/^export ANTHROPIC_AUTH_TOKEN="\(.*\)"$/\1/p' "$HOME/.llm-gateway/env.sh" 2>/dev/null | head -1)"
    if [ -n "$PORT_LINE" ] && [ -n "$TOKEN" ]; then
      export SKILLSPECTOR_PROVIDER=openai
      export OPENAI_BASE_URL="http://$PORT_LINE/v1"
      export OPENAI_API_KEY="$TOKEN"
      export SKILLSPECTOR_MODEL="${SKILLSPECTOR_MODEL:-free}"
      printf 'Using your local free gateway for the deeper read (gateway must be running).\n'
      return 0
    fi
  fi
  if [ -z "${SKILLSPECTOR_PROVIDER:-}" ]; then
    warn "No model configured for --llm, falling back to static analysis only."
    warn "Fix: run inside 'ccg', or set SKILLSPECTOR_PROVIDER + its key."
    USE_LLM=0
  fi
}

# --- one scan ---------------------------------------------------------------
# Renders the JSON SkillSpector wrote. Keeps every decision in one place.
render() { # $1=json  $2=label  $3=strict  $4=report_path(or empty)  $5=llm_requested
  python3 - "$1" "$2" "$3" "$4" "$5" <<'PY'
import json, os, sys, datetime

path, label, strict = sys.argv[1], sys.argv[2], sys.argv[3] == '1'
report_path, llm_requested = sys.argv[4], sys.argv[5] == '1'
try:
    with open(path) as fh:
        data = json.load(fh)
except Exception:
    print("  Scanner produced no report — the target may not be a skill")
    print("  (a skill folder needs a SKILL.md at its top level).")
    sys.exit(2)

ra    = data.get('risk_assessment') or {}
score = ra.get('score', 0)
rec   = (ra.get('recommendation') or 'UNKNOWN').replace('_', ' ')
sev   = ra.get('severity') or '?'
issues = data.get('issues') or []
meta   = data.get('metadata') or {}

# A folder with no SKILL.md is not a skill. The scanner still returns a cheerful
# SAFE because it found nothing bad in the handful of files it looked at — the
# dangerous version of a false alarm. Catch it here instead of trusting it.
components = data.get('components') or []
has_skill_md = any('skill.md' in str(c.get('path', '')).lower() for c in components)

rank  = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
count = {k: 0 for k in rank}
for i in issues:
    s = (i.get('severity') or '').upper()
    if s in count:
        count[s] += 1

crit = count['CRITICAL']
high = count['HIGH']
# SkillSpector labels an otherwise spotless scan 'CAUTION' because it also weighs
# factors beyond findings. With zero findings and a zero score there is nothing
# for a reader to act on, so say that instead of inventing alarm.
if not issues and score == 0 and not crit and not high:
    rec = 'CLEAN — nothing flagged'
color = {'DO NOT INSTALL': '\033[1;31m', 'REVIEW': '\033[1;33m',
         'SAFE': '\033[1;32m', 'CLEAN — nothing flagged': '\033[1;32m'}
head  = color.get(rec, '\033[1m')

print()
print(f"  \033[1m{label}\033[0m")
print(f"  Verdict: {head}{rec}\033[0m   score {score}/100   "
      f"critical {crit} · high {high} · medium {count['MEDIUM']}")

if not has_skill_md:
    if score == 0 and not issues:
        print("\n  \033[1;33mNOT A SKILL — nothing was really checked.\033[0m")
        print("  No SKILL.md inside that target, so a clean score means nothing here.")
        print("  Point this at the folder that holds SKILL.md, or straight at the .zip.")
        sys.exit(2)
    print("\n  \033[1;33mNote:\033[0m no SKILL.md found — the findings below come from loose files.")

if llm_requested and not meta.get('llm_available'):
    print("  \033[1;33mNote:\033[0m the deeper model pass was unavailable — static analysis only.")

if issues:
    print("\n  What it flagged (worst first):")
    seen = set()
    shown = 0
    for i in sorted(issues, key=lambda x: rank.get((x.get('severity') or '').upper(), 9)):
        loc = i.get('location') or {}
        f   = loc.get('file') or '?'
        ln  = loc.get('start_line')
        where = f"{f}:{ln}" if ln else f
        cat = (i.get('category') or '?')[:22]
        desc = (i.get('explanation') or i.get('pattern') or '')[:88]
        key = (i.get('severity'), cat, where, desc)
        if key in seen:
            continue
        seen.add(key)
        shown += 1
        if shown > 6:
            break
        s = (i.get('severity') or '?').upper()
        print(f"   {s:<9} {cat:<22} {where:<38} {desc}")
    if len(seen) > 6:
        print(f"   … {len(seen) - 6} more distinct findings in the report")

print("\n  How to read this: the score is a smoke alarm, not a verdict.")
print("  Widely used, harmless skill packs also score 100 — read the findings.")

markdown = None
if report_path:
    lines = [f"# Skill scan — {label}", "",
             f"- Date: {datetime.date.today().isoformat()}",
             f"- Score: {score}/100 — {rec} ({sev})",
             f"- Findings: critical {crit}, high {high}, medium {count['MEDIUM']}, low {count['LOW']}",
             "", "| severity | category | file | detail |", "|---|---|---|---|"]
    for i in sorted(issues, key=lambda x: rank.get((x.get('severity') or '').upper(), 9))[:40]:
        loc = i.get('location') or {}
        f = loc.get('file') or '?'
        if loc.get('start_line'):
            f += f":{loc['start_line']}"
        detail = (i.get('explanation') or i.get('pattern') or '').replace('|', '/')[:200]
        lines.append(f"| {i.get('severity')} | {i.get('category')} | `{f}` | {detail} |")
    markdown = "\n".join(lines) + "\n"

if markdown:
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w') as fh:
        fh.write(markdown)
    print(f"\n  Full report: {report_path}")

sys.exit(1 if crit or (strict and high) else 0)
PY
}

scan_one() { # $1=target  $2=label
  local json err rc report
  # Portable across macOS and Linux (macOS mktemp accepts -t, GNU needs XXXXXX).
  json="$(mktemp "${TMPDIR:-/tmp}/skillspector.XXXXXX")" || die "Cannot create a temp file."
  err="$json.err"
  report=""
  [ "$SAVE" -eq 1 ] && report="$REPORT_DIR/$2-$(date +%Y-%m-%d).md"

  local flags=(--format json --output "$json")
  [ "$USE_LLM" -eq 0 ] && flags+=(--no-llm)

  "$TOOL" scan "$1" "${flags[@]}" >/dev/null 2>"$err"
  rc=$?
  if [ $rc -ne 0 ] && [ ! -s "$json" ]; then
    printf '\n  \033[1;31mScan failed\033[0m for %s\n' "$1"
    sed -n '1,6p' "$err" >&2
    rm -f "$json" "$err"
    return 2
  fi

  render "$json" "$2" "$STRICT" "$report" "$USE_LLM"
  rc=$?
  rm -f "$json" "$err"
  return $rc
}

# --- run --------------------------------------------------------------------
ensure_tool
llm_env_note

printf 'Scanner: %s\n' "$("$TOOL" --version 2>/dev/null | head -1)"

worst=0

if [ "$SCAN_ALL" -eq 1 ]; then
  if [ ! -d "$SKILLS_DIR" ]; then
    printf '\nNo skills installed yet — %s does not exist.\n' "$SKILLS_DIR"
    printf 'That is a clean answer: nothing is installed, so nothing can misbehave.\n'
    exit 0
  fi
  found=0
  for dir in "$SKILLS_DIR"/*/; do
    [ -f "$dir/SKILL.md" ] || continue
    found=$((found + 1))
    scan_one "${dir%/}" "$(basename "$dir")"
    rc=$?
    [ $rc -gt $worst ] && worst=$rc
  done
  if [ $found -eq 0 ]; then
    printf '\nNo installed skills to audit in %s\n' "$SKILLS_DIR"
  else
    printf '\n%d skill(s) audited.\n' "$found"
  fi
else
  scan_one "$TARGET" "$(basename "$TARGET" | sed 's/\.\(zip\|skill\)$//')"
  worst=$?
fi

if [ $worst -eq 1 ]; then
  printf '\n\033[1;31mDo not install until you have read the findings above.\033[0m\n'
elif [ $worst -eq 0 ]; then
  printf '\n\033[1;32mNothing critical. Still skim the findings before you install.\033[0m\n'
fi
exit $worst
