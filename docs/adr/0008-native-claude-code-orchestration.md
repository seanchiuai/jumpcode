# Native Claude Code Orchestration Replaces the Custom Delivery Layer

Status: **Accepted** (2026-07-17). **Supersedes ADR 0002 (dispatch), 0004 (fresh launch),
0005 (revive), and 0007 (role discovery) at the mechanism level.** Keeps ADR 0001
(topology) and ADR 0006 (GitHub Issues is the system of record) — those decisions stand;
only how they are *carried out* changes.

Jumpcode keeps its **behavioral contract** — a non-coding accountable orchestrator, named
specialists with owned territory, independent review and testing, GitHub Issues as durable
truth, done/blocked reporting, and Sean's decision gates — and retires the **custom
infrastructure** that used to deliver it. The tmux role grid, the `dispatch` wake/log CLI,
the append-only dispatch log, `health`/`peek`/`fleet`, and `revive`/`recompact` are removed
in favor of Claude Code's native orchestration primitives.

## Why

The custom layer re-implemented, in ~1,600 lines of Python and Bash, capabilities Claude
Code now ships natively:

| Jumpcode custom mechanism (retired) | Native primitive (replacement) |
| --- | --- |
| tmux pane grid + `start-webapp` launcher | Main session = orchestrator; specialists are **subagents** spawned with the **Agent** tool (background by default) |
| `@jumpcode_role` pane targeting + keystroke **wake** (`dispatch send`) | The Agent tool prompt delivers the first instruction; **`SendMessage`** (by agent id or name) delivers every follow-up — the agent already holds its context |
| `dispatches.jsonl` dispatch log + `conversation.log` | **GitHub Issues** (durable truth, unchanged) for what the work is; native **agent transcripts** for the live conversation |
| `health` / `peek` / `fleet` pane monitors | **Agent view / FleetView** (`claude agents`, `--json`, `claude logs <id>`, `claude attach <id>`) |
| `revive` + per-workspace session manifest | native **`claude --resume`**; recovery reconstructs from GitHub Issues + git/PR/worktree state |
| `recompact` + compaction hooks | native compaction + `SessionStart` / `PreCompact` hooks |
| `roles/*.md` charters + discovery + `enabled_roles` | **`.claude/agents/*.md`** native subagent definitions; team = which agents you spawn |
| repo-local overlay charters | project-scope `.claude/agents/` in the target worktree (native discovery) |
| soft, prose-only tool guardrails | frontmatter **`tools`** allowlists / **`disallowedTools`** denylists — enforced by the runtime |

Continuity — the property AUDIT.md called the system's most important — is preserved, but
its backbone moves from the dispatch log to **GitHub Issues + git state**, which are already
the durable record the team edits (see "Recovery" below). The Task tools' agent state
(`~/.claude/jobs/<id>/state.json`) is **ephemeral and session-local**; it is a live
convenience, never durable truth.

## Decision

### Roles map to native constructs

- **Orchestrator = the main interactive session** Sean drives. Non-coding and accountable:
  it decomposes goals into GitHub Issues, spawns specialists, integrates their reports, and
  holds the Sean-facing gates. It is not governed by an agent definition (no agent def
  governs the main session), so its rules live in `roles/orchestrator.md`, which the session
  reads at kickoff.
- **Coding leads** (`backend-lead`, `frontend-lead`, `devops-lead`) and the independent
  **reviewer** (`code-reviewer`) and **tester** (`qa-tester`) are `.claude/agents/*.md`
  subagents. A "team" is just the subset the orchestrator spawns for a goal.

### Browser automation is owned by reviewer and tester only

This is a **hard boundary**, not a soft guardrail:

- `code-reviewer` and `qa-tester` **own all browser automation** — Claude in Chrome
  (`mcp__claude-in-chrome__*`) and Playwright — and their frontmatter `tools` grant it.
- Coding leads **deny** the browser MCP servers in `disallowedTools`, so the runtime blocks
  browser use even if a prompt asks for it.
- The **orchestrator never operates a browser.** Because the main session cannot be governed
  by an agent def, this one is necessarily **behavioral**, stated plainly in
  `roles/orchestrator.md`: browser automation clutters the orchestrator's context and is
  always delegated to the reviewer or tester. The rationale is context hygiene, and the rule
  is enforced by discipline, not permissions — say so, don't imply enforcement that isn't
  there.

### Topology is preserved and now substrate-enforced (ADR 0001 stands)

Native subagents return their result to the spawning session and cannot address each other —
that *is* hub-and-spoke, now enforced by the substrate instead of by prose. `SendMessage`
carries orchestrator → specialist follow-ups; a specialist that needs another specialist asks
the orchestrator to relay. Hub-and-spoke is the default; for a tiny task the orchestrator may
work inline (hub-and-spoke is optional, not mandatory).

### GitHub Issues stays the system of record (ADR 0006 stands)

Unchanged: a project is a repo/milestone, a task is an issue, reached via the `gh` CLI. No
local task/run/project registry. Reports are (1) the subagent's returned summary to the
orchestrator and (2) a `gh` issue comment/status update.

## Delivery: how a session actually gets these agents

This is the load-bearing detail. Native agent discovery walks up from the session's working
directory and reads `<cwd>/.claude/agents/` and `~/.claude/agents/` — it will **never**
discover `.jumpcode/.claude/agents/` when the orchestrator is rooted in a target repo
worktree (which it must be, so leads edit the right tree and `isolation: worktree` branches
the right repo).

Therefore **this repo is the canonical *source* of an agent pack, not an auto-loaded one.**
Adoption installs the pack where Claude Code looks:

1. **Project scope (per workspace, recommended)** — copy the pack into the target worktree's
   `.claude/agents/`. This is the native analog of the retired repo-local overlay charters.
2. **User scope (permanent personal team)** — copy into `~/.claude/agents/`; every session
   gets the specialists.
3. **Ad-hoc** — launch with `claude --agents <path-to-.jumpcode/.claude/agents>`.

`bin/jumpcode-install` performs (1) or (2). The orchestrator charter and shared protocol
(`roles/orchestrator.md`, `roles/_PROTOCOL.md`) are markdown the orchestrator session reads at
kickoff; the installer places them alongside the agents so a fresh session can find them.

## Recovery without the dispatch log

A fresh or resumed session reconstructs state from durable sources only — never from the
retired log or from ephemeral agent state:

1. **`gh issue list` / `gh issue view`** in the workspace repo — the open issues, their
   acceptance criteria, labels, and comment history are what the work *is* and how far it got.
2. **Git state** in the worktree — `git status`, `git log`, the feature branch, and
   `gh pr list` / `gh pr view` show what has actually been built and what is in review.
3. **`claude --resume`** when restoring the orchestrator's own prior reasoning is worth more
   than a clean slate (the native replacement for `revive`); otherwise start fresh and rebuild
   from (1) and (2).

## Consequences

- All of `bin/` except a thin `jumpcode-install` adoption helper is removed; the dispatch
  JSONL, session manifests, and `conversation.log` are gone.
- The parent `workspace-macbook` `jumpcode` skill and any CLAUDE.md text that call
  `dispatch` / `start-webapp` / `revive` will break and must be updated separately — those
  are out of this repo's scope but are a required follow-up.
- Guardrails that were "advisory in v1" become **enforced** for the one boundary that
  matters most (browser tools), via frontmatter tool lists.
- Historical design docs under `docs/plans/` and `AUDIT.md` describe the retired mechanics
  and are kept as dated history, superseded by this ADR.
