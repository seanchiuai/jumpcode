# Webapp Cockpit Launch Prompts

`start-webapp` launches the four visible Claude Code panes **fresh** (no session resume,
leads without `-p`) and injects an initial prompt into each. This file documents that
prompt so the doc and the launcher stay in sync — if you change one, change the other.
See [`../../bin/start-webapp`](../../bin/start-webapp) for the live source.

Each pane is launched with `claude`, given a stable `@cockpit_role` tmux option (so
`dispatch` can wake it), then sent this prompt (with `$role` = its role name):

```text
You are the webapp workspace $role. Read your charter
.agent-cockpit/roles/$role.md and the shared protocol
.agent-cockpit/roles/_PROTOCOL.md. Projects and tasks live in LINEAR — use the
Linear MCP as the system of record; the cockpit keeps no local copy. Check your
inbox now: ./.agent-cockpit/bin/dispatch inbox $role. Then wait — when someone
dispatches you, this pane is woken automatically. Send messages with
./.agent-cockpit/bin/dispatch send --from $role --to <role> [--task LINEAR-ID] BODY.
```

The four roles launched:

```text
orchestrator    full-height right pane
frontend-lead   left top
backend-lead    left middle
qa-lead         left bottom
```

Each agent then reorients from durable sources — its charter, the shared protocol,
Linear, and the dispatch log (`./.agent-cockpit/bin/dispatch log 40`) — and waits to be
woken by a dispatch. Leads report back with `--kind report-done` / `report-blocked`
dispatches to the orchestrator and update the Linear issue.
