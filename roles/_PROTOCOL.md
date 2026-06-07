# Shared Protocol — How Cockpit Agents Interact

Every charter in this folder points here. These rules are common to all roles; the
role files only add what is specific to a role. Canonical terms live in
`../CONTEXT.md`; the reasoning behind these rules lives in `../docs/adr/`.

## The one mental model

> Human + Hermes drive the **orchestrator**, which commands its **team leads**, which
> invoke general **subagents** as a tool. **Projects and tasks live in Linear.** The
> cockpit only moves messages between visible panes and remembers what was said.

## Where work lives: Linear, not here

- A **project** is a Linear project; a **task** is a Linear issue. Read and update them
  with the Linear MCP. There is **no local task registry** — do not look for `task`,
  `run`, or `status` registries; they were retired (ADR 0003).
- "Done" is informal: update the Linear issue and report via dispatch. There is no
  machine "completion" gate.

## Dispatch: the only channel

A **dispatch** is one directed message that does two things at once (ADR 0002): it is
**delivered live** (injected into the recipient's pane so it starts immediately) and
**appended to the durable dispatch log**. Send one with:

```bash
./.agent-cockpit/bin/dispatch send \
  --from <your-role> --to <recipient-role> \
  [--project <LINEAR-PROJECT>] [--task <LINEAR-ISSUE>] \
  [--subject "<short subject>"] \
  [--kind request|reply|report-done|report-blocked|notice] \
  "<body>"
```

- Default `--kind` is `request`. Use `reply` to answer one, `notice` for FYI.
- `--no-wake` logs without injecting (for scripted/batch use); normal sends always wake.

### On a wake

When your pane is woken, a one-line nudge appears. Read the full message:

```bash
./.agent-cockpit/bin/dispatch inbox <your-role>      # everything addressed to you
./.agent-cockpit/bin/dispatch show <dispatch-id>     # one message in full
```

You cannot poll your own inbox unprompted — you act when woken. After finishing a
unit of work, **always send a report dispatch** so the sender knows; do not assume a
chat message alone counts.

### Reporting

When a task is done or stuck, send a dispatch back to whoever assigned it **and**
update the Linear issue. **Always pass `--reply-to <the request's dispatch-id>`** (the id
shown when the request was sent / in `dispatch inbox`): it is what lets `dispatch status`
pair your report to its request precisely and close the open loop. Without it, status
falls back to matching by `--task`, which can't tell two open requests on the same issue
apart.

```bash
# done
./.agent-cockpit/bin/dispatch send --from <your-role> --to orchestrator \
  --kind report-done --task <LINEAR-ISSUE> --reply-to <REQUEST-DISPATCH-ID> \
  "Summary; what changed; checks run; open concerns; recommended next step."

# blocked
./.agent-cockpit/bin/dispatch send --from <your-role> --to orchestrator \
  --kind report-blocked --task <LINEAR-ISSUE> --reply-to <REQUEST-DISPATCH-ID> \
  "Blocker; why; what you tried; what you need from the orchestrator."
```

## Topology — who may talk to whom (ADR 0001)

```text
Human  -> orchestrator, any team lead          (Human can type into any pane)
Hermes -> orchestrator only
orchestrator -> any team lead, Human, Hermes
team lead    -> orchestrator only
team lead    -> its own subagents (a tool, not a pane)
```

- **No lead ↔ lead.** To reach another lead, send the orchestrator a dispatch asking it
  to **relay**. The orchestrator decides whether to forward.
- Neither Human nor Hermes addresses subagents directly.

## Continuity: always fresh (ADR 0004)

Panes launch as clean Claude agents with no session resume. When a workspace reopens,
you have **no memory** of the prior session. Reconstruct context from the durable
sources: **Linear** (what the work is) and the **dispatch log** (what was said):

```bash
./.agent-cockpit/bin/dispatch log 40
```

## Health checks & subagent visibility

Hermes or the orchestrator can snapshot the whole team at any time:

```bash
./.agent-cockpit/bin/health          # per-role: alive/stopped · working/waiting/idle · last-seen · subagents
./.agent-cockpit/bin/health --json   # same, machine-readable
./.agent-cockpit/bin/peek <role> [n] # read-only view of one role's pane (never wakes it)
```

`health` is the whole-team snapshot; `peek` reads a single pane's recent output when you
need to see *what* a lead is actually doing (mid-work, idle, errored, crashed). The
orchestrator uses `peek` to monitor and recover — see its charter.

`health` reads liveness and busy/idle state from your tmux pane directly. But your
**subagents run in-process** and are invisible from outside — so leads must self-report
them. When you spawn or finish a subagent, send a `notice` whose subject follows this
exact convention:

```bash
./.agent-cockpit/bin/dispatch send --from <your-role> --to orchestrator --kind notice \
  --subject "subagent:start <name>" "why you're spawning it"
# ...and when it's done:
./.agent-cockpit/bin/dispatch send --from <your-role> --to orchestrator --kind notice \
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
- **Linear access depends on the runtime's MCP.** Linear is the system of record. A Codex
  lead can only read/update Linear if `~/.codex/config.toml` has a `[mcp_servers.linear]`
  entry. If yours does not, report progress via `dispatch` and let the orchestrator make
  the Linear writes.

## Guardrails are soft (v1)

Your charter names the territory you own and what to leave alone. These are
**advisory** — not enforced by permissions. The convention: stay in your domain, and
relay cross-domain work through the orchestrator rather than reaching across.
