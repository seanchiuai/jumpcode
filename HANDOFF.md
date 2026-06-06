# Agent Cockpit Handoff

## What this is

A minimal local orchestration system for `workspace-macbook`, modeled after the useful core of BridgeSwarm without copying proprietary BridgeSpace code.

## Built primitives

```text
run     top-level run ledger
任务/task    task registry
mail    structured mailbox
report  machine-readable DONE/BLOCKED reports
```

All state is append-only JSONL under `.agent-cockpit/state/`.

## Current command surface

```bash
./.agent-cockpit/bin/run start|current|note|checkpoint|summary
./.agent-cockpit/bin/task create|list|show|start|done|block
./.agent-cockpit/bin/mail send|inbox|show|reply
./.agent-cockpit/bin/report done|blocked
./.agent-cockpit/bin/ask <agent> <message...>
./.agent-cockpit/bin/convo [lines]
./.agent-cockpit/bin/status
./.agent-cockpit/bin/start-webapp
```

## First workspace

The first configured workspace is `webapp`:

```text
.agent-cockpit/workspaces/webapp/WORKSPACE.md
.agent-cockpit/workspaces/webapp/workspace.json
.agent-cockpit/workspaces/webapp/LAUNCH_PROMPTS.md
workspaces/webapp/README.md
```

Visible role prompts are:

```text
.agent-cockpit/roles/orchestrator.md
.agent-cockpit/roles/frontend-lead.md
.agent-cockpit/roles/backend-lead.md
.agent-cockpit/roles/qa-lead.md
```

`start-webapp` uses two tmux windows:

```text
macbook-webapp:roles    four Claude Code role panes only
                        orchestrator = full-height right pane
                        leads = stacked left column
macbook-webapp:monitor  feed/status logs when needed
```

The orchestrator pane has a stable tmux border label: `🧭 ORCHESTRATOR — RIGHT SIDE`. Use the border label/location rather than normal pane title; Claude Code changes pane titles while it works.

## Important design decisions

- No liveness daemon in v1.
- No eval/rating harness in v1.
- Reports include `checks_run` so eval can be layered later.
- Durable visible roles should stay at orchestrator/lead level.
- Ephemeral engineers/specialists should be spawned inside Claude Code by leads, not as permanent cockpit panes.
- `mail` is the source of truth. `ask` is only a delivery/logging convenience wrapper.

## Verification

Tests:

```bash
python3 .agent-cockpit/tests/test_cockpit.py
```

Syntax checks:

```bash
python3 -m py_compile .agent-cockpit/bin/cockpit
bash -n .agent-cockpit/bin/run .agent-cockpit/bin/task .agent-cockpit/bin/mail .agent-cockpit/bin/report .agent-cockpit/bin/ask .agent-cockpit/bin/convo .agent-cockpit/bin/status
```
