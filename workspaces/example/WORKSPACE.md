# Example Workspace

A template workspace for Jumpcode. Copy this directory to `workspaces/<name>/`,
point `workspace.json`'s `workspace_root` at your project repo, and launch. For canonical
terms see [`../../CONTEXT.md`](../../CONTEXT.md); for the decisions see
[`../../docs/adr/`](../../docs/adr/).

> Real workspaces are **not** committed to this repo — only this example is. A real
> workspace's `workspace_root` lives in its own project repo, which carries its own
> charters under `<workspace_root>/.jumpcode/roles/` (in that repo's git). This repo
> ships the engine plus an example **base set** of roles and this example config.

## How roles are resolved

`start-webapp` (or `JUMPCODE_WORKSPACE=<name> start-webapp`) calls
`jumpcode roles discover --workspace <name> --json`. Discovery:

1. starts from the central base set in `$JUMPCODE_HOME/roles/*.md`;
2. overlays any repo-local prompts in `<workspace_root>/.jumpcode/roles/*.md`,
   matched by **canonical role id** (a repo-local file replaces the central one);
3. uses the repo-local `_PROTOCOL.md` if present, else the central one.

Prompt filenames set the pane label and id: `🎨 frontend-lead.md` → pane `🎨 frontend-lead`,
dispatch id `frontend-lead`. A plain `frontend-lead.md` works too. Only the `orchestrator`
role is required; any number/mix of leads is allowed. `workspace.json` is settings-only
(`workspace_root`, `role_runtimes`) — there is no roster JSON to keep in sync.

## Topology

```text
You / Hermes
  -> 🧭 orchestrator              full-height right pane; the only relay
      -> <leads>                  left columns, one visible pane each
          -> subagents            invoked by a lead as a tool (not panes)
```

Hub-and-spoke (ADR 0001): the orchestrator decomposes goals into GitHub issues and
dispatches leads; leads report back with `report-done`/`report-blocked` and update the
GitHub issue; there is no lead↔lead channel — a lead asks the orchestrator to relay.
Projects and tasks live in **GitHub issues** (ADR 0006); Jumpcode keeps no local task state.

## Launch

```bash
# from the repo's parent dir
JUMPCODE_WORKSPACE=example ./.jumpcode/bin/start-webapp
```

Panes launch fresh with no session resume (ADR 0004); each reorients from its charter,
the shared protocol, GitHub issues, and the dispatch log (`bin/dispatch log 40`). Give the
orchestrator a goal with `bin/dispatch send --from hermes --to orchestrator …`.
