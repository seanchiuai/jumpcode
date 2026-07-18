# Jumpcode

Jumpcode is a small **behavioral contract for multi-agent software delivery**, expressed as a
pack of native Claude Code agent definitions. It gives you a non-coding, accountable
orchestrator that decomposes a goal into GitHub Issues and commands named specialists —
coding leads plus an independent reviewer and tester — with clear ownership boundaries,
done/blocked reporting, and human decision gates.

It runs entirely on **Claude Code's native orchestration primitives** — subagents, the Agent
view, `SendMessage`, git worktrees, hooks, and session resume. There is no daemon, no custom
process manager, no message bus. An earlier version shipped a tmux/dispatch/wake engine of its
own; that infrastructure has been retired (see [`docs/adr/0008`](docs/adr/0008-native-claude-code-orchestration.md)).

For canonical terms see [`CONTEXT.md`](CONTEXT.md); for the operator manual see
[`INSTRUCTIONS.md`](INSTRUCTIONS.md); for the decisions see [`docs/adr/`](docs/adr/). The ADRs
are the authority if anything here conflicts.

## The one mental model

> Sean drives the **orchestrator** (his main Claude Code session), which spawns **specialist
> subagents** with the Agent tool and continues them with `SendMessage`. **Projects and tasks
> live in GitHub Issues.** The runtime moves work between agents and holds their live
> transcripts; GitHub holds the durable truth.

## Roles

- **Orchestrator** — your main interactive session, rooted in the target repo's worktree.
  Non-coding and accountable: it decomposes goals into GitHub Issues, spawns specialists,
  integrates their reports, and owns the Sean-facing gates. It **never drives a browser**. Its
  charter is [`roles/orchestrator.md`](roles/orchestrator.md).
- **Coding leads** — `backend-lead`, `frontend-lead`, `devops-lead`: specialists that own a
  territory and report back. Denied browser tools at the frontmatter level.
- **Reviewer** — `code-reviewer`: the independent merge-gate. **Owns browser automation** for
  verifying rendered/public output.
- **Tester** — `qa-tester`: independent verification. **Owns browser automation** for e2e and
  smoke flows.

The specialists live in [`.claude/agents/`](.claude/agents/) as native subagent definitions.

## The browser boundary (the one hard rule)

Only the **reviewer** and **tester** perform browser automation — Claude in Chrome
(`mcp__claude-in-chrome__*`) or Playwright. This is enforced, not advisory: the coding leads
list the browser MCP servers in `disallowedTools`, so the runtime blocks them. The
orchestrator never drives a browser either; because the main session cannot be governed by an
agent definition, that is a behavioral rule (browser automation floods the orchestrator's
context and destroys its ability to hold the whole workload). When a task needs a browser, the
orchestrator delegates it to the reviewer or tester.

## Install the agent pack

Native agent discovery reads `<cwd>/.claude/agents/` and `~/.claude/agents/` — it never looks
inside `.jumpcode/`. So this repo is the **canonical source** of the pack; adoption copies it
to where Claude Code looks:

```bash
# Per workspace (recommended): install into the target repo worktree the orchestrator runs in
./.jumpcode/bin/jumpcode-install --project ~/Desktop/webapp/.worktrees/<slug>

# Permanent personal team: install into your user scope
./.jumpcode/bin/jumpcode-install --user

# Ad-hoc, no copy: point Claude Code at the source pack at launch
claude --agents ./.jumpcode/.claude/agents
```

The installer places the five specialists under `.claude/agents/` and the orchestrator charter
+ shared protocol under `.claude/agents/jumpcode/`, so a fresh session rooted at the target can
read all of them. (If your environment names its browser MCP servers differently from
`mcp__claude-in-chrome` / `mcp__playwright-*`, adjust the `tools`/`disallowedTools` lines in the
agent files to match.)

## Run a goal

1. Start Claude Code in the target repo's worktree — this session is your orchestrator.
2. Have it read `roles/orchestrator.md` (installed under `.claude/agents/jumpcode/`).
3. Hand it the goal. It files GitHub Issues, spawns the specialists it needs, watches them in
   the Agent view (`claude agents`), continues them with `SendMessage`, and integrates their
   reports into one update for you — holding merges at the review/test gate.

## Where work lives: GitHub Issues

A **project** is a GitHub repo/milestone; a **task** is a GitHub issue (ADR 0006). Agents read
and update them via the `gh` CLI. Jumpcode keeps **no** local copy of project/task state. The
runtime's own agent/task state is ephemeral and session-local — a live convenience, never
durable truth. "Done" is informal: update the GitHub issue and report.

## Recovery

A fresh or resumed session reconstructs from durable sources only:

1. `gh issue list` / `gh issue view` — what the work is and how far it got.
2. Git state — `git status`, `git log`, `gh pr list` / `gh pr view` — what is built and in
   review.
3. `claude --resume` when restoring the orchestrator's own prior reasoning is worth more than a
   clean slate.

## Human decision gates (Sean's, always)

- Merging to a shared branch, and un-drafting a PR (PRs open with `gh pr create --draft`).
- Triggering a nuclear review (`/code-review ultra` is billed and user-triggered; agents cannot
  launch it).
- Flipping a repo public, force-pushing, or any other outward-facing/irreversible step.

## Tests

```bash
python3 -m unittest discover -s tests
```
