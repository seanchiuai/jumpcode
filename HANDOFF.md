# Agent Cockpit Handoff

## What this is

A minimal local orchestration system for `workspace-macbook`. It owns only the delivery
layer — visible panes, live wake, and a durable dispatch log. Projects and tasks live in
Linear. See [`CONTEXT.md`](CONTEXT.md) for canonical terms and [`docs/adr/`](docs/adr/)
for the decisions.

## Core primitive

```text
dispatch   one directed message that is BOTH delivered live (wake into the
           recipient's pane) AND appended to the durable dispatch log
```

The only state file is append-only JSONL under `.agent-cockpit/state/`:

```text
.agent-cockpit/state/dispatches.jsonl
```

(plus internal `state/counters.json` and `state/.lock`). Human-readable feed:
`.agent-cockpit/shared/conversation.log`.

## Current command surface

```bash
./.agent-cockpit/bin/dispatch send --from R --to R [--project P] [--task T] \
    [--subject S] [--kind request|reply|report-done|report-blocked|notice] [--no-wake] BODY
./.agent-cockpit/bin/dispatch inbox R [--json]
./.agent-cockpit/bin/dispatch show DID [--json]
./.agent-cockpit/bin/dispatch log [N]
./.agent-cockpit/bin/status        # open loops: requests with no matching report (+ pane state)
./.agent-cockpit/bin/convo [lines]
./.agent-cockpit/bin/start-webapp
```

## First workspace

The first configured workspace is `webapp`:

```text
.agent-cockpit/workspaces/webapp/WORKSPACE.md
.agent-cockpit/workspaces/webapp/LAUNCH_PROMPTS.md
```

Roles are thin **charters** plus one shared protocol. `start-webapp` discovers the roster
from the prompt folder; adding/removing a `*.md` charter adds/removes a lead.

```text
.agent-cockpit/roles/_PROTOCOL.md
.agent-cockpit/roles/🧭 orchestrator.md
.agent-cockpit/roles/🎨 frontend-lead.md
.agent-cockpit/roles/🛠 backend-lead.md
.agent-cockpit/roles/✅ qa-lead.md
.agent-cockpit/roles/🚀 devops-lead.md
.agent-cockpit/roles/🔌 mcp-lead.md
```

`start-webapp` builds one tmux session with two windows:

```text
macbook-webapp:roles    Claude Code/Codex panes (launched fresh, no -p on leads)
                        orchestrator = full-height right pane
                        leads = stacked left column
macbook-webapp:monitor  feed/status logs when needed
```

Each pane carries a machine-readable `@cockpit_role` option (e.g. `orchestrator`,
`backend-lead`) which is how `dispatch send` targets the right pane for a wake — Claude
overwrites the visible pane title, so wake targeting never relies on it.

## Important design decisions

- Projects and tasks live in **Linear** (ADR 0003); no local task/run/project registry.
- A **dispatch** unifies live wake + durable log (ADR 0002), replacing the old mailbox.
- Topology is hub-and-spoke with the orchestrator as hub (ADR 0001).
- Workspaces always launch **fresh** — no session resume (ADR 0004).
- Durable visible roles stay at orchestrator/lead level; subagents are invoked by leads
  as a tool, not run as permanent panes.
- v1 has no liveness daemon and no eval/rating harness (deferred).

## Verification

```bash
python3 .agent-cockpit/tests/test_cockpit.py
python3 -m py_compile .agent-cockpit/bin/cockpit
bash -n .agent-cockpit/bin/dispatch .agent-cockpit/bin/convo .agent-cockpit/bin/status .agent-cockpit/bin/start-webapp
```
