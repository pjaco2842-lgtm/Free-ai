#!/usr/bin/env python3
"""
A durable task worker for a free OpenAI-compatible model.

What it is
----------
You drop a task in agent/tasks/*.json, start the worker, and it keeps making
progress until the task is finished, failed, or hits its step/time limits.
Every step is written to disk before the next one runs, so a crash, a reboot or
a closed laptop does not lose the work: restart the worker and it picks up
where it stopped.

What it is not
--------------
* It is not a chat. There is no human in the loop; the model acts on its own.
* It is not magic. A free model misreads instructions constantly. The step
  limits, the journal and the blocked-commands list exist because of that.

Run
---
    python3 agent/worker.py --once          # work until every task is done
    python3 agent/worker.py                 # loop forever, poll every 30s

Environment
-----------
    AGENT_BASE_URL   default http://127.0.0.1:4000/v1  (the local gateway)
    AGENT_API_KEY    default empty                     (gateway master key)
    AGENT_MODEL      default "free"
    AGENT_WORKSPACE  default the repo root
    AGENT_MAX_STEPS  default 25 per task
    AGENT_MAX_MINUTES default 120 per task
    AGENT_POLL       default 30 seconds between empty polls
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("AGENT_ROOT", Path(__file__).resolve().parent))
TASKS = ROOT / "tasks"
STATE = ROOT / "state"
OUT = ROOT / "out"
JOURNAL = ROOT / "journal.jsonl"

BASE_URL = os.environ.get("AGENT_BASE_URL", "http://127.0.0.1:4000/v1")
API_KEY = os.environ.get("AGENT_API_KEY", "")
MODEL = os.environ.get("AGENT_MODEL", "free")
WORKSPACE = Path(os.environ.get("AGENT_WORKSPACE", ROOT.parent)).resolve()
MAX_STEPS = int(os.environ.get("AGENT_MAX_STEPS", "25"))
MAX_MINUTES = float(os.environ.get("AGENT_MAX_MINUTES", "120"))
CMD_TIMEOUT = int(os.environ.get("AGENT_CMD_TIMEOUT", "120"))
POLL = float(os.environ.get("AGENT_POLL", "30"))
OBSERVATION_LIMIT = 4000

SYSTEM = """You are an autonomous worker. You finish ONE task, then stop.

Reply with a single JSON object and nothing else. No markdown fences, no prose.

{"thought": "<one short sentence>", "action": "<name>", "args": {...}}

Actions:
  {"action":"run",    "args":{"command":"<shell command>"}}
  {"action":"write",  "args":{"path":"<relative path>","content":"<file text>"}}
  {"action":"read",   "args":{"path":"<relative path>"}}
  {"action":"note",   "args":{"text":"<what you learned>"}}
  {"action":"finish", "args":{"summary":"<what you did, 1-3 sentences>"}}

Rules:
* One action per reply. Wait for the observation before choosing the next one.
* Prefer small, checkable steps. Read before you write. Verify what you changed.
* Never invent command output. If a command fails, read the error and adapt.
* Stay inside the workspace. Do not touch anything outside it.
* If the task is impossible or unsafe, use finish with a summary saying why.
"""

# Commands are refused when they match any of these. This is a floor, not a
# sandbox: a determined model can still express harm in a way no regex catches,
# which is why the environment is scrubbed below and the journal keeps every
# step. Treat the worker as a capable intern, not as a security boundary.
DANGEROUS = [
    r":\(\)\s*\{",                                   # fork bomb
    r"\brm\s+(-[a-zA-Z]*\s+)*-\S*\s*/\s*$",          # rm ... /
    r"\brm\s+-rf\s+/(\s|$)",
    r"\bmkfs(\.|\s)", r"\bdd\s+if=", r">\s*/dev/(sd|nvme|hd)",
    r"\b(shutdown|reboot|poweroff|halt)\b",
    r"\bcurl\b[^|]*\|\s*(sudo\s+)?(ba|z|)sh",
    r"\bwget\b[^|]*\|\s*(sudo\s+)?(ba|z|)sh",
    r"\bsudo\b", r"\bchmod\s+-R\s+777\s+/", r"\bchown\s+-R\b.*\s/(\s|$)",
    r"\bhistory\s+-c\b", r"\bgit\s+push\b.*--force",
    # Secrets: never let a shell command read the files that hold credentials.
    # Everything the model is shown also goes to the model provider, so a key
    # that gets `cat`-ed into an observation has left the machine.
    r"(?:\.env\b|\.env\.|\.encryption-key|\.llm-gateway|env\.sh|\.ssh/|\.aws/|\.npmrc|\.git-credentials|\.pem\b|id_rsa|id_ed25519)",
    r"\bprintenv\b",                                 # dump the whole environment
    r"(?:^|[|;&]\s*)env\s*(?:$|[|;&])",               # bare `env` as a command
    r"\bsecurity\s+find-(?:generic|internet)-password",
]

# Paths the worker may never read or write, even inside the workspace. A task
# that asks for one of these is refused and journalled.
SECRET_NAMES = {
    ".env", ".env.local", ".env.production", ".encryption-key", ".npmrc",
    ".git-credentials", "id_rsa", "id_ed25519", "env.sh",
}
SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
SECRET_PARTS = (".ssh", ".aws", ".gnupg", ".llm-gateway")

DONE, FAILED, RUNNING, PENDING = "done", "failed", "running", "pending"


# ---------------------------------------------------------------- utilities
def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def say(msg: str) -> None:
    print(f"[{now()}] {msg}", flush=True)


def journal(record: dict) -> None:
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": now(), **record}) + "\n")


def save_task(task: dict) -> None:
    """Write the task atomically so a crash mid-write cannot corrupt it."""
    path = STATE / f"{task['id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(task, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def trim(messages: list[dict]) -> list[dict]:
    """Keep the prompt small: system + goal + the last few observations."""
    if len(messages) <= 9:
        return messages
    return messages[:2] + messages[-6:]


# ---------------------------------------------------------------- model call
def chat(messages: list[dict], retries: int = 5) -> str:
    payload = {
        "model": MODEL,
        "messages": trim(messages),
        "temperature": 0.2,
        "max_tokens": 1500,
    }
    body = json.dumps(payload).encode()
    headers = {"content-type": "application/json"}
    if API_KEY:
        headers["authorization"] = f"Bearer {API_KEY}"
    url = BASE_URL.rstrip("/") + "/chat/completions"

    last = ""
    for attempt in range(retries):
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=240) as res:
                data = json.loads(res.read().decode())
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as err:
            detail = err.read().decode(errors="replace")[:300]
            last = f"HTTP {err.code}: {detail}"
            # 429 is the normal state of a free tier. Wait it out.
            if err.code in (408, 409, 429, 500, 502, 503, 504) and attempt < retries - 1:
                wait = err.headers.get("retry-after")
                wait = float(wait) if wait and wait.isdigit() else min(2 ** attempt * 5, 120)
                say(f"model busy ({err.code}), waiting {wait:.0f}s")
                time.sleep(wait)
                continue
            raise RuntimeError(last)
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            last = str(err)
            if attempt < retries - 1:
                wait = min(2 ** attempt * 5, 120)
                say(f"model unreachable ({err}), retrying in {wait:.0f}s")
                time.sleep(wait)
                continue
            raise RuntimeError(last)
    raise RuntimeError(last or "model call failed")


def parse_action(text: str) -> dict:
    """Pull the first JSON object out of whatever the model said."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    raise ValueError(f"model did not return JSON: {text[:200]}")


# ------------------------------------------------------------------ actions
def safe_path(raw: str) -> Path:
    path = (WORKSPACE / raw).resolve()
    # relative_to, not startswith: `/w/chat` is a string prefix of `/w/chat-2`,
    # so a prefix check lets a sibling directory through.
    try:
        path.relative_to(WORKSPACE)
    except ValueError:
        raise ValueError(f"path outside the workspace: {raw}") from None
    if path.name in SECRET_NAMES or path.name.endswith(SECRET_SUFFIXES):
        raise ValueError(f"refusing to touch a credentials file: {raw}")
    if any(part in SECRET_PARTS for part in path.parts):
        raise ValueError(f"refusing to touch a credentials directory: {raw}")
    return path


def child_env() -> dict[str, str]:
    """Environment for a model-chosen command: paths and locale, no secrets.

    Without this the child inherits GEMINI_API_KEY, ANTHROPIC_AUTH_TOKEN and
    anything else exported for the gateway, so a single `printenv` in a command
    would post them into the model's context (and therefore to the provider).
    """
    keep = {
        key: os.environ[key]
        for key in ("PATH", "HOME", "LANG", "LC_ALL", "TERM", "SHELL", "PWD",
                    "TMPDIR", "USER", "LOGNAME", "VIRTUAL_ENV")
        if key in os.environ
    }
    keep.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
    return keep


def blocked(command: str) -> str | None:
    for pattern in DANGEROUS:
        if re.search(pattern, command, re.IGNORECASE):
            return pattern
    return None


def act(action: str, args: dict) -> tuple[str, bool]:
    """Run one action. Returns (observation, finished)."""
    if action == "run":
        command = str(args.get("command", "")).strip()
        if not command:
            return "error: empty command", False
        hit = blocked(command)
        if hit:
            return f"refused: command matches blocked pattern {hit!r}", False
        say(f"$ {command}")
        try:
            proc = subprocess.run(
                command, shell=True, cwd=WORKSPACE, capture_output=True,
                text=True, timeout=CMD_TIMEOUT, env=child_env(),
            )
        except subprocess.TimeoutExpired:
            return f"error: timed out after {CMD_TIMEOUT}s", False
        out = (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
        out = out.strip() or "(no output)"
        if len(out) > OBSERVATION_LIMIT:
            out = out[:OBSERVATION_LIMIT] + f"\n…[truncated {len(out) - OBSERVATION_LIMIT} chars]"
        return f"exit={proc.returncode}\n{out}", False

    if action == "write":
        try:
            path = safe_path(str(args.get("path", "")))
        except ValueError as err:
            return f"error: {err}", False
        content = str(args.get("content", ""))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        say(f"wrote {path.relative_to(WORKSPACE)} ({len(content)} bytes)")
        return f"wrote {path.relative_to(WORKSPACE)} ({len(content)} bytes)", False

    if action == "read":
        try:
            path = safe_path(str(args.get("path", "")))
        except ValueError as err:
            return f"error: {err}", False
        if not path.is_file():
            return f"error: not a file: {args.get('path')}", False
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > OBSERVATION_LIMIT:
            text = text[:OBSERVATION_LIMIT] + "…[truncated]"
        return text, False

    if action == "note":
        say(f"note: {args.get('text', '')}")
        return "noted", False

    if action == "finish":
        return str(args.get("summary", "finished")), True

    return (
        f"error: unknown action {action!r}; use run, write, read, note or finish",
        False,
    )


# -------------------------------------------------------------------- tasks
def recover() -> None:
    """A task left in `running` means the worker died mid-task."""
    for path in sorted(STATE.glob("*.json")):
        try:
            task = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if task.get("status") == RUNNING:
            task["status"] = PENDING
            task["messages"].append(
                {"role": "user", "content": "The worker restarted. Continue the task."}
            )
            save_task(task)
            say(f"resumed {task['id']}")


def load_queue() -> list[dict]:
    TASKS.mkdir(parents=True, exist_ok=True)
    tasks = []
    for path in sorted(TASKS.glob("*.json")):
        try:
            spec = json.loads(path.read_text())
        except json.JSONDecodeError as err:
            say(f"skipping {path.name}: {err}")
            continue
        task_id = spec.get("id") or path.stem
        state_file = STATE / f"{task_id}.json"
        if state_file.exists():
            continue  # already known; its live state lives in STATE
        task = {
            "id": task_id,
            "goal": spec["goal"],
            "status": PENDING,
            "steps": 0,
            "created": now(),
            "started": None,
            "finished": None,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"TASK:\n{spec['goal']}"},
            ],
        }
        save_task(task)
        say(f"queued {task_id}")
        tasks.append(task)
    return tasks


def next_pending() -> dict | None:
    for path in sorted(STATE.glob("*.json")):
        try:
            task = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        if task.get("status") == PENDING:
            return task
    return None


def run_task(task: dict, max_steps: int) -> None:
    deadline = time.time() + MAX_MINUTES * 60
    task["status"] = RUNNING
    task["started"] = task.get("started") or now()
    save_task(task)
    say(f"start {task['id']} — {task['goal'][:70]}")

    while task["steps"] < max_steps:
        if time.time() > deadline:
            task["status"] = FAILED
            task["error"] = f"time limit ({MAX_MINUTES:.0f} min) reached"
            save_task(task)
            say(f"failed {task['id']}: time limit")
            return

        try:
            reply = chat(task["messages"])
        except RuntimeError as err:
            # Model-side failure: leave the task pending so a restart retries it.
            task["status"] = PENDING
            task["error"] = str(err)
            save_task(task)
            say(f"paused {task['id']}: {err}")
            return

        task["messages"].append({"role": "assistant", "content": reply})
        try:
            call = parse_action(reply)
        except ValueError as err:
            observation = f"error: {err}. Reply with one JSON object only."
            journal({"task": task["id"], "step": task["steps"], "parse_error": str(err)})
            task["steps"] += 1
            task["messages"].append({"role": "user", "content": observation})
            save_task(task)
            continue

        action = str(call.get("action", "")).strip()
        args = call.get("args") or {}
        thought = str(call.get("thought", ""))[:200]
        observation, finished = act(action, args)
        task["steps"] += 1

        journal({
            "task": task["id"], "step": task["steps"], "thought": thought,
            "action": action, "args": {k: (v[:200] if isinstance(v, str) else v) for k, v in args.items()},
            "observation": observation[:1000],
        })

        if finished:
            task["status"] = DONE
            task["summary"] = observation
            task["finished"] = now()
            save_task(task)
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / f"{task['id']}.md").write_text(
                f"# {task['id']}\n\n**Goal**\n{task['goal']}\n\n**Summary**\n{observation}\n\n"
                f"**Steps** {task['steps']} · started {task['started']} · finished {task['finished']}\n",
                encoding="utf-8",
            )
            say(f"done {task['id']} in {task['steps']} steps")
            return

        task["messages"].append({"role": "user", "content": f"OBSERVATION:\n{observation}"})
        save_task(task)

    task["status"] = FAILED
    task["error"] = f"step limit ({max_steps}) reached"
    save_task(task)
    say(f"failed {task['id']}: step limit")


def main() -> int:
    parser = argparse.ArgumentParser(description="Durable task worker for a free model.")
    parser.add_argument("--once", action="store_true", help="drain the queue, then exit")
    parser.add_argument("--max-steps", type=int, default=MAX_STEPS)
    args = parser.parse_args()

    for folder in (TASKS, STATE, OUT):
        folder.mkdir(parents=True, exist_ok=True)

    recover()
    load_queue()

    idle_rounds = 0
    while True:
        task = next_pending()
        if task:
            idle_rounds = 0
            run_task(task, args.max_steps)
            continue
        if args.once:
            say("queue empty")
            return 0
        idle_rounds += 1
        if idle_rounds % 20 == 1:
            say("waiting for tasks…")
        time.sleep(POLL)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say("stopped by hand; state is on disk")
        sys.exit(0)
