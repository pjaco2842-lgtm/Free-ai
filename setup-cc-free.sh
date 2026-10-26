#!/usr/bin/env bash
# Claude Code on a free model — for GitHub Codespaces (or any Linux box).
#
# What it does:
#   1. installs Claude Code (the CLI)
#   2. installs a small local gateway (LiteLLM) that speaks Anthropic's API
#   3. points Claude Code at that gateway, which forwards to a free model
#
# Everything runs locally in the same terminal session. No server, no tunnel,
# no 24/7 hosting, nothing to keep alive after you close the codespace.
#
# Usage:
#   bash setup-cc-free.sh                     # asks which free provider you have
#   GEMINI_API_KEY=... bash setup-cc-free.sh
#   GROQ_API_KEY=...   bash setup-cc-free.sh  # both may be set; Gemini wins
#
# After it finishes:  ccg        (or  ccg -p "explain this repo" )
#
# Optional overrides:
#   GEMINI_MODEL      default gemini-3.8-flash
#   GROQ_MODEL        default openai/gpt-oss-120b
#   GATEWAY_PORT      default 4000
#   GATEWAY_DIR       default ~/.llm-gateway
#   GATEWAY_VENV      python venv to reuse (default $GATEWAY_DIR/venv)
#   OPENAI_BASE_URL   point at any other OpenAI-compatible endpoint
#   GATEWAY_MODEL     full gateway model string (advanced/testing)

set -uo pipefail

PORT="${GATEWAY_PORT:-4000}"
DIR="${GATEWAY_DIR:-$HOME/.llm-gateway}"
VENV="${GATEWAY_VENV:-$DIR/venv}"
BIN="$HOME/.npm-global/bin"
mkdir -p "$DIR" "$BIN"

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31m%s\033[0m\n' "$*" >&2; exit 1; }

command -v node >/dev/null || die "node is not installed (Codespaces has it by default)."
command -v python3 >/dev/null || die "python3 is not installed (Codespaces has it by default)."
command -v curl >/dev/null || die "curl is not installed."

# --- 1. Claude Code ---------------------------------------------------------
if [ ! -x "$BIN/claude" ]; then
  say "1/5 Installing Claude Code (one time, about a minute)"
  npm install -g --prefix "$HOME/.npm-global" @anthropic-ai/claude-code || die "Claude Code install failed."
else
  say "1/5 Claude Code already installed"
fi

# --- 2. gateway -------------------------------------------------------------
PYTHON_BIN="$(command -v python3.12 || command -v python3.11 || command -v python3)"
[ -n "$PYTHON_BIN" ] || die "No python3 found. Install it with: brew install python@3.12"

if [ ! -x "$VENV/bin/litellm" ]; then
  say "2/5 Installing the local gateway (one time, 2-3 minutes, be patient)"
  say "    using $PYTHON_BIN ($("$PYTHON_BIN" -V 2>&1))"
  rm -rf "$VENV"
  "$PYTHON_BIN" -m venv "$VENV" || die "Could not create the python venv."
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q 'litellm[proxy]' || die "Gateway install failed."
else
  say "2/5 Gateway already installed"
fi
printf '%s\n' "$VENV" > "$DIR/venv-path"

# --- 3. credentials ---------------------------------------------------------
if [ ! -s "$DIR/master.key" ]; then
  python3 -c 'import secrets; print("sk-" + secrets.token_hex(24))' > "$DIR/master.key"
  chmod 600 "$DIR/master.key"
fi
MASTER="$(cat "$DIR/master.key")"

GEMINI_API_KEY="${GEMINI_API_KEY:-}"
GROQ_API_KEY="${GROQ_API_KEY:-}"
if [ -z "$GEMINI_API_KEY" ] && [ -z "$GROQ_API_KEY" ]; then
  cat <<'TXT'

Which free provider do you have a key for?
  1) Google Gemini   recommended — ~250k tokens/minute, ~1,500 requests/day
                     (aistudio.google.com/apikey)
  2) Groq            very fast, but only 8k tokens/minute on the free tier,
                     which is smaller than one big Claude Code request
TXT
  printf 'Enter 1 or 2 [1]: '
  read -r pick
  case "${pick:-1}" in
    2) printf 'Paste your Groq API key (input hidden): '
       read -rs GROQ_API_KEY; echo ;;
    *) printf 'Paste your Gemini API key (input hidden): '
       read -rs GEMINI_API_KEY; echo ;;
  esac
fi

MODELS=()
PROVIDERS=""
if [ -n "${GATEWAY_MODEL:-}" ]; then
  MODELS+=("$GATEWAY_MODEL|${GATEWAY_KEY_VAR:-GEMINI_API_KEY}")
  PROVIDERS="custom"
else
  if [ -n "$GEMINI_API_KEY" ]; then
    MODELS+=("gemini/${GEMINI_MODEL:-gemini-3.8-flash}|GEMINI_API_KEY")
    PROVIDERS="Google Gemini"
  fi
  if [ -n "$GROQ_API_KEY" ]; then
    MODELS+=("groq/${GROQ_MODEL:-openai/gpt-oss-120b}|GROQ_API_KEY")
    PROVIDERS="${PROVIDERS:+$PROVIDERS + }Groq"
  fi
fi
[ "${#MODELS[@]}" -gt 0 ] || die "No API key given, stopping."

# --- 4. config + env --------------------------------------------------------
say "3/5 Writing configuration"

{
  printf 'model_list:\n'
  for entry in "${MODELS[@]}"; do
    printf '  - model_name: free\n'
    printf '    litellm_params:\n'
    printf '      model: %s\n' "${entry%%|*}"
    printf '      api_key: os.environ/%s\n' "${entry##*|}"
    [ -n "${OPENAI_BASE_URL:-}" ] && printf '      api_base: %s\n' "$OPENAI_BASE_URL"
  done
  printf 'litellm_settings:\n  drop_params: true\n  num_retries: 2\n'
  printf 'general_settings:\n  master_key: %s\n' "$MASTER"
} > "$DIR/config.yaml"

{
  printf '# Sourced by the ccg wrapper. This file holds secrets: keep it private.\n'
  printf 'export PATH="%s:$PATH"\n' "$BIN"
  [ -n "$GEMINI_API_KEY" ] && printf 'export GEMINI_API_KEY="%s"\n' "$GEMINI_API_KEY"
  [ -n "$GROQ_API_KEY" ] && printf 'export GROQ_API_KEY="%s"\n' "$GROQ_API_KEY"
  printf 'export ANTHROPIC_BASE_URL="http://127.0.0.1:%s"\n' "$PORT"
  printf 'export ANTHROPIC_AUTH_TOKEN="%s"\n' "$MASTER"
  printf 'export ANTHROPIC_MODEL="free"\n'
  printf 'export ANTHROPIC_SMALL_FAST_MODEL="free"\n'
  printf 'export ANTHROPIC_DEFAULT_HAIKU_MODEL="free"\n'
  printf 'export ANTHROPIC_DEFAULT_SONNET_MODEL="free"\n'
  printf 'export ANTHROPIC_DEFAULT_OPUS_MODEL="free"\n'
  printf 'export CLAUDE_CODE_MAX_CONTEXT_TOKENS="%s"\n' "${CLAUDE_CODE_MAX_CONTEXT_TOKENS:-131072}"
  printf 'export DISABLE_TELEMETRY=1\n'
} > "$DIR/env.sh"
chmod 600 "$DIR/env.sh"

# --- 5. launcher ------------------------------------------------------------
cat > "$DIR/start-gateway.sh" <<'SH'
#!/usr/bin/env bash
# Starts the local gateway if it is not already listening.
set -uo pipefail
SELF="$0"
while [ -L "$SELF" ]; do
  _link="$(readlink "$SELF")"
  case "$_link" in
    /*) SELF="$_link" ;;
    *)  SELF="$(cd "$(dirname "$SELF")" && pwd)/$_link" ;;
  esac
done
DIR="$(cd "$(dirname "$SELF")" && pwd)"
PORT="$(sed -n 's|.*127\.0\.0\.1:\([0-9]*\)".*|\1|p' "$DIR/env.sh" | head -1)"
PORT="${PORT:-4000}"
RESTART=0
[ "${1:-}" = "--restart" ] && RESTART=1

# Reuse the gateway only if it is ours (pidfile alive and running this config).
if [ -f "$DIR/gateway.pid" ] && [ -d "/proc/$(cat "$DIR/gateway.pid")" ] && \
   tr '\0' ' ' < "/proc/$(cat "$DIR/gateway.pid")/cmdline" 2>/dev/null | grep -qF "$DIR/config.yaml"; then
  if [ "$RESTART" = "1" ]; then
    kill "$(cat "$DIR/gateway.pid")" 2>/dev/null
    sleep 2
  else
    curl -sf -o /dev/null "http://127.0.0.1:$PORT/health/liveliness" 2>/dev/null && exit 0
  fi
fi
if curl -sf -o /dev/null "http://127.0.0.1:$PORT/health/liveliness" 2>/dev/null; then
  echo "Port $PORT is already serving a gateway that this script does not own." >&2
  echo "Stop it, or run again with GATEWAY_PORT=<another port>." >&2
  exit 1
fi

set -a
. "$DIR/env.sh"
set +a
VENV="$(cat "$DIR/venv-path" 2>/dev/null || echo "$DIR/venv")"
nohup "$VENV/bin/litellm" --config "$DIR/config.yaml" --port "$PORT" --host 127.0.0.1 \
  > "$DIR/gateway.log" 2>&1 &
echo $! > "$DIR/gateway.pid"
for _ in $(seq 1 90); do
  curl -sf -o /dev/null "http://127.0.0.1:$PORT/health/liveliness" 2>/dev/null && exit 0
  sleep 1
done
echo "Gateway did not start. Last lines of $DIR/gateway.log:" >&2
tail -20 "$DIR/gateway.log" >&2
exit 1
SH

cat > "$DIR/cc" <<'SH'
#!/usr/bin/env bash
# ccg — Claude Code on a free model. Starts the local gateway first if needed.
set -uo pipefail
SELF="$0"
while [ -L "$SELF" ]; do
  _link="$(readlink "$SELF")"
  case "$_link" in
    /*) SELF="$_link" ;;
    *)  SELF="$(cd "$(dirname "$SELF")" && pwd)/$_link" ;;
  esac
done
DIR="$(cd "$(dirname "$SELF")" && pwd)"
"$DIR/start-gateway.sh" || exit 1
set -a
. "$DIR/env.sh"
set +a
exec claude "$@"
SH

chmod +x "$DIR/start-gateway.sh" "$DIR/cc"

# Make `ccg` available without typing a path.
if [ -w /usr/local/bin ]; then
  ln -sf "$DIR/cc" /usr/local/bin/ccg && LINKED=/usr/local/bin/ccg
else
  mkdir -p "$HOME/.local/bin"
  ln -sf "$DIR/cc" "$HOME/.local/bin/ccg" && LINKED="$HOME/.local/bin/ccg"
  # macOS runs zsh by default, Linux runs bash: write the PATH line to both.
  for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
    touch "$rc" 2>/dev/null || continue
    grep -qs 'HOME/.local/bin' "$rc" || \
      printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$rc"
  done
fi

# --- verify ----------------------------------------------------------------
say "4/5 Starting the gateway"
"$DIR/start-gateway.sh" --restart || die "Gateway failed to start."
say "5/5 Test request through $PROVIDERS"
if timeout 120 "$DIR/cc" -p "Reply with exactly: SETUP-OK" 2>/dev/null | grep -q "SETUP-OK"; then
  cat <<DONE

Ready. Claude Code answered through $PROVIDERS.

  ccg                     interactive Claude Code
  ccg -p "your question"  one-shot question
  $LINKED
                          same command, full path

Files live in $DIR
  env.sh       your keys (private, chmod 600)
  config.yaml  model mapping
  gateway.log  gateway output if something breaks
DONE
else
  cat <<FAILED

The gateway started but the test request failed.
Check the log:  tail -30 "$DIR/gateway.log"
Common causes: an invalid API key, a model your key cannot use,
or a rate limit hit (free tiers cap tokens per minute).
FAILED
  exit 1
fi
