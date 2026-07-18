# Jumpcode Instructions

The operator manual for Sean and the orchestrator session. Canonical terms live in
[`CONTEXT.md`](CONTEXT.md); the reasoning lives in [`docs/adr/`](docs/adr/); the shared
interaction rules live in [`roles/_PROTOCOL.md`](roles/_PROTOCOL.md).

## When to use Jumpcode

Use it when a goal is large enough to want a **non-coding accountable orchestrator commanding
named specialists** with independent review and testing — multi-file features, cross-domain
changes, anything that must be reviewed and verified before it merges up. For a tiny one-shot
change, the orchestrator can just do the work inline; hub-and-spoke is optional.

## Setup: install the pack

The orchestrator runs as your main Claude Code session **rooted in the target repo's
worktree**. Native discovery only finds `<worktree>/.claude/agents/` and `~/.claude/agents/`, so
install the pack there first:

```bash
./.jumpcode/bin/jumpcode-install --project ~/Desktop/<repo>/.worktrees/<slug>   # per workspace
./.jumpcode/bin/jumpcode-install --user                                         # or personal, all repos
```

This delivers the five specialist agents plus the orchestrator charter and shared protocol
(under `.claude/agents/jumpcode/`). Confirm the agents are visible with `claude agents` or by
asking the session to list its available subagents.

## Where work lives: GitHub Issues, not here

A **project** is a GitHub repo/milestone; a **task** is a GitHub issue (ADR 0006). Read and
write them with the `gh` CLI. There is **no local task/project/run registry**. "Done" is
informal: update the issue and report. The runtime's own agent/task state is ephemeral — never
treat it as the source of truth.

## The command contract (native)

There is no jumpcode CLI. The orchestrator uses Claude Code's native primitives:

- **Spawn a specialist** — the Agent tool, `subagent_type` = the agent's `name`
  (`backend-lead`, `frontend-lead`, `devops-lead`, `code-reviewer`, `qa-tester`), passing the
  task, acceptance criteria, and issue number. Subagents run in the background by default.
- **Continue a specialist** — `SendMessage`, addressing it by agent id (returned when spawned)
  or name. Use it to nudge, correct, or hand the next step; the agent keeps its context.
- **Monitor the team** — the Agent view:

  ```bash
  claude agents            # interactive view: working / idle / done / failed
  claude agents --json     # machine-readable
  claude logs <id>         # a specialist's transcript
  claude attach <id>       # attach to a running specialist
  ```

- **Track work** — `gh issue list`, `gh issue view <n>`, `gh issue comment`, `gh pr list` /
  `gh pr view`. GitHub is the durable record.

## Reporting discipline

A specialist's returned final message **is** its report. It states done or blocked against the
acceptance criteria it confirmed up front, and mirrors the outcome to the GitHub issue:

- **Done:** summary; what changed; checks run; open concerns; recommended next step.
- **Blocked:** the blocker; why; what was tried; what it needs from the orchestrator.

A specialist cannot ask a blocking question on its pane (nothing will answer it) — it puts the
question in its report with a best-guess default and keeps going on anything not blocked.

## The browser boundary

Only `code-reviewer` and `qa-tester` drive a browser (Claude in Chrome / Playwright); they own
all browser automation. The coding leads are denied the browser MCP servers in their agent
definitions, and the orchestrator never drives a browser (a behavioral rule — it delegates
browser work). If a coding lead's task needs browser verification, it flags that in its report
for the orchestrator to route.

## Topology

Hub-and-spoke (ADR 0001): Sean may address any agent; specialists return to the orchestrator and
reach each other only by asking it to **relay**. Native subagents cannot address each other, so
the substrate enforces this.

## Review, testing, and merge gates

- Before anything merges up into a shared branch, the orchestrator spawns `code-reviewer` for
  sign-off and `qa-tester` to verify against the acceptance criteria.
- For a medium-large or high-blast-radius change, the reviewer auto-runs a **thermo**
  maintainability audit (advisory). A **nuclear** review (`/code-review ultra`) is billed and
  **user-triggered** — no agent can launch it; the reviewer recommends it and Sean triggers it.
- **PRs stay draft** (`gh pr create --draft`). Un-drafting and merging are Sean's gates.

## Continuity & recovery

A fresh session has no memory of a prior one. Reconstruct from durable sources:

```bash
gh issue list        # open work + acceptance criteria (what/how-far)
gh pr list           # what is built and in review
git status && git log --oneline -20
claude --resume      # restore a prior session when its own reasoning is worth keeping
```

## Testing after changes

```bash
python3 -m unittest discover -s tests
bash -n bin/jumpcode-install
```
