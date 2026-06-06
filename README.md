# Local Agent Cockpit Orchestration

This directory is the local, project-owned orchestration layer for `workspace-macbook`.
It is intentionally small: no daemon, no database, no cloud dependency.

## Core primitives

- `run` — top-level orchestration session ledger.
- `task` — durable task registry.
- `mail` — structured inter-agent mailbox.
- `report` — machine-readable `DONE` / `BLOCKED` reports.

Source of truth is append-only JSONL:

```text
.agent-cockpit/state/runs.jsonl
.agent-cockpit/state/tasks.jsonl
.agent-cockpit/state/messages.jsonl
.agent-cockpit/state/reports.jsonl
```

Human-readable activity is mirrored to:

```text
.agent-cockpit/shared/conversation.log
```

## Instructional context

For Hermes/MacBook and future agent sessions, read these before using or modifying the tool:

```text
/Users/seanchiu/Desktop/workspace-macbook/ORCHESTRATION.md
/Users/seanchiu/Desktop/workspace-macbook/.agent-cockpit/INSTRUCTIONS.md
/Users/seanchiu/Desktop/workspace-macbook/.agent-cockpit/HANDOFF.md
```

This is a core tool for durable coordination. Use it when work involves multiple agents, visible cockpit roles, task ownership, blockers, Brainy handoffs, Claude Code/Codex/OpenCode workers, or any project that may survive context compaction.

## Quick start

```bash
# Start a run
./.agent-cockpit/bin/run start \
  --goal "Build BridgeSwarm-like local orchestration" \
  --participant orchestrator \
  --participant backend-lead \
  --participant frontend-lead \
  --participant qa-lead

# Create a task
./.agent-cockpit/bin/task create \
  --title "Implement mailbox protocol" \
  --owner backend-lead \
  --criteria "Inbox lists messages addressed to the lead" \
  --criteria "Replies preserve task/thread id"

# Send a message
./.agent-cockpit/bin/mail send \
  --from orchestrator \
  --to backend-lead \
  --task task-YYYYMMDD-001 \
  --subject "Start implementation" \
  "Please implement the mailbox protocol."

# Read inbox
./.agent-cockpit/bin/mail inbox backend-lead

# Report done
./.agent-cockpit/bin/report done task-YYYYMMDD-001 \
  --from backend-lead \
  --summary "Implemented JSONL-backed mailbox" \
  --work "Added mail send/inbox/reply/show" \
  --check "python3 -m py_compile .agent-cockpit/bin/cockpit:pass:compiled"

# Report blocked
./.agent-cockpit/bin/report blocked task-YYYYMMDD-001 \
  --from backend-lead \
  --blocker "Need scope decision" \
  --why "Two possible designs" \
  --tried "Reviewed current scripts" \
  --need-from orchestrator

# Summarize current run
./.agent-cockpit/bin/status
```

## Convenience wrappers

- `ask <agent> <message...>` logs a mailbox message from `COCKPIT_FROM` or `hermes`.
  If `COCKPIT_TMUX_SESSION` is set and a tmux pane title matches the agent name, it also injects a visible cockpit message.
- `convo [lines]` tails the human-readable conversation log.
- `status` renders the current run summary.

## Design constraints

- Keep visible panes for durable accountability roles only: orchestrator and leads.
- Specialists/subagents should be launched internally by the responsible lead, not as permanent panes.
- Keep machine-readable state in JSONL; avoid relying on tmux pane scraping for correctness.
- Use only `DONE` and `BLOCKED` reports for v1.
- Liveness and eval/rating are deferred. For now, `last message/report timestamp` and `checks_run` inside reports are enough.

## Tests

```bash
python3 .agent-cockpit/tests/test_cockpit.py
```
