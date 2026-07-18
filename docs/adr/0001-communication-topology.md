# Communication Topology

> **Still in force (as of [ADR 0008](0008-native-claude-code-orchestration.md)).** Hub-and-spoke
> is now *enforced by the substrate*: native subagents return to the orchestrator and cannot
> address each other. "Human types into a pane" reads as "Sean addresses any agent"; a lead's
> relay request is a message to the orchestrator. Below, read *dispatch/mail* as *spawn /
> SendMessage / return*.


The jumpcode uses a strict hub-and-spoke topology with the orchestrator as the hub, chosen over a free mesh so that all coordination has one accountable point and the message graph stays legible as agents multiply.

## The graph

```
Human (Sean)  →  Orchestrator,  Team Leads   (human may type into any visible pane)
Human (Sean)  →  workspace config            (the human is the only actor that edits the system)
Orchestrator  →  Human (Sean)                (readable output; reports go to Sean only)
Orchestrator  →  all Team Leads              (commands)
Team Lead     →  Orchestrator                (reports; may request a relay to another lead)
Team Lead     ✗  Team Lead                   (no direct channel — use Relay)
Lead          →  Subagents                   (invokes general, repo-agnostic Claude Code subagents)
Human (Sean)  ✗  Subagents                   (never address subagents directly)
```

## Key point

Sean (the Human) is the single actor above the orchestrator: he drives the orchestrator, may talk to any team lead directly (they are visible panes he can type into), and is the only actor that edits the system/config. The orchestrator reports back to Sean only. There is no separate machine-driven orchestration layer above the orchestrator.

## Relay

There is no lead-to-lead channel. A lead that needs another lead asks the orchestrator, which — being an intelligent agent, not a dumb router — decides whether to forward.

## Status

Accepted. The current role prompts encode most of this; the CLI does not yet enforce it (routing is advisory). Enforcement, if added, must allow the Human (Sean)→lead direct path. (Revised 2026-06-23: removed the former external meta-orchestrator layer; Sean is the sole driver above the orchestrator.)
