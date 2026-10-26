---
description: Write a handoff brief so the next session can pick up mid-task
allowed-tools: Read, Write, Edit, Bash(git:*), Bash(date:*), Bash(ls:*)
---

Write a handoff brief. Do not ask me anything first — read what you need, then write it.

1. Read the current `HANDOFF.md`. If it exists, append it verbatim to `HANDOFF-LOG.md`
   under a heading of its own date (create the file if missing), then replace
   `HANDOFF.md` with the new brief. Never delete history from the log.

2. Write `HANDOFF.md` with exactly these sections, in this order:

```
# Handoff — <YYYY-MM-DD HH:MM>

## Where the project is
Two or three sentences. The state, not the history.

## Done and verified
Bullets. Only work you actually verified — say how it was verified.

## In flight
Anything half-finished, with the exact file and the exact next edit.

## Next
The next 3 things, most important first. One line each, concrete enough to start.

## Avoid
Traps, wrong turns already taken, commands that break something, dead ends.
Say why, so the next session doesn't have to rediscover it.

## Commands and paths
The handful a new session needs to orient itself. Literal, copy-pasteable.

## Open questions for the user
Anything waiting on a decision from me.
```

3. Rules for the brief: facts, not reassurance. If something failed, it goes in with
   the failure. If a number came from one short run, say the sample is short. No
   praise, no summary of this conversation.

4. Finish by printing a 6-line recap I can paste into a fresh chat, and the command
   to resume: `/resume`.
