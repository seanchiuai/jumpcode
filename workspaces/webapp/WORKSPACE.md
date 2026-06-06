# Webapp Workspace

The first local orchestration workspace managed by MacBook's `.agent-cockpit`. For
canonical terms see [`../../CONTEXT.md`](../../CONTEXT.md); for the decisions see
[`../../docs/adr/`](../../docs/adr/).

## Purpose

Coordinate development of web applications through a visible, accountable team. The set
of leads is **whatever this workspace declares** in `workspace.json` (any number, any
domain) — only the orchestrator is fixed. The current team:

```text
Sean / Hermes
  -> 🧭 orchestrator
      -> 🎨 frontend-lead
      -> 🛠 backend-lead
      -> ✅ qa-lead
      -> 🚀 devops-lead
      -> 🔌 mcp-lead
```

To change the team, edit `default_participants` / `routing` / `role_prompts` /
`role_emojis` in `workspace.json`, add the lead's charter under `../../roles/`, and
relaunch.

Leads may invoke general, repo-agnostic Claude Code **subagents** as a tool, but only the
orchestrator and leads are durable cockpit panes. Hermes drives the orchestrator only;
Sean may type into any pane.

The visible cockpit uses one tmux session with two windows:

```text
roles    one Claude Code pane per role
         left column: the workspace's leads, stacked (count/order follow workspace.json)
         right side: orchestrator, full height
monitor  feed + status logs, available but not stealing role-pane space
```

The orchestrator is always on the **right side**. Each pane carries a stable
`@cockpit_role` option (e.g. `orchestrator`, `backend-lead`) — that is how `dispatch`
targets a pane for a wake. Claude overwrites visible pane titles, so wake targeting never
relies on the title; a human-readable `@role` border label is shown for people.

**Every role label carries an emoji** (convention). Set one per role in
`workspace.json` `role_emojis`; any lead without one is auto-assigned a distinct fallback
so the requirement always holds.

Switch windows with `Ctrl-b n` / `Ctrl-b p`, or attach directly:

```bash
tmux attach -t macbook-webapp:roles
tmux switch-client -t macbook-webapp:monitor
```

When an app/repo is chosen, put or link it under this directory; create work as Linear
issues (the cockpit keeps no local copy of project/task state).

## Local paths

Workspace root:

```text
/Users/seanchiu/Desktop/workspace-macbook/workspaces/webapp
```

Cockpit metadata:

```text
/Users/seanchiu/Desktop/workspace-macbook/.agent-cockpit/workspaces/webapp
```

Role charters + shared protocol:

```text
/Users/seanchiu/Desktop/workspace-macbook/.agent-cockpit/roles/_PROTOCOL.md
/Users/seanchiu/Desktop/workspace-macbook/.agent-cockpit/roles/orchestrator.md
/Users/seanchiu/Desktop/workspace-macbook/.agent-cockpit/roles/frontend-lead.md
/Users/seanchiu/Desktop/workspace-macbook/.agent-cockpit/roles/backend-lead.md
/Users/seanchiu/Desktop/workspace-macbook/.agent-cockpit/roles/qa-lead.md
/Users/seanchiu/Desktop/workspace-macbook/.agent-cockpit/roles/devops-lead.md
/Users/seanchiu/Desktop/workspace-macbook/.agent-cockpit/roles/mcp-lead.md
```

## Operating rules

1. Hermes talks to the orchestrator by default; Sean may type into any pane.
2. The orchestrator decomposes goals into Linear issues and dispatches leads.
3. Leads close the loop with `report-done` / `report-blocked` dispatches and update the
   Linear issue.
4. Projects and tasks live in Linear; the dispatch log (`state/dispatches.jsonl`) is the
   durable record of who said what.
5. Visible panes are accountability roles (orchestrator + leads); subagents are invoked
   by leads, not run as permanent panes.
6. There is no lead↔lead channel — a lead asks the orchestrator to relay.

## Launching

```bash
cd /Users/seanchiu/Desktop/workspace-macbook
./.agent-cockpit/bin/start-webapp
```

This launches fresh Claude agents (no session resume). Each pane reorients from its
charter, the shared protocol, Linear, and the dispatch log
(`./.agent-cockpit/bin/dispatch log 40`). Give the orchestrator a goal with:

```bash
./.agent-cockpit/bin/dispatch send --from hermes --to orchestrator \
  --project <LINEAR-PROJECT> --subject "<webapp goal>" "<details>"
```
