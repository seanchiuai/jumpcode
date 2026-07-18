# Jumpcode Handoff

## What this is

A behavioral contract for multi-agent software delivery, shipped as a pack of native Claude Code
agent definitions. A non-coding accountable **orchestrator** (Sean's main session) decomposes a
goal into GitHub Issues and commands named **specialists** — coding leads plus an independent
**reviewer** and **tester** — with owned territory, done/blocked reports, and Sean's decision
gates. It runs on Claude Code's native primitives; the old tmux/dispatch/wake engine is retired
(see [`docs/adr/0008`](docs/adr/0008-native-claude-code-orchestration.md)). See
[`CONTEXT.md`](CONTEXT.md) for terms and [`docs/adr/`](docs/adr/) for decisions.

## Core primitives (native)

```text
Agent tool    orchestrator spawns a specialist subagent (background by default)
SendMessage   orchestrator continues a specialist by id/name, context intact
Agent view    claude agents / --json / logs <id> / attach <id> — live monitor
GitHub Issues durable truth (gh CLI); no local task/run/project registry
git worktrees isolation per workspace; claude --resume for continuity
```

There is **no jumpcode CLI and no state files.** The only script is the adoption helper.

## Repository layout

```text
.claude/agents/backend-lead.md     coding lead — no browser
.claude/agents/frontend-lead.md    coding lead — no browser
.claude/agents/devops-lead.md      coding lead — no browser
.claude/agents/code-reviewer.md    reviewer — OWNS browser automation
.claude/agents/qa-tester.md        tester — OWNS browser automation
roles/orchestrator.md              orchestrator charter (main-session guidance)
roles/_PROTOCOL.md                 shared interaction rules
bin/jumpcode-install               adoption helper (copies the pack where Claude Code looks)
CONTEXT.md / README.md / INSTRUCTIONS.md   glossary / overview / operator manual
docs/adr/                          decisions (0008 anchors the native migration)
jumpcode-workspaces/               example workspace configs (config-only)
tests/                             agent-pack + browser-boundary + installer validation
```

## Delivery model (the load-bearing detail)

Native agent discovery reads `<cwd>/.claude/agents/` and `~/.claude/agents/` — never
`.jumpcode/.claude/agents/`. This repo is the **canonical source**; adoption installs the pack
into the target worktree (`--project`) or user scope (`--user`), or points Claude Code at the
source with `claude --agents`. Nothing is auto-loaded from `.jumpcode/`.

## The one hard rule: browser ownership

Only `code-reviewer` and `qa-tester` drive a browser (Claude in Chrome / Playwright). Coding
leads deny the browser MCP servers in `disallowedTools` (runtime-enforced); the orchestrator
never drives a browser (behavioral — it delegates, to keep its context clean). `tests/test_agents.py`
locks this in.

## Important design decisions

- Native Claude Code orchestration replaces the custom delivery layer (ADR 0008), superseding the
  dispatch/fresh/revive/discovery mechanics (ADR 0002/0004/0005/0007) while keeping topology
  (0001) and GitHub-Issues-as-system-of-record (0006).
- Hub-and-spoke is enforced by the substrate (subagents cannot address each other) and is optional
  for tiny tasks.
- Continuity comes from GitHub Issues + git state, not a dispatch log; runtime agent/task state is
  ephemeral.

## Verification

```bash
python3 -m unittest discover -s tests
bash -n bin/jumpcode-install
```

## Known follow-up (outside this repo)

The parent `workspace-macbook` `jumpcode` skill and any CLAUDE.md text that call the retired
dispatch / launch / revive CLI must be updated separately — they are out of this public repo's
scope. See ADR 0008's "Consequences" for the specifics.
