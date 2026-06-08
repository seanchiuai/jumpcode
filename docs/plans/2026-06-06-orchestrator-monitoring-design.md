# Design: Orchestrator-as-Monitor (status & report-back, lean v1)

**Date:** 2026-06-06
**Status:** Approved (brainstormed with Sean)

## Problem

The jumpcode can confirm a dispatch's keystrokes were *delivered* (`woke: true`), but it
cannot tell whether a lead is **still working**, **finished but forgot to report**, or
**errored/crashed**. From the outside, all three present as a quiet pane. So an
unanswered request is indistinguishable from a completed one, and a "sitting agent that
finished without informing the orchestrator" is invisible.

## Decision

Do **not** build dedicated machinery (Stop hooks, a status engine, a launchd watcher).
Instead **generalize: give the orchestrator the power to monitor and recover**, and let
its judgment do the work. The orchestrator is already a Claude agent with shell access;
it only needs *eyes* and a *mandate*.

This is a deliberate lean trade — see "What we give up".

## What gets built

### 1. `peek` — the orchestrator's eyes

A new read-only command + wrapper:

```
./.jumpcode/bin/peek <role> [lines]
```

- Resolves the role's pane via the existing `resolve_pane` (`@jumpcode_role`) and
  `resolve_session` (`$TMUX` / `JUMPCODE_TMUX_SESSION`).
- Prints `tmux capture-pane -p -S -<lines>` for that pane (default ~50 lines of
  scrollback) so the caller can read what the lead is doing: mid-work (spinner), idle at
  an empty prompt, an API/error banner, or a dead shell.
- Graceful, non-crashing messages when the session or pane isn't found (workspace closed).
- Read-only: never sends keys. (To *act*, the orchestrator uses `dispatch send`, which wakes.)

### 2. Orchestrator charter — "Monitoring & recovery" section

Add to `roles/🧭 orchestrator.md` (and a short pointer in `roles/_PROTOCOL.md`):

- **You own watching your leads.** After you dispatch work, check back rather than
  assuming completion. Your tools: `peek <role>` (read a pane) and `dispatch log` (what
  you asked vs. what came back).
- **Reading state from a peek:** advancing spinner/timer = working; static empty `❯`
  prompt = idle/finished-its-turn; an error banner = errored; a shell prompt (no
  `claude`) = crashed.
- **Conservative recovery:** for a transient error or a lead idle-without-reporting,
  **re-wake it to retry** — `dispatch send --from orchestrator --to <role> --task <T>
  "status? continue/retry SEA-…"`. If it still fails after ~2 nudges, or the error is
  non-transient (auth/quota exhausted, crashed pane, a bug in the jumpcode CLI itself),
  **escalate to Sean** with the diagnosis you read from the pane. Do **not** auto-answer
  permission dialogs, respawn panes, or edit the jumpcode tooling (that's Hermes's job).

## What we give up (accepted)

- **No autonomous timer.** The orchestrator only checks when it is *awake* (just after
  dispatching, when a lead reports back, or when Sean prompts it). If everything —
  including the orchestrator — goes silent, nothing external is watching; **Sean is the
  backstop of last resort.**
- **No hard report-back guarantee.** Report-back stays advisory (charter instruction).
  The orchestrator catches a silent-finish by *looking* (`peek`), not by a hook
  *preventing* it.

These were chosen over the heavier 3-layer design (Stop hook + status engine + launchd
watcher) for simplicity in v1. The heavier design remains a documented future option if
the lean version proves insufficient.

## Architecture / data flow

```
Sean ──prompt──▶ orchestrator
orchestrator ──dispatch(wake)──▶ lead   (work)
orchestrator ──peek──▶ reads lead's pane (read-only tmux capture)
   ├─ working      → wait
   ├─ idle, no report → re-wake "status?/report"   (retry, transient)
   ├─ error banner → re-wake retry ×~2, else escalate to Sean
   └─ dead shell   → escalate to Sean (needs relaunch)
lead ──dispatch report-done/blocked(wake)──▶ orchestrator   (loop closes)
```

## Components

| Component | Where | Notes |
|---|---|---|
| `peek <role> [lines]` | `bin/jumpcode` (`cmd_peek`) + `bin/peek` wrapper | reuses `resolve_pane`/`resolve_session`; read-only |
| Monitoring & recovery | `roles/🧭 orchestrator.md` + `roles/_PROTOCOL.md` pointer | conservative posture |

## Error handling

- Session/pane not found → print a clear "workspace not running / unknown role"
  message, exit non-zero, never traceback.
- `peek` never mutates a pane.
- Recovery boundary is enforced by instruction, not code (soft, per v1 guardrails).

## Testing

- Reuses already-tested `resolve_pane`. The new `cmd_peek` arg/branch handling (unknown
  role, no session) is unit-testable by stubbing the session/capture; the `tmux
  capture-pane` IO itself is verified once manually against a live pane.
- Live check: with the workspace up, `./.jumpcode/bin/peek backend-lead` prints
  that pane's content.

## Out of scope (future, if lean proves insufficient)

- Stop hook to *prevent* silent-finish.
- Computed `dispatch status` (open-loops + working/idle/dead classification).
- launchd watcher pinging the orchestrator / notifying Sean when the orchestrator is down.
