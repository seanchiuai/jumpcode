# GitHub Issues is the System of Record for Projects and Tasks

Status: **Accepted** (2026-06-17). **Supersedes the prior system-of-record decision.**

Projects and tasks live in **GitHub issues**, not in the jumpcode. A task is a GitHub issue in the relevant repo; an issue number (`#42`) is its id. The orchestrator reads/writes them via the **`gh` CLI**. The jumpcode deliberately keeps **no** local project/task/run registry.

## Why

We adopted GitHub issues as the system of record — they sit next to the code the team actually changes and are reachable from any pane through the already-present `gh` CLI, with no extra MCP wiring. GitHub provides just-enough structure (issues, labels, milestones, comments), one source of truth, no sync problem. This refines, rather than overturns, the standing principle: *the tracker is external; the jumpcode owns coordination, not task state.* Only the tracker itself changed.

## What the jumpcode still owns

- Visible-pane orchestration (the tmux role grid: orchestrator + team leads)
- **Wake** / dispatch *delivery* (injecting prompts into idle panes)
- The **dispatch log** — the durable record of who-said-what between actors (GitHub does not capture inter-agent messages)
- Workspace **config** — charters, which leads exist, launch behavior

## Consequences

- Dispatches reference tasks by issue number: `--task #42` (or the bare number). A lead's DONE/BLOCKED **report** becomes (1) a dispatch to the orchestrator (logged) and (2) a GitHub issue status/comment update via `gh`.
- **Completion is informal.** There is no jumpcode "project done" event. Work ends when the Human closes the live workspace window; GitHub holds whatever issue state is meaningful.
- The orchestrator pane needs `gh` authenticated. A Codex lead needs `gh` available in its environment.
- **Repo guardrail:** file issues in the workspace's own repo; never invent or auto-create a repo. If the target repo is unspecified, **ask which repo** before filing.
- A workspace may still **override** the tracker via its overlay (e.g. a different repo, or another tracker entirely) — GitHub issues is the default, not a hard requirement.
