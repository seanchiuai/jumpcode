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
update the Linear issue:

```bash
# done
./.agent-cockpit/bin/dispatch send --from <your-role> --to orchestrator \
  --kind report-done --task <LINEAR-ISSUE> \
  "Summary; what changed; checks run; open concerns; recommended next step."

# blocked
./.agent-cockpit/bin/dispatch send --from <your-role> --to orchestrator \
  --kind report-blocked --task <LINEAR-ISSUE> \
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

## Guardrails are soft (v1)

Your charter names the territory you own and what to leave alone. These are
**advisory** — not enforced by permissions. The convention: stay in your domain, and
relay cross-domain work through the orchestrator rather than reaching across.
