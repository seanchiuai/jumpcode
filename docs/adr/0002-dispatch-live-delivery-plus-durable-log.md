# Dispatch: Live Delivery + Durable Log

> **SUPERSEDED (2026-07-17) by [ADR 0008](0008-native-claude-code-orchestration.md).** The
> dispatch CLI, keystroke wake, and JSONL dispatch log are retired. Their jobs are now done by
> the Agent tool + `SendMessage` (delivery/continuation), the Agent view (monitoring), and
> GitHub Issues + git state (durable continuity). Kept for history.


Inter-actor communication is modeled as a **dispatch**: a single action that both (1) delivers live by injecting a prompt into the recipient's Claude pane so it gets to work immediately, and (2) appends one line to a durable, append-only log. Chosen over fire-and-forget injection (no record) and over a passive check-your-inbox mailbox.

## Why both halves

- **Live delivery (the webhook half).** A Claude agent in a pane cannot poll — it goes idle after finishing and waits for input. So the only way to make a lead "get to work" is to inject keystrokes into its pane (a **wake**), targeted by the pane's stable `@role` border label (not its title, which Claude overwrites).
- **Durable log (the continuity half).** An injected keystroke leaves no trace. Sean's recurring failure mode is "I lost the agent I was working with." The durable log is what lets a restarted agent — or Sean — reconstruct what was asked. (This is not hypothetical: the entire project history was rebuilt from these logs during the dev takeover.) The log is the recovery/review path; it is not how delivery happens.

Rejected: **fire-and-forget** (loses the rebuild-after-losing-an-agent superpower) and **poll-the-mailbox** (a Claude pane can't poll, and it makes delivery passive/slow).

## What gets logged

Only the orchestrator's two boundaries:

- **Sean (Human) ↔ Orchestrator**
- **Orchestrator ↔ Team Leads** (including reports)

Deferred: capturing the actual *substance/output* of an agent's work (self-report vs pane-scrape). For now agents self-author summaries via reports; richer output capture is a later decision.

## Consequences

- Communication that bypasses the CLI is invisible to the log: a Human typing directly into the orchestrator pane, or an orchestrator merely printing output instead of dispatching it. Closed by role-prompt discipline ("send through the tool"), not by scraping.
- The wake trigger for v1 is sender-triggered (the send action also wakes the recipient); a watcher daemon is deferred (see the no-daemon stance in the v1 design).
