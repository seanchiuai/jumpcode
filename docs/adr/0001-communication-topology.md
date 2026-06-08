# Communication Topology

The jumpcode uses a strict hub-and-spoke topology with the orchestrator as the hub, chosen over a free mesh so that all coordination has one accountable point and the message graph stays legible as agents multiply.

## The graph

```
Human  ⇄  Hermes
Human  →  Orchestrator,  Team Leads        (human may type into any visible pane)
Hermes →  Orchestrator                     (NOT leads — Hermes routes through the orchestrator)
Hermes →  workspace config                 (Hermes is the only actor that edits the system)
Orchestrator  →  Human, Hermes             (readable output)
Orchestrator  →  all Team Leads            (commands)
Team Lead     →  Orchestrator              (reports; may request a relay to another lead)
Team Lead     ✗  Team Lead                 (no direct channel — use Relay)
Lead          →  Subagents               (invokes general, repo-agnostic Claude Code subagents)
Human/Hermes  ✗  Subagents               (never address subagents directly)
```

## Key asymmetry

The **Human** may talk to team leads directly (they are visible panes the human can type into), but **Hermes** may not — Hermes commands only the orchestrator. This keeps the programmatic hierarchy clean (one machine-driven path) while preserving the human's freedom at the visible jumpcode.

## Relay

There is no lead-to-lead channel. A lead that needs another lead asks the orchestrator, which — being an intelligent agent, not a dumb router — decides whether to forward.

## Status

Accepted. The current role prompts encode most of this; the CLI does not yet enforce it (routing is advisory). Enforcement, if added, must allow the Human→lead direct path.
