# Agent Cockpit Instructions

This file is the local operator manual for Hermes/MacBook and any visible Claude Code lead panes.

## Mandatory use cases

Use `.agent-cockpit` whenever work needs durable orchestration:

- multi-agent work
- visible cockpit work
- work involving orchestrator/leads/subagents
- tasks that need owners, acceptance criteria, blockers, or handoff
- work likely to span context compaction or multiple sessions
- coordination with Brainy or another agent process
- anything described as BridgeSwarm-like orchestration

For tiny one-shot answers, do not create orchestration events.

## Source of truth

Machine-readable source of truth:

```text
.agent-cockpit/state/*.jsonl
```

Human-readable feed:

```text
.agent-cockpit/shared/conversation.log
```

`mail` is canonical for communication. `ask` is just a transport helper.

## Command contract

All commands should be run from:

```bash
cd /Users/seanchiu/Desktop/workspace-macbook
```

Commands:

```bash
./.agent-cockpit/bin/run current
./.agent-cockpit/bin/run start --goal "..."
./.agent-cockpit/bin/task create --title "..." --owner backend-lead
./.agent-cockpit/bin/task list
./.agent-cockpit/bin/mail send --from orchestrator --to backend-lead --task task-... "..."
./.agent-cockpit/bin/mail inbox backend-lead
./.agent-cockpit/bin/report done task-... --from backend-lead --summary "..."
./.agent-cockpit/bin/report blocked task-... --from backend-lead --blocker "..." --need-from orchestrator
./.agent-cockpit/bin/status
```

## Report discipline

Only two report outcomes exist in v1:

```text
DONE
BLOCKED
```

DONE reports should include what changed and checks run. BLOCKED reports should include the blocker, why blocked, what was tried, and who needs to respond.

## Testing after changes

```bash
python3 -m py_compile .agent-cockpit/bin/cockpit
bash -n .agent-cockpit/bin/run .agent-cockpit/bin/task .agent-cockpit/bin/mail .agent-cockpit/bin/report .agent-cockpit/bin/ask .agent-cockpit/bin/convo .agent-cockpit/bin/status
python3 .agent-cockpit/tests/test_cockpit.py
```
