# Jumpcode

The local, file-based multi-agent orchestration system for `workspace-macbook`. Sean (the Human) drives a workspace's orchestrator, which commands its team leads, which invoke general subagents as tools. Projects and tasks live in GitHub issues; the jumpcode owns the visible panes, dispatch delivery, the dispatch log, and workspace config.

## Language

**Project**:
A collection of tasks sharing one goal (e.g. "set up MCP"), tracked as a **GitHub repo/milestone**. A workspace can have several active at once; its orchestrator interleaves them. The jumpcode does **not** maintain its own project registry — GitHub issues are the system of record (see ADR 0006).
_Avoid_: run, registry

**Task**:
A unit of work — a **GitHub issue**. Lives in GitHub, not the jumpcode. The orchestrator reads/writes it via the `gh` CLI.
_Avoid_: ticket

**Workspace**:
A named, saved, reusable configuration bound to a repo — one orchestrator plus multiple team leads and their prompts/agent config. A repo can hold multiple workspaces, but in practice usually one; concurrency lives at the project level (one workspace's orchestrator can work several projects at once), not the workspace level. There are no templates: you create a new workspace from scratch or by copying an existing one. The workspace *is* the saved config; launching it brings it to life as visible panes — there is no separate noun for the running instance. Launching always starts **fresh**: clean Claude agents with the same config, no session resume. Closing a workspace closes the window; the saved config persists. Agents orient from GitHub issues + the dispatch log, never from prior agent memory. A workspace does **not** bind to a single repo as its tracker: the orchestrator has general `gh` access and is told which repo each task belongs to. Created fresh or by copying an existing workspace (no templates).
_Avoid_: project, session, template, instance

**Repo**:
The codebase a workspace operates on. One repo can have multiple workspaces.

## Roles

**Orchestrator**:
The single accountable agent in a workspace. Receives goals from Sean, decomposes them into tasks, commands all team leads, and is the only relay between leads. One per workspace; a visible pane.

**Team Lead**:
A durable accountable agent owning a discipline that is **specific to the repo** (e.g. backend lead, frontend lead, MCP lead, qa lead). A visible CLI pane, run without `-p` so Human can see and interact with it. Receives commands from the orchestrator, reports back, and may request the orchestrator relay to another lead; cannot talk to other leads directly. Has its own charter doc (CLAUDE.md-style) defining its domain, how it interacts with the orchestrator, and its guardrails. Invokes subagents as a tool.
_Avoid_: specialist (do not call a lead a "backend specialist" — it is the backend **lead**)

**Subagent**:
A **general, repo-agnostic** Claude Code subagent (e.g. code reviewer) that a team lead invokes as a tool to help with a task. Ephemeral, not a pane, not an accountability layer, no `-p`. The Human (Sean) never addresses subagents directly. This is what was loosely called a "specialist".
_Avoid_: specialist

**Relay**:
The pattern by which one lead reaches another: it asks the orchestrator, which decides whether to forward. There is no direct lead-to-lead channel.

## Communication

**Dispatch**:
A directed message from one actor to another. A single dispatch does two things at once: it is delivered live (a prompt injected into the recipient's pane so it gets to work immediately) and it is written to the durable dispatch log. The unified replacement for "mail".
_Avoid_: mail, message

**Dispatch log**:
The durable, append-only record of every dispatch. Survives context compaction and lets a lost agent — or Sean — reconstruct what was asked and what happened. Recovery/review tool, not the primary delivery path.

**Wake**:
The live half of a dispatch: a keystroke injection into the recipient's idle Claude pane (targeted by its stable `@role` border label). Necessary because a Claude agent cannot poll its own inbox; it sits idle until something feeds it input.

## Configuration

**Charter**:
A team lead's own thin CLAUDE.md-style doc with four sections: (1) identity + domain, (2) editable territory & guardrails, (3) domain conventions, (4) a pointer to the shared protocol. The common interaction rules (dispatch/report/relay/wake/CLI) live once in the shared protocol, not duplicated per lead. One charter per team lead; written/copied when the workspace is created.

**Shared protocol**:
The single doc holding the interaction rules common to all leads (how to receive a dispatch, report DONE/BLOCKED, request a relay, the wake mechanism, CLI usage). Referenced by every charter so the rules live in one place and never drift.

**Guardrails**:
The constraints in a lead's charter — editable vs off-limits areas, dos and don'ts. **Soft (advisory) in v1**: stated in the charter, not enforced by Claude Code permissions. Hard enforcement (deny rules / hooks) is a later option. The convention: a lead stays in its domain and relays cross-domain work through the orchestrator.
