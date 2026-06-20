# Linear is the System of Record for Projects and Tasks

> **Status: Superseded by ADR 0006** (superseded 2026-06-17 — GitHub issues are now the system of record). This record is kept for history; the body below describes the prior decision.

Projects and tasks live in **Linear**, not in the jumpcode. A project is a Linear project; a task is a Linear issue. The orchestrator (and Hermes) read/write them via Linear. The jumpcode deliberately keeps **no** local project/task/run registry.

## Why

A local JSONL task/run registry was built early, then retired. It over-structured the system and duplicated what Linear already does well. Linear provides just-enough structure, and Hermes can customize it freely. One source of truth, no sync problem.

## What the jumpcode still owns

- Visible-pane orchestration (the tmux role grid: orchestrator + team leads)
- **Wake** / dispatch *delivery* (injecting prompts into idle panes)
- The **dispatch log** — the durable record of who-said-what between actors (Linear does not capture inter-agent messages)
- Workspace **config** — charters, which leads exist, launch behavior

## Consequences

- The `run` and `task` CLI commands and their JSONL (`runs.jsonl`, `tasks.jsonl`) are obsolete. Audit items about the local task registry (id-collision, current_run scoping) no longer apply to project/task state — only to the dispatch log, if anything.
- A lead's DONE/BLOCKED **report** is no longer a local registry entry. It becomes (1) a dispatch to the orchestrator (logged) and (2) a Linear status/comment update.
- **Completion is informal.** There is no jumpcode "project done" event. Work ends when the Human closes the live workspace window (see workspace launch modes). Linear holds whatever status is meaningful.
- Both the orchestrator pane and Hermes need Linear access (Linear MCP).
