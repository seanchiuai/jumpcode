# Workspaces Always Launch Fresh

Launching a workspace always starts clean Claude agents with the same saved config. There is no session resume. Closing a workspace closes the window; reopening it is a fresh start.

## Why

Resume (restoring each pane's prior Claude session) was considered and dropped — it adds per-role session-id tracking and brittle dependence on Claude Code's resume behavior. Instead, continuity comes from **durable sources**: Linear (tasks/status) and the dispatch log (who-said-what). A fresh agent reconstructs context by reading those, which is more robust than restoring possibly-stale agent memory and keeps the launcher simple.

## Consequence

The dispatch log earns its keep here: it is the thing a fresh orchestrator/lead reads to learn what happened before the window was closed. This is why dispatches are durably logged (ADR 0002) even though delivery is live.
