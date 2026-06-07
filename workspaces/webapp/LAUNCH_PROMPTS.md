# Webapp Cockpit Launch Prompts

`start-webapp` launches the visible Claude Code/Codex panes **fresh** (no session resume,
leads without `-p`) and injects an initial prompt into each. This file documents that
prompt so the doc and the launcher stay in sync — if you change one, change the other.
See [`../../bin/start-webapp`](../../bin/start-webapp) for the live source.

Each pane is launched with its configured runtime, given a stable `@cockpit_role` tmux
option (so `dispatch` can wake it), then sent this prompt (with `$role` = its role name):

```text
You are the webapp workspace $role. You are running from repo/workspace root
$WORKSPACE_ROOT. Read your charter $prompt_file and the shared protocol
$SHARED_PROTOCOL. Projects and tasks live in LINEAR — use the Linear MCP as the system
of record; there is no local task registry. Check your inbox now:
$COCKPIT_BIN/dispatch inbox $role. Then wait — when someone dispatches you, this pane
is woken automatically. Send messages with $COCKPIT_BIN/dispatch send --from $role
--to <role> [--task LINEAR-ID] BODY.
```

The roles launched are the validated discovery result from `cockpit roles discover --workspace webapp --json`:

```text
🧭 orchestrator.md     full-height right pane; dispatch id: orchestrator
🎨 frontend-lead.md    lead pane; dispatch id: frontend-lead
🛠 backend-lead.md     lead pane; dispatch id: backend-lead
✅ qa-lead.md          lead pane; dispatch id: qa-lead
🚀 devops-lead.md      lead pane; dispatch id: devops-lead
🔌 mcp-lead.md         lead pane; dispatch id: mcp-lead
```

Prompt discovery uses central `$COCKPIT_HOME/roles` as the base set, then overlays repo-local `$WORKSPACE_ROOT/.agent-cockpit/roles` prompts by canonical role id. A repo-local `_PROTOCOL.md` overrides central only when present; otherwise central `_PROTOCOL.md` is used. `workspace.json` remains settings-only (`workspace_root`, `role_runtimes`) and never carries roster maps. This is intentional: repo-specific system prompts can live in the repo while the cockpit binaries/state stay central and ignored. Each agent then reorients from
durable sources — its charter, the shared protocol, Linear, and the dispatch log
(`$COCKPIT_BIN/dispatch log 40`) — and waits to be woken by a dispatch. Leads report back
with `--kind report-done` / `report-blocked` dispatches to the orchestrator and update the
Linear issue.
