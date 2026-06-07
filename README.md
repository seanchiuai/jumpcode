# Local Agent Cockpit Orchestration

This directory is the local, project-owned orchestration layer for `workspace-macbook`.
It is intentionally small: no daemon, no database, no cloud dependency. It owns only the
*delivery* layer — visible panes, live wake, and a durable dispatch log. Projects and
tasks live in **Linear**, not here.

For canonical terms see [`CONTEXT.md`](CONTEXT.md); for the decisions behind the design
see [`docs/adr/`](docs/adr/) (0001–0004). Those are the authority if anything here
conflicts.

## The one mental model

> Human + Hermes drive the **orchestrator**, which commands its **team leads**, which
> invoke general **subagents** as a tool. **Projects and tasks live in Linear.** The
> cockpit only moves messages between visible panes and remembers what was said.

## Core primitive: the dispatch

A **dispatch** (ADR 0002) is one directed message that does two things at once:

- **Delivered live** — a prompt is injected ("wake") into the recipient's tmux pane,
  targeted by its stable `@cockpit_role` option, so the agent gets to work immediately.
- **Appended to the durable dispatch log** — so a restarted agent, or Human/Hermes, can
  reconstruct what was asked and what happened.

There is a single CLI verb, `dispatch`:

```bash
# send (live wake + durable log)
./.agent-cockpit/bin/dispatch send \
  --from <role> --to <role> \
  [--project <LINEAR-PROJECT>] [--task <LINEAR-ISSUE>] \
  [--subject "<subject>"] \
  [--kind request|reply|report-done|report-blocked|notice] \
  [--no-wake] \
  "<body>"

# inspect
./.agent-cockpit/bin/dispatch inbox <role> [--json]   # dispatches addressed to a role
./.agent-cockpit/bin/dispatch show <dispatch-id> [--json]
./.agent-cockpit/bin/dispatch log [N]                 # human-readable feed (default 40)
./.agent-cockpit/bin/dispatch status [--json]         # open loops: requests with no matching report (+ pane state)

# monitor
./.agent-cockpit/bin/health [--json]                  # per-role: alive · working/waiting/idle · runtime · subagents
./.agent-cockpit/bin/peek <role> [lines]              # read-only view of a role's pane (never wakes it)
```

Default `--kind` is `request`. Use `reply` to answer one, `notice` for an FYI,
`report-done`/`report-blocked` when closing out a task — pass `--reply-to <request
dispatch-id>` on reports so `dispatch status` pairs them and closes the loop. `--no-wake`
logs without injecting (scripted/batch use); normal sends always wake.

## State

The only state file is append-only JSONL:

```text
.agent-cockpit/state/dispatches.jsonl
```

(plus an internal `state/counters.json` for id reservation and a `state/.lock`).
Human-readable activity is mirrored to:

```text
.agent-cockpit/shared/conversation.log
```

## Convenience wrappers

- `status` — alias for `dispatch log` (the recent dispatch feed).
- `convo [lines]` — tails the human-readable conversation log (default 80).
- `start-webapp` — launches the `webapp` workspace tmux grid (fresh agents).

## Where work lives: Linear

A **project** is a Linear project; a **task** is a Linear issue (ADR 0003). Agents read
and update them via the Linear MCP. The cockpit keeps **no** local copy of project/task state.
"Done" is informal: update the Linear issue and send a `report-done` dispatch.

## Roles and topology

- **Orchestrator** — one per workspace, the single accountable agent; a visible right
  pane. Receives goals from Human/Hermes, decomposes into Linear issues, commands leads.
- **Team leads** — durable, repo-specific accountable agents (e.g. frontend-lead,
  backend-lead, qa-lead); visible left panes, launched without `-p`.
- **Subagents** — general, repo-agnostic Claude Code subagents (e.g. a code reviewer) a
  lead invokes as a tool. Not panes, not an accountability layer.

Topology is hub-and-spoke (ADR 0001): Human may type into any pane (orchestrator or any
lead); Hermes talks only to the orchestrator; there is no lead↔lead channel — a lead
asks the orchestrator to **relay**.

## Continuity: always fresh

Launching a workspace always starts clean Claude agents with no session resume (ADR
0004). A fresh agent reconstructs context from the durable sources — Linear and the
dispatch log. "Close workspace" = close the window; the saved config persists.

## Design constraints

- A local `workspace-macbook` tool, not a BuilderBase repo tool; not in system root.
- Visible panes are durable accountability roles only (orchestrator and leads).
- Subagents are invoked internally by the responsible lead, not run as permanent panes.
- v1 has no liveness daemon and no eval/rating harness (both deferred).

## Tests

```bash
python3 .agent-cockpit/tests/test_cockpit.py
```
