# Webapp Workspace

This is the first local orchestration workspace managed by MacBook's `.agent-cockpit`.

## Purpose

Coordinate development of web applications through a visible accountable team:

```text
Sean/Hermes
  -> orchestrator
      -> frontend-lead
      -> backend-lead
      -> qa-lead
```

Leads may launch ephemeral Claude Code/Codex/OpenCode subagents internally, but only the orchestrator and leads are durable cockpit participants.

The visible cockpit uses two tmux windows:

```text
roles    four Claude Code role panes only
         left column: frontend-lead / backend-lead / qa-lead
         right side: orchestrator, full height
monitor  feed + status logs, available when needed but not stealing role-pane space
```

The orchestrator is deliberately always on the **right side** and has a tmux pane-border label:

```text
🧭 ORCHESTRATOR — RIGHT SIDE
```

Claude Code may overwrite normal pane titles, so the stable human indicator is the tmux border label, not the application title.

Switch windows with `Ctrl-b n` / `Ctrl-b p`, or attach directly:

```bash
tmux attach -t macbook-webapp:roles
tmux switch-client -t macbook-webapp:monitor
```

When an actual app/repo is chosen, put or link it under this directory and create tasks through `.agent-cockpit/bin/task`.

## Local paths

Workspace root:

```text
/Users/seanchiu/Desktop/workspace-macbook/workspaces/webapp
```

Cockpit metadata:

```text
/Users/seanchiu/Desktop/workspace-macbook/.agent-cockpit/workspaces/webapp
```

Role prompts:

```text
/Users/seanchiu/Desktop/workspace-macbook/.agent-cockpit/roles/orchestrator.md
/Users/seanchiu/Desktop/workspace-macbook/.agent-cockpit/roles/frontend-lead.md
/Users/seanchiu/Desktop/workspace-macbook/.agent-cockpit/roles/backend-lead.md
/Users/seanchiu/Desktop/workspace-macbook/.agent-cockpit/roles/qa-lead.md
```

## Operating rules

1. Hermes/user talks to the orchestrator by default.
2. Orchestrator creates/assigns tasks and mails leads.
3. Leads report back to orchestrator with `DONE` or `BLOCKED` reports.
4. The mailbox/task/run/report JSONL files are the source of truth.
5. Visible panes are accountability roles, not every specialist/engineer.
6. Do not rely on tmux pane scraping as canonical state.

## Standard run bootstrap

```bash
cd /Users/seanchiu/Desktop/workspace-macbook
./.agent-cockpit/bin/run start \
  --goal "<webapp goal>" \
  --participant hermes \
  --participant orchestrator \
  --participant frontend-lead \
  --participant backend-lead \
  --participant qa-lead
```
