# Jumpcode Handoff

## What this is

A minimal local orchestration system for `workspace-macbook`. It owns only the delivery
layer — visible panes, live wake, and a durable dispatch log. Projects and tasks live in
GitHub issues. See [`CONTEXT.md`](CONTEXT.md) for canonical terms and [`docs/adr/`](docs/adr/)
for the decisions.

## Core primitive

```text
dispatch   one directed message that is BOTH delivered live (wake into the
           recipient's pane) AND appended to the durable dispatch log
```

The only state file is append-only JSONL under `.jumpcode/state/`:

```text
.jumpcode/state/dispatches.jsonl
```

(plus internal `state/counters.json` and `state/.lock`). Human-readable feed:
`.jumpcode/shared/conversation.log`.

## Current command surface

```bash
./.jumpcode/bin/dispatch send --from R --to R [--project P] [--task T] \
    [--subject S] [--kind request|reply|report-done|report-blocked|notice] [--no-wake] BODY
./.jumpcode/bin/dispatch inbox R [--json]
./.jumpcode/bin/dispatch show DID [--json]
./.jumpcode/bin/dispatch log [N]
./.jumpcode/bin/status        # open loops: requests with no matching report (+ pane state)
./.jumpcode/bin/convo [lines]
./.jumpcode/bin/start-webapp
./.jumpcode/bin/jumpcode roles discover --workspace webapp [--json]
```

## First workspace

The first configured workspace is `webapp`:

```text
.jumpcode/workspaces/webapp/WORKSPACE.md
.jumpcode/workspaces/webapp/LAUNCH_PROMPTS.md
```

Roles are thin **charters** plus one shared protocol. `start-webapp` consumes the centralized discovery JSON. **Only the orchestrator launches by default — no pre-generated leads.** Central `$JUMPCODE_HOME/roles` holds *recommended* leads (opt in per-workspace via `enabled_roles`); repo-local `$WORKSPACE_ROOT/.jumpcode/roles` charters launch automatically and overlay prompts by canonical role id; a repo-local `_PROTOCOL.md` overrides central only when present. Adding/removing an overlay `*.md` charter adds/removes a lead; `workspace.json` is settings-only (`workspace_root`, `role_runtimes`, `enabled_roles`) and contains no roster prompts.

```text
.jumpcode/roles/_PROTOCOL.md
.jumpcode/roles/🧭 orchestrator.md
.jumpcode/roles/🎨 frontend-lead.md
.jumpcode/roles/🛠 backend-lead.md
.jumpcode/roles/✅ qa-lead.md
.jumpcode/roles/🚀 devops-lead.md
.jumpcode/roles/🔌 mcp-lead.md
```

`start-webapp` builds one tmux session with two windows:

```text
macbook-webapp:roles    Claude Code/Codex panes (launched fresh, no -p on leads)
                        orchestrator = full-height right pane
                        leads = stacked left columns from prompt-folder discovery
macbook-webapp:monitor  feed/status logs when needed
```

Each pane carries a machine-readable `@jumpcode_role` option (e.g. `orchestrator`,
`backend-lead`) which is how `dispatch send` targets the right pane for a wake — Claude
overwrites the visible pane title, so wake targeting never relies on it.

## Important design decisions

- Projects and tasks live in **GitHub issues** (ADR 0006, superseding ADR 0003); no local task/run/project registry.
- A **dispatch** unifies live wake + durable log (ADR 0002), replacing the old mailbox.
- Topology is hub-and-spoke with the orchestrator as hub (ADR 0001).
- Workspaces always launch **fresh** — no session resume (ADR 0004).
- Durable visible roles stay at orchestrator/lead level; subagents are invoked by leads
  as a tool, not run as permanent panes.
- v1 has no liveness daemon and no eval/rating harness (deferred).

## Verification

```bash
python3 -m unittest discover -s tests
python3 -m py_compile .jumpcode/bin/jumpcode
bash -n .jumpcode/bin/dispatch .jumpcode/bin/convo .jumpcode/bin/status .jumpcode/bin/start-webapp
```
