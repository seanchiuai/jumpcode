# Jumpcode

A behavioral contract for multi-agent software delivery, expressed as native Claude Code agent
definitions. Sean drives a workspace's orchestrator (his main session), which spawns specialist
subagents and continues them with `SendMessage`. Projects and tasks live in GitHub Issues;
Claude Code's runtime provides the orchestration substrate (subagents, Agent view, worktrees,
resume).

## Language

**Project**:
A collection of tasks sharing one goal, tracked as a **GitHub repo/milestone**. A workspace can
have several active at once; its orchestrator interleaves them. Jumpcode keeps **no** project
registry — GitHub Issues are the system of record (ADR 0006).
_Avoid_: run, registry

**Task**:
A unit of work — a **GitHub issue**. Lives in GitHub, not Jumpcode. Read/written via the `gh`
CLI.
_Avoid_: ticket

**Workspace**:
A goal bound to a repo and a git worktree (`<repo>/.worktrees/<slug>`), plus the installed agent
pack the orchestrator commands. There is no saved-config engine and no launcher: a workspace is
brought to life by starting Claude Code in the worktree (that session is the orchestrator) with
the pack installed. Agents orient from GitHub Issues + git state, never from prior agent memory.
_Avoid_: session, template, instance, run

**Repo**:
The codebase a workspace operates on. One repo can host multiple workspaces (worktrees).

## Roles

**Orchestrator**:
The single accountable agent — Sean's **main Claude Code session**, rooted in the target
worktree. Receives goals from Sean, decomposes them into GitHub Issues, spawns and commands
specialists, and is the only relay between them. Non-coding; never drives a browser. Not a
subagent — governed by `roles/orchestrator.md`, which the session reads at kickoff.

**Specialist** (coding lead / reviewer / tester):
A named accountable subagent defined in `.claude/agents/*.md`, spawned by the orchestrator with
the Agent tool for a scoped task. Owns a territory, returns a done/blocked report, and cannot
address another specialist (it asks the orchestrator to relay). The coding leads
(`backend-lead`, `frontend-lead`, `devops-lead`) build; the **reviewer** (`code-reviewer`) is
the independent merge-gate; the **tester** (`qa-tester`) is independent verification.
_Avoid_: pane, team lead pane

**Reviewer / Tester (browser owners)**:
`code-reviewer` and `qa-tester` are the **only** agents that drive a browser (Claude in Chrome /
Playwright). They own all browser automation — rendered/public output, e2e, smoke flows.

**Relay**:
The pattern by which one specialist reaches another: it asks the orchestrator, which decides
whether to forward. There is no direct specialist-to-specialist channel — native subagents
cannot address each other.

## Communication

**Spawn**:
The orchestrator starting a specialist with the Agent tool, handing it the task, acceptance
criteria, and issue number. The specialist runs (background by default) and returns its report
as its final message.

**SendMessage**:
The native tool the orchestrator uses to continue a running or finished specialist — a nudge,
correction, or next step — addressing it by agent id or name. The specialist already holds its
context; there is no keystroke injection and no inbox to poll.
_Avoid_: dispatch, mail, wake

**Report**:
A specialist's returned final message — explicitly *done* (summary, what changed, checks run,
concerns, next step) or *blocked* (blocker, why, what was tried, what it needs) — mirrored to
the GitHub issue.

**Agent view / FleetView**:
The native monitor (`claude agents`, `--json`, `claude logs <id>`, `claude attach <id>`) showing
which specialists are working / idle / done / failed. Replaces the retired `health`/`peek`/
`fleet` pane monitors.

## Continuity

**Durable truth**:
GitHub Issues (what the work is) + git/PR state (what is built). The runtime's agent/task state
(`~/.claude/jobs/<id>/state.json`) is ephemeral and session-local — never treated as truth.

**Recovery**:
A fresh session rebuilds from `gh issue view` + `git`/`gh pr` state; `claude --resume` restores
a prior session when its own reasoning is worth keeping.

## Configuration

**Agent definition**:
A `.claude/agents/*.md` file: YAML frontmatter (`name`, `description`, `tools` /
`disallowedTools`, `color`) + a Markdown system prompt. The `tools`/`disallowedTools` lists
**enforce** the browser boundary. This is the native replacement for the old per-lead charter.

**Shared protocol**:
`roles/_PROTOCOL.md` — the interaction rules common to every role (spawn/report/relay, the
browser boundary, confirm-the-target, recovery). Referenced by every agent so the rules live in
one place.

**Guardrails**:
Territory boundaries in an agent's definition. The **browser boundary is enforced** (frontmatter
tool lists); the territory (which paths a lead edits) is a convention the agent honors and relays
across through the orchestrator.
