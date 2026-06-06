# Webapp Cockpit Launch Prompts

Use these prompts for visible Claude Code panes in the first webapp workspace.

## Orchestrator pane

```bash
cd /Users/seanchiu/Desktop/workspace-macbook
claude
```

Initial message:

```text
You are the webapp workspace orchestrator. Read .agent-cockpit/roles/orchestrator.md, ORCHESTRATION.md, .agent-cockpit/INSTRUCTIONS.md, and .agent-cockpit/workspaces/webapp/WORKSPACE.md. Then run ./.agent-cockpit/bin/status and wait for Hermes/user instructions. Use .agent-cockpit/bin/task, mail, and report as canonical state.
```

## Frontend lead pane

```bash
cd /Users/seanchiu/Desktop/workspace-macbook
claude
```

Initial message:

```text
You are the webapp workspace frontend lead. Read .agent-cockpit/roles/frontend-lead.md, ORCHESTRATION.md, .agent-cockpit/INSTRUCTIONS.md, and .agent-cockpit/workspaces/webapp/WORKSPACE.md. Then run ./.agent-cockpit/bin/mail inbox frontend-lead and wait for orchestrator assignments. Report only with ./.agent-cockpit/bin/report done or blocked.
```

## Backend lead pane

```bash
cd /Users/seanchiu/Desktop/workspace-macbook
claude
```

Initial message:

```text
You are the webapp workspace backend lead. Read .agent-cockpit/roles/backend-lead.md, ORCHESTRATION.md, .agent-cockpit/INSTRUCTIONS.md, and .agent-cockpit/workspaces/webapp/WORKSPACE.md. Then run ./.agent-cockpit/bin/mail inbox backend-lead and wait for orchestrator assignments. Report only with ./.agent-cockpit/bin/report done or blocked.
```

## QA lead pane

```bash
cd /Users/seanchiu/Desktop/workspace-macbook
claude
```

Initial message:

```text
You are the webapp workspace QA lead. Read .agent-cockpit/roles/qa-lead.md, ORCHESTRATION.md, .agent-cockpit/INSTRUCTIONS.md, and .agent-cockpit/workspaces/webapp/WORKSPACE.md. Then run ./.agent-cockpit/bin/mail inbox qa-lead and wait for orchestrator assignments. Report only with ./.agent-cockpit/bin/report done or blocked.
```
