---
description: Load the handoff brief and continue from where the last session stopped
allowed-tools: Read, Bash(git:*), Bash(ls:*), Bash(tail:*)
---

You are picking up work another session left unfinished. Orient yourself before touching anything.

1. Read `HANDOFF.md`. If it is missing, say so plainly and ask which task I want — do
   not invent a state.
2. Check that the brief still matches reality: `git log --oneline -5`, `git status --short`,
   and read the files the brief names under "In flight". If the brief and the code
   disagree, trust the code and say which line of the brief is stale.
3. Read the last entry of `HANDOFF-LOG.md` only if you need history the brief omits.
4. Then report in five lines or fewer: where things are, what "In flight" means for
   your next edit, and the first thing you are about to do. Stop and wait for my go
   before editing anything, unless the brief's "Next" section is unambiguous.
5. Keep the brief current as you work: when you finish a step that changes the
   "Where the project is" line, update `HANDOFF.md` in the same commit.
