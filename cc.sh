#!/usr/bin/env bash
# Launch Claude Code against this workspace's FreeLLMAPI server.
#
# Claude Code normally talks to Anthropic's paid API. This script points its
# ANTHROPIC_BASE_URL at the local FreeLLMAPI instance instead, and uses the
# unified key that the dashboard already generated, so every claude-* request
# is routed to whichever free provider is configured.
#
# The key is read from the database at run time and never stored in a file or
# printed. Run from anywhere; paths resolve relative to this script.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-http://127.0.0.1:3001}"
export ANTHROPIC_API_KEY="$(
  node -e '
    const Database = require("better-sqlite3");
    const db = new Database(process.argv[1], { readonly: true });
    const row = db.prepare("select value from settings where key = ?").get("unified_api_key");
    if (!row || !row.value) { console.error("No unified API key in the database yet."); process.exit(1); }
    process.stdout.write(row.value);
  ' "$SCRIPT_DIR/server/data/freeapi.db"
)"

# Keep the client quiet about telemetry and self-updates while it is pointed at
# a non-Anthropic backend.
export DISABLE_TELEMETRY=1
export DISABLE_ERROR_REPORTING=1
export DISABLE_AUTOUPDATER=1

CLAUDE_BIN="${CLAUDE_BIN:-$HOME/.npm-global/bin/claude}"
if [[ ! -x "$CLAUDE_BIN" ]]; then
  echo "Claude Code is not installed at $CLAUDE_BIN" >&2
  echo "Install it with: npm install -g --prefix ~/.npm-global @anthropic-ai/claude-code" >&2
  exit 1
fi

cd "$SCRIPT_DIR"
exec "$CLAUDE_BIN" "$@"
