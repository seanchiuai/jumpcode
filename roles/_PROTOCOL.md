# Shared Protocol — How Jumpcode Agents Interact

Every specialist agent definition and the orchestrator charter point here. These rules are
common to all roles; the role files add only what is specific to a role. Canonical terms live
in `CONTEXT.md`; the reasoning lives in `docs/adr/`.

## The one mental model

> Sean drives the **orchestrator** (his main Claude Code session), which spawns **specialist
> subagents** with the Agent tool and continues them with **SendMessage**. **Projects and
> tasks live in GitHub Issues.** The runtime moves work between agents and holds their live
> transcripts; GitHub holds the durable truth.

## Where work lives: GitHub Issues, not here

- A **project** is a GitHub repo/milestone; a **task** is a GitHub issue. Read and update them
  with the `gh` CLI. There is **no local task registry** (ADR 0006).
- **Never invent or auto-create a repo.** File issues in the workspace's own repo only. If a
  repo is unspecified, **stop and ask** (a specialist asks the orchestrator; the orchestrator
  asks Sean).
- "Done" is informal: there is no machine completion gate. So confirm the acceptance criteria
  *before* you build and report your result against them.

## Spawning and continuing agents (the native channel)

- The orchestrator **spawns** a specialist with the Agent tool, passing the task, its
  acceptance criteria, and the issue number. The specialist runs (in the background by
  default) and **returns its report as its final message**.
- The orchestrator **continues** a running or finished specialist with **`SendMessage`**
  (addressing it by agent id or name) — a nudge, correction, or next step. The agent already
  holds its context; there is no keystroke injection and no inbox to poll.
- **Monitor** the team with the Agent view (`claude agents`, `--json`, `claude logs <id>`).

## Confirm the target before building

Before you start a task, state — back to the orchestrator or in the GitHub issue — the
**acceptance criteria** you will treat as "done": the observable condition that means the task
is complete. Pull it from the issue (`gh issue view`) or the task you were handed. If you
cannot find or derive clear, checkable criteria, **do not start building** — return a blocked
report asking to make "done" concrete first. This binds every role: never make a speculative
choice and call it done.

## Reporting

A specialist's **returned final message is its report.** Make it explicit — done or blocked —
and also reflect the outcome in the GitHub issue:

- **Done:** summary; what changed; checks run; open concerns; recommended next step.
- **Blocked:** the blocker; why; what you tried; what you need from the orchestrator.

Do not assume a passing test alone counts as a report; state the verdict against the criteria
you confirmed.

## The browser boundary (hard)

- **Only the reviewer (`code-reviewer`) and tester (`qa-tester`) drive a browser** — Claude in
  Chrome (`mcp__claude-in-chrome__*`) or Playwright. They own **all** browser automation:
  rendered/public output, e2e, and smoke flows.
- **Coding leads are denied the browser MCP servers** in their agent definitions — the runtime
  blocks it. If a lead's task needs browser verification, it flags that in its report for the
  orchestrator to route to the reviewer or tester.
- **The orchestrator never drives a browser.** It is the main session, so this is a behavioral
  rule (context hygiene), not a permission — it always delegates browser work.

## Never sit on an interactive prompt

Specialists run unattended. Do not open a blocking question UI, enter plan-approval mode, or
stop on a yes/no confirm — nothing will press a key. When you would ask a question, **put it in
your report** instead (a specialist to the orchestrator; the orchestrator to Sean), state your
best-guess default, and keep going on anything not blocked by it. Prefer decide-and-note for
low-risk, reversible choices; reserve questions for genuine decision gates.

## Topology — who talks to whom (ADR 0001)

```text
Sean (Human) -> orchestrator, any specialist   (Sean can address any agent)
orchestrator -> any specialist                  (spawn / SendMessage)
orchestrator -> Sean                             (reports go to Sean only)
specialist   -> orchestrator                     (returns its report)
specialist   ✗  specialist                       (no direct channel — ask the orchestrator to relay)
```

Native subagents cannot address each other, so hub-and-spoke is enforced by the substrate. A
specialist that needs another asks the orchestrator to **relay**. Hub-and-spoke is the default;
for a tiny task the orchestrator may work inline (it is optional, not mandatory).

## Continuity & recovery (ADR 0004 / 0008)

A fresh session has no memory of a prior one. Reconstruct from durable sources only — never
from ephemeral agent state (the Task tools' state is session-local, not truth):

1. `gh issue list` / `gh issue view` — what the work is and how far it got.
2. Git state — `git status`, `git log`, `gh pr list` / `gh pr view` — what is built and in
   review.
3. `claude --resume` when restoring an agent's own prior reasoning is worth more than a clean
   slate.

## Guardrails

Your role file names the territory you own and what to leave alone. Stay in your domain and
relay cross-domain work through the orchestrator. The **browser boundary above is enforced**
for coding leads (denied in frontmatter); the territory boundaries are conventions — honor
them.
