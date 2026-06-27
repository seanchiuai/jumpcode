# Jumpcode Launch Prompts

`start-webapp` launches the visible Claude Code/Codex panes **fresh** (no session resume,
leads without `-p`) and injects an initial prompt into each. This file documents that
prompt so the doc and the launcher stay in sync — if you change one, change the other.
See [`../../bin/start-webapp`](../../bin/start-webapp) for the live source.

Each pane is launched with its configured runtime, given a stable `@jumpcode_role` tmux
option (so `dispatch` can wake it), then sent this prompt (with `$role` = its role name and
`$WORKSPACE` = the workspace name):

```text
You are the $WORKSPACE workspace $role. You are running from repo/workspace root
$WORKSPACE_ROOT. Read your charter $prompt_file and the shared protocol
$SHARED_PROTOCOL. Projects and tasks live in GitHub issues — use the `gh` CLI as the system
of record; there is no local task registry. Check your inbox now:
$JUMPCODE_BIN/dispatch inbox $role. Then wait — when someone dispatches you, this pane
is woken automatically. Send messages with $JUMPCODE_BIN/dispatch send --from $role
--to <role> [--task #NN] BODY.
```

The roles launched are the validated discovery result from
`jumpcode roles discover --workspace <name> --json`. **Only the orchestrator launches by
default — there are no pre-generated leads.** The recommended central leads each launch only
when the workspace opts them in via `enabled_roles`:

```text
🧭 orchestrator.md     full-height right pane; dispatch id: orchestrator  (always)
🎨 frontend-lead.md    recommended lead; launches when "frontend-lead" ∈ enabled_roles
🛠 backend-lead.md     recommended lead; launches when "backend-lead"  ∈ enabled_roles
✅ qa-lead.md          recommended lead; launches when "qa-lead"       ∈ enabled_roles
🚀 devops-lead.md      recommended lead; launches when "devops-lead"   ∈ enabled_roles
🔬 code-review-lead.md recommended lead; launches when "code-review-lead" ∈ enabled_roles
```

A workspace adds specialist leads (e.g. `🔥 heatmap-expert.md`) by dropping prompt files
into its own `<workspace_root>/.jumpcode/roles/` overlay — those launch automatically,
no `enabled_roles` entry needed.

Discovery always launches the central `orchestrator`, adds the recommended central leads
named in `enabled_roles`, then overlays repo-local `$WORKSPACE_ROOT/.jumpcode/roles`
charters (which launch automatically) by canonical role id; a repo-local `_PROTOCOL.md`
overrides central when present. `workspace.json` stays settings-only (`workspace_root`,
`role_runtimes`, `enabled_roles`) and never carries roster prompts. This is intentional:
repo-specific system prompts live in the project repo while the Jumpcode binaries/state
stay shared. Each agent reorients from durable sources — its charter, the shared protocol,
GitHub issues, and the dispatch log (`$JUMPCODE_BIN/dispatch log 40`) — and waits to be woken by a
dispatch. Leads report back with `--kind report-done` / `report-blocked` dispatches to the
orchestrator and update the GitHub issue.
