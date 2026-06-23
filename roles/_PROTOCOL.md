# Shared Protocol — How Jumpcode Agents Interact

Every charter in this folder points here. These rules are common to all roles; the
role files only add what is specific to a role. Canonical terms live in
`$JUMPCODE_HOME/CONTEXT.md`; the reasoning behind these rules lives in `$JUMPCODE_HOME/docs/adr/`.

## The one mental model

> The Human (Sean) drives the **orchestrator**, which commands its **team leads**, which
> invoke general **subagents** as a tool. **Projects and tasks live in GitHub issues.** The
> jumpcode only moves messages between visible panes and remembers what was said.

## Where work lives: GitHub issues, not here

- A **project** is a GitHub repo/milestone; a **task** is a GitHub issue. Read and update them
  with the `gh` CLI. There is **no local task registry** — do not look for `task`,
  `run`, or `status` registries; they were retired (ADR 0006).
- "Done" is informal: update the GitHub issue and report via dispatch. There is no
  machine "completion" gate — so the discipline is on you: confirm the acceptance
  criteria *before* you build (see "Confirm the target before building") and report your
  result against them.

## Which repo an issue belongs to

- **Never invent or auto-create a repo.** Issues are filed in **existing** repos only —
  the workspace's own repo.
- The repo for a task is **specified by the Human/orchestrator** — normally
  via the dispatch's `--project <owner/repo>` / `--task #NN`. If you need to
  create an issue and **no repo is specified, STOP and ask** (a lead asks the
  orchestrator; the orchestrator asks Sean). Do **not** guess a repo.

## Dispatch: the only channel

A **dispatch** is one directed message that does two things at once (ADR 0002): it is
**delivered live** (injected into the recipient's pane so it starts immediately) and
**appended to the durable dispatch log**. Send one with:

```bash
$JUMPCODE_HOME/bin/dispatch send \
  --from <your-role> --to <recipient-role> \
  [--project <owner/repo>] [--task #NN] \
  [--subject "<short subject>"] \
  [--kind request|reply|report-done|report-blocked|notice] \
  "<body>"
```

- Default `--kind` is `request`. Use `reply` to answer one, `notice` for FYI.
- `--no-wake` logs without injecting (for scripted/batch use); normal sends always wake.

### On a wake

When your pane is woken, a one-line nudge appears. Read the full message:

```bash
$JUMPCODE_HOME/bin/dispatch inbox <your-role>      # everything addressed to you
$JUMPCODE_HOME/bin/dispatch show <dispatch-id>     # one message in full
```

You cannot poll your own inbox unprompted — you act when woken. After finishing a
unit of work, **always send a report dispatch** so the sender knows; do not assume a
chat message alone counts.

### Confirm the target before building

Before you start work on a `request`, state — in one line back to the sender, or in the
GitHub issue — the **acceptance criteria** you will treat as "done": the observable
condition that, once true, means this task is complete. Pull it from the issue
(`gh issue view`) or from the dispatch body.

If you cannot find or derive clear, checkable criteria, **do not start building** — send a
`reply` (or `report-blocked`) asking the sender to make "done" concrete first. A lead asks
the orchestrator; the orchestrator asks Sean. Declaring the target up front is cheaper than
discovering at report-time that you built to the wrong one.

This is the shared form of the orchestrator's **"do not guess your way through unclear
work"** rule — it binds **every role**. If the intended behavior, scope, or done-condition
is unclear, resolve it before writing code; never make a speculative choice and call it
done. When you report, report your result *against* the criteria you confirmed here.

### Reporting

When a task is done or stuck, send a dispatch back to whoever assigned it **and**
update the GitHub issue. **Always pass `--reply-to <the request's dispatch-id>`** (the id
shown when the request was sent / in `dispatch inbox`): it is what lets `dispatch status`
pair your report to its request precisely and close the open loop. Without it, status
falls back to matching by `--task`, which can't tell two open requests on the same issue
apart.

```bash
# done
$JUMPCODE_HOME/bin/dispatch send --from <your-role> --to orchestrator \
  --kind report-done --task #NN --reply-to <REQUEST-DISPATCH-ID> \
  "Summary; what changed; checks run; open concerns; recommended next step."

# blocked
$JUMPCODE_HOME/bin/dispatch send --from <your-role> --to orchestrator \
  --kind report-blocked --task #NN --reply-to <REQUEST-DISPATCH-ID> \
  "Blocker; why; what you tried; what you need from the orchestrator."
```

## Topology — who may talk to whom (ADR 0001)

```text
Human (Sean) -> orchestrator, any team lead    (Human can type into any pane)
orchestrator -> any team lead, Human (Sean)    (reports go to Sean only)
team lead    -> orchestrator only
team lead    -> its own subagents (a tool, not a pane)
```

- **No lead ↔ lead.** To reach another lead, send the orchestrator a dispatch asking it
  to **relay**. The orchestrator decides whether to forward.
- The Human (Sean) never addresses subagents directly.

## Continuity: always fresh (ADR 0004)

Panes launch as clean Claude agents with no session resume. When a workspace reopens,
you have **no memory** of the prior session. Reconstruct context from the durable
sources: **GitHub issues** (what the work is) and the **dispatch log** (what was said):

```bash
$JUMPCODE_HOME/bin/dispatch log 40
```

## Health checks & subagent visibility

Sean or the orchestrator can snapshot the whole team at any time:

```bash
$JUMPCODE_HOME/bin/health          # per-role: alive/stopped · working/waiting/idle · last-seen · subagents
$JUMPCODE_HOME/bin/health --json   # same, machine-readable
$JUMPCODE_HOME/bin/peek <role> [n] # read-only view of one role's pane (never wakes it)
```

`health` is the whole-team snapshot; `peek` reads a single pane's recent output when you
need to see *what* a lead is actually doing (mid-work, idle, errored, crashed). The
orchestrator uses `peek` to monitor and recover — see its charter.

`health` reads liveness and busy/idle state from your tmux pane directly. But your
**subagents run in-process** and are invisible from outside — so leads must self-report
them. When you spawn or finish a subagent, send a `notice` whose subject follows this
exact convention:

```bash
$JUMPCODE_HOME/bin/dispatch send --from <your-role> --to orchestrator --kind notice \
  --subject "subagent:start <name>" "why you're spawning it"
# ...and when it's done:
$JUMPCODE_HOME/bin/dispatch send --from <your-role> --to orchestrator --kind notice \
  --subject "subagent:end <name>" "result summary"
```

`health` counts `start` minus `end` per role, so an unmatched `start` shows as an active
subagent. Keep names stable between the start and end so they pair up.

### Runtime note (Claude Code vs Codex)

Leads behave identically regardless of which runtime fills their pane (set per role via
`role_runtimes` in the workspace config). Two caveats:

- **Subagents are optional.** A Codex lead may not spawn subagents the way Claude Code
  does. The `subagent:start`/`subagent:end` self-report convention is advisory — absence
  of subagents is normal, not an error.
- **GitHub access depends on the `gh` CLI.** GitHub issues are the system of record. A Codex
  lead can only read/update issues if the `gh` CLI is authenticated in its environment.
  If yours is not, report progress via `dispatch` and let the orchestrator make
  the GitHub writes.

## Guardrails are soft (v1)

Your charter names the territory you own and what to leave alone. These are
**advisory** — not enforced by permissions. The convention: stay in your domain, and
relay cross-domain work through the orchestrator rather than reaching across.
