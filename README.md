# Local Jumpcode Orchestration

This directory is the local, project-owned orchestration layer for `workspace-macbook`.
It is intentionally small: no daemon, no database, no cloud dependency. It owns only the
*delivery* layer — visible panes, live wake, and a durable dispatch log. Projects and
tasks live in **GitHub issues**, not here.

For canonical terms see [`CONTEXT.md`](CONTEXT.md); for the decisions behind the design
see [`docs/adr/`](docs/adr/) (0001–0006). Those are the authority if anything here
conflicts.

## The one mental model

> The Human (Sean) drives the **orchestrator**, which commands its **team leads**, which
> invoke general **subagents** as a tool. **Projects and tasks live in GitHub issues.** The
> jumpcode only moves messages between visible panes and remembers what was said.

## Core primitive: the dispatch

A **dispatch** (ADR 0002) is one directed message that does two things at once:

- **Delivered live** — a prompt is injected ("wake") into the recipient's tmux pane,
  targeted by its stable `@jumpcode_role` option, so the agent gets to work immediately.
- **Appended to the durable dispatch log** — so a restarted agent, or Sean, can
  reconstruct what was asked and what happened.

There is a single CLI verb, `dispatch`:

```bash
# send (live wake + durable log)
./.jumpcode/bin/dispatch send \
  --from <role> --to <role> \
  [--project <owner/repo>] [--task #42] \
  [--subject "<subject>"] \
  [--kind request|reply|report-done|report-blocked|notice] \
  [--no-wake] \
  "<body>"

# inspect
./.jumpcode/bin/dispatch inbox <role> [--json]   # dispatches addressed to a role
./.jumpcode/bin/dispatch show <dispatch-id> [--json]
./.jumpcode/bin/dispatch log [N]                 # human-readable feed (default 40)
./.jumpcode/bin/dispatch status [--json]         # open loops: requests with no matching report (+ pane state)

# monitor
./.jumpcode/bin/health [--json]                  # per-role: alive · working/waiting/idle · runtime · subagents
./.jumpcode/bin/fleet [--json|--once]            # live dashboard of ALL workspaces + status (active/idle/past/error)
./.jumpcode/bin/peek <role> [lines]              # read-only view of a role's pane (never wakes it)
./.jumpcode/bin/jumpcode roles discover --workspace <name> --json  # validated role discovery
```

Default `--kind` is `request`. Use `reply` to answer one, `notice` for an FYI,
`report-done`/`report-blocked` when closing out a task — pass `--reply-to <request
dispatch-id>` on reports so `dispatch status` pairs them and closes the loop. `--no-wake`
logs without injecting (scripted/batch use); normal sends always wake.

## State

The only state file is append-only JSONL:

```text
.jumpcode/state/dispatches.jsonl
```

(plus an internal `state/counters.json` for id reservation and a `state/.lock`).
Human-readable activity is mirrored to:

```text
.jumpcode/shared/conversation.log
```

## Convenience wrappers

- `status` — alias for `dispatch status` (open loops plus pane state).
- `convo [lines]` — tails the human-readable conversation log (default 80).
- `start-webapp` — launches the `webapp` workspace tmux grid (fresh agents).

## Where work lives: GitHub issues

A **project** is a GitHub repo/milestone; a **task** is a GitHub issue (ADR 0006). Agents read
and update them via the `gh` CLI. The jumpcode keeps **no** local copy of project/task state.
"Done" is informal: update the GitHub issue and send a `report-done` dispatch.

## Roles and topology

Role panes are discovered from prompt folders, not roster JSON. **Only the orchestrator launches by default — there are no pre-generated leads.** Central `$JUMPCODE_HOME/roles` holds *recommended* leads that launch only when a workspace opts them in via `enabled_roles` in `workspace.json`; a repo may also add `$WORKSPACE_ROOT/.jumpcode/roles` charters that launch automatically and overlay central prompts by canonical role id. A repo-local `_PROTOCOL.md` overrides the central protocol when present; otherwise the central `_PROTOCOL.md` is used. `workspace.json` is settings-only (`workspace_root`, `role_runtimes`, `enabled_roles`) and must not contain team roster prompts.

- **Orchestrator** — one per workspace, the single accountable agent; a visible right
  pane. Receives goals from Sean, decomposes into GitHub issues, commands leads.
- **Team leads** — durable, repo-specific accountable agents (e.g. frontend-lead,
  backend-lead, qa-lead); visible left panes, launched without `-p`.
- **Subagents** — general, repo-agnostic Claude Code subagents (e.g. a code reviewer) a
  lead invokes as a tool. Not panes, not an accountability layer.

Topology is hub-and-spoke (ADR 0001): Sean (the Human) may type into any pane
(orchestrator or any lead); there is no lead↔lead channel — a lead asks the orchestrator
to **relay**.

## Creating a workspace: the Goal Contract

A workspace exists to serve **one clearly defined goal with a verifiable final state**.
The goal is its spine — it pins what the session is for and tailors the orchestrator,
leads, and specialist agents toward it. Define the goal and gather repo context *before*
creating: the charters and roster all depend on the mission, so launching a team on a
vague or wrongly-scoped goal wastes work in the wrong direction.

Resolve every field below before launch. **🔒 = hard gate** — cannot launch until it's
resolved. The rest are **derived** from the goal, repo, and GitHub issues, and confirmed only
when genuinely in doubt; if the direction is obvious, set it and move on (don't ask what
you can safely derive).

**Mission — you must supply:**
- 🔒 **Goal** — one or two sentences: what this workspace achieves.
- 🔒 **Final state** — an *observable/verifiable* done-condition (a test passes, a metric
  hits N, a feature behaves like Y). The implementation may be vague; the end state may not.
- 🔒 **Scope forks** — for an ambiguous mission, the decisive choice only you can make
  (port-vs-embed, one-DB-vs-two). Surfaced and asked only when a real fork exists.

**Anchoring context:**
- 🔒 **Repo** — every workspace is bound to one git repo + a new worktree at
  `<repo>/.worktrees/<slug>`.
- **Base branch** — default `staging`; ask only if the repo has none.
- **System of record** — default **GitHub issues** (`gh`): file issues in the workspace's own
  repo; ask which repo if not given. Never invent or auto-create a repo. A workspace may instead
  track work in a different tracker — if so, enforce it with a thin orchestrator overlay, since
  the launcher prompt and central charter assume GitHub issues.

**Derived — confirm only if doubtful:**
- **Slug** → session `macbook-<slug>`, the worktree path, and the feature branch.
- **Roster** — the base leads always, plus specialist lead(s) tailored to the goal.
- **Charters** — specialist + orchestrator, generated from the goal, domain, and final
  state. The orchestrator's identity and pane title are **`orchestrator · <goal>`**, not a
  generic workspace name.

**Defaults (overridable):** runtime `claude` for every role; dedicated worktree, husky
respected, never push `staging`/`main`.

Flow once the contract is resolved: interview only where the goal leaves genuine doubt →
design → implementation plan → build, run autonomously — don't stop for an obvious fix
that clearly serves the goal.

**Kickoff — `/goal` (preferred, strongly recommended).** Once the grid is up and the
orchestrator pane is idle, hand it the mission with the global `/goal <mission>` command
(`~/.claude/commands/goal.md`, a user-global Claude Code command — not shipped by this repo).
It runs the orchestrator's
decompose → file-issues → dispatch → integrate → review-gate loop from one mission string,
checking the charter to know which tracker is in use. Offer it every time; the freeform alternative
loses the structured loop. In `workspace-macbook`, the full lifecycle procedure lives in the
canonical shared **`jumpcode` skill** (`.claude/skills/jumpcode/SKILL.md`, exposed to Codex
through `.agents/skills/jumpcode`).

## Continuity: always fresh

Launching a workspace always starts clean Claude agents with no session resume (ADR
0004). A fresh agent reconstructs context from the durable sources — GitHub issues and the
dispatch log. "Close workspace" = close the window; the saved config persists.

## Design constraints

- A local `workspace-macbook` tool, not a BuilderBase repo tool; not in system root.
- Visible panes are durable accountability roles only (orchestrator and leads).
- Subagents are invoked internally by the responsible lead, not run as permanent panes.
- v1 has no liveness daemon and no eval/rating harness (both deferred).

## Tests

```bash
python3 -m unittest discover -s tests
```
