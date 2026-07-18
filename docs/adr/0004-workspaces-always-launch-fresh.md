# Workspaces Always Launch Fresh

> **SUPERSEDED at the mechanism level (2026-07-17) by [ADR 0008](0008-native-claude-code-orchestration.md).**
> The *principle* stands — continuity comes from durable sources, not restored agent memory —
> but the durable source is now GitHub Issues + git state, not the dispatch log, and "fresh
> launch" is just starting a Claude Code session. Native `claude --resume` (see ADR 0005) is the
> opt-in resume path. Kept for history.


Launching a workspace always starts clean Claude agents with the same saved config. There is no session resume. Closing a workspace closes the window; reopening it is a fresh start.

## Why

Resume (restoring each pane's prior Claude session) was considered and dropped — it adds per-role session-id tracking and brittle dependence on Claude Code's resume behavior. Instead, continuity comes from **durable sources**: the external tracker (tasks/status) and the dispatch log (who-said-what). A fresh agent reconstructs context by reading those, which is more robust than restoring possibly-stale agent memory and keeps the launcher simple.

## Consequence

The dispatch log earns its keep here: it is the thing a fresh orchestrator/lead reads to learn what happened before the window was closed. This is why dispatches are durably logged (ADR 0002) even though delivery is live.
