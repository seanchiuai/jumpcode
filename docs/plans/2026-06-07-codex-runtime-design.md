# Design: Multi-runtime support — add Codex alongside Claude Code (mixed teams)

**Date:** 2026-06-07
**Status:** Approved (brainstormed with Sean)

## Problem

Every jumpcode pane runs Claude Code. The launcher hardcodes one binary
(`start-webapp:6` `CLAUDE_BIN`, `:41` `exec "$CLAUDE_BIN"`) for all panes, and health
detection keys off Claude's literal status strings (`jumpcode:287-288`). Sean wants
**mixed teams** — a lead can run **Codex** while others run Claude, chosen per role for
whatever each is best at. Runtime should be a per-role knob, not a rebuild.

## Prior art (this validates the shape; it does not replace it)

"Don't reinvent the wheel" is a *validation* instruction. Three independent tools confirm
each piece of this design:

| Our piece | Established equivalent |
|---|---|
| `role_runtimes` per-role knob | **Claude Squad** profiles — `{ "name": "codex", "program": "codex" }` (`~/.claude-squad/config.json`) |
| runtime-keyed `pane_state` (idle/busy/waiting) | **ccmanager** "per-agent state detection strategy" — same three states |
| visible tmux panes + send-keys | common substrate across claude-squad, ccmanager, Tmux-Orchestrator, AMUX |
| hook/event-driven state (deferred, below) | **tmai** `attention: started\|halted\|completed` via runtime hooks (no polling) |

What is genuinely *ours* and absent from all of them: the coordination layer —
**Linear-as-system-of-record, the dispatch log, Hermes, hub-and-spoke charters, and
`@jumpcode_role` wake targeting**. That is why we **extend our launcher rather than adopt
one of these tools**: they are worktree-per-task TUIs with their own UX; bolting our
Linear/dispatch/Hermes model onto Claude Squad is more friction than ~30 lines in
`start-webapp`.

## Decision

Add a **thin, per-role runtime knob** plus a small **structured runtime descriptor**
inline in the launcher. Borrow proven *patterns* (profiles, runtime-keyed three-state
detection). Do **not** introduce a new config-file abstraction, an indirection layer, or
event-hook plumbing in v1. Everything already runtime-agnostic (dispatch log, wake,
`@jumpcode_role`, hub-and-spoke) is untouched.

## Empirically settled (live spike, 2026-06-07)

A throwaway tmux session running the app-bundled Codex (`codex-cli 0.137.0-alpha.4`,
`/Applications/Codex.app/Contents/Resources/codex`) confirmed:

- **Initial prompt**: `codex [PROMPT]` seeds an interactive session (also stdin via `-`).
- **Wake mechanics port**: typed text **echoes** verbatim into Codex's composer (so
  `_injected_text_present` finds its needle), and **`C-u` clears** the input line — the
  two load-bearing halves of `wake_pane`. Verified without submitting a turn.
- **Waiting marker confirmed live**: Codex's first-run trust prompt shows `1. Yes,
  continue`, which the existing `_WAITING_MARKERS` already matches.
- **Codex config has no Linear MCP** (only `pencil`, `node_repl`) — see Prerequisites.

**Busy marker — now confirmed live (2026-06-07).** A controlled throwaway turn on
`0.137.0-alpha.4` showed the busy status line as `• Working (Ns • esc to interrupt)`,
which contains `esc to interrupt` and so matches `_RUNTIME_MARKERS["codex"]["busy"]`. No
code change was needed; the earlier "to-verify" caveat is closed.

## What gets built

### 1. `role_runtimes` in `workspace.json`

A new optional map beside `role_emojis`:

```json
"role_runtimes": { "backend-lead": "codex" }
```

Any role not listed defaults to `claude`. The orchestrator stays `claude` unless
explicitly overridden (it owns Linear writes + escalation).

### 2. Structured runtime descriptor in `start-webapp` (inline, data-shaped)

A small lookup keyed by runtime name, each entry: `{program, busy_markers,
waiting_markers}`. Borrow Claude Squad's *shape*, not a `runtimes.json` file (YAGNI until
a third runtime arrives).

- `claude` → program `$CLAUDE_BIN` (`claude`)
- `codex`  → program `$CODEX_BIN`, defaulting to the working app binary
  `/Applications/Codex.app/Contents/Resources/codex` (the npm/brew `codex` currently has
  a missing native binary — broken).

`agent_cmd` gains a runtime arg to pick the program. Seeding uses the **same** two-step
send-keys injection for both runtimes (reuses the verify-hardened path; `codex [PROMPT]`
is not needed). Each pane is tagged with **`@jumpcode_runtime`** at launch, mirroring the
existing `@jumpcode_role` option.

### 3. Runtime-keyed `pane_state()` in `bin/jumpcode`

`pane_state(capture_text, runtime="claude")` selects the marker set for that runtime.
`cmd_health` reads each pane's `@jumpcode_runtime` (added to the `list-panes -F` format
string alongside `@jumpcode_role`) and passes it in. Three states unchanged:
`working` | `waiting` | `idle` (ccmanager's model). Markers become a per-runtime table
rather than two module globals.

### 4. Charters / protocol — minor notes only

Leads behave identically regardless of runtime. Two small notes in `_PROTOCOL.md`:
- A Codex lead may not spawn subagents the way Claude does — the subagent self-report
  convention stays **optional** (absence is fine; `active_subagents` already tolerates it).
- The Linear-as-SoT instruction assumes the user has wired Codex's Linear MCP (below).

## Architecture / data flow

```
workspace.json  role_runtimes: { backend-lead: codex }
        │
start-webapp ──per role──▶ RUNTIME[name] = {program, busy_markers, waiting_markers}
        ├─ launch pane with that program  (exec claude | exec codex)
        ├─ set @jumpcode_role     (wake target — unchanged)
        └─ set @jumpcode_runtime  (state-detection selector — NEW)
        │
dispatch send ──wake_pane (C-u → type → capture-verify → Enter)──▶ pane   (runtime-agnostic)
        │
health ──list-panes @jumpcode_role + @jumpcode_runtime──▶ pane_state(capture, runtime)
        └─ working | waiting | idle   (per-runtime markers)
```

## Components

| Component | Where | Notes |
|---|---|---|
| `role_runtimes` map | `workspaces/webapp/workspace.json` | optional; default `claude` |
| runtime descriptor + `@jumpcode_runtime` | `bin/start-webapp` | inline, data-shaped; default `CODEX_BIN` = app binary |
| runtime-keyed `pane_state` | `bin/jumpcode` (`cmd_health`) | reads `@jumpcode_runtime`; per-runtime marker table |
| subagent/Linear notes | `roles/_PROTOCOL.md` | advisory |

## Error handling

- Unknown runtime name in `role_runtimes` → launcher warns and falls back to `claude` for
  that role (never aborts the whole launch — mirrors the existing tolerant-split posture).
- Missing `$CODEX_BIN` → the existing `command -v` preflight check is extended to validate
  every runtime actually referenced by the workspace, with a clear message, before any
  pane is created.
- `pane_state` with an unknown/absent `@jumpcode_runtime` → default to the `claude` marker
  set (safe; the working/waiting markers largely overlap).

## Testing

- **Unit (`tests/test_health.py`)**: `pane_state(capture, runtime)` against captured
  Codex screens from the spike — the trust/`1. Yes` **waiting** capture (confirmed) and an
  **idle** composer capture (confirmed); a **busy** capture added once observed live. Plus
  the existing Claude captures, asserting the runtime arg selects the right set.
- **Launcher (headless, `CLAUDE_BIN=cat`/`CODEX_BIN=cat` throwaway session)**: assert each
  pane gets the correct `@jumpcode_runtime` for a mixed `role_runtimes`, and that an unknown
  runtime falls back to `claude`. (Same throwaway-session style as the geometry test.)
- **Live (one mixed launch)**: a webapp launch with one Codex lead; drive a `dispatch
  send` to it and read the `woke` flag; run `health` and **confirm the Codex busy marker**
  (closes the to-verify gap); confirm a round-trip report-done. Never touches a real run
  beyond this check.

## Prerequisites (Sean owns these — documented, not automated)

- A **runnable codex binary** (reinstall the standalone CLI, or keep `CODEX_BIN` pointed at
  the app binary).
- **Linear MCP in `~/.codex/config.toml`** (`[mcp_servers.linear]` + OAuth). Without it a
  Codex lead cannot reach the system of record. Sean: *"i'll take care of it."*
- **Trust** the workspace/repo dirs for Codex, so the pane reaches its composer instead of
  sitting on the trust prompt.

## Out of scope (deferred; best-practice ≠ build-it-now)

- **Event/hook-driven state** (tmai's pattern; Codex's `notify` `turn-ended` hook). The
  robust, polling-free mechanism — but string-scraping is spike-proven, and the Codex
  route means editing Sean's `~/.codex/config.toml` `notify` array (already pointing at his
  computer-use app). His to own. Documented as the recommended future improvement; no
  indirection layer built for it now (YAGNI until a second consumer).
- **git-worktree-per-agent** (near-universal in claude-squad/AMUX/Conductor). Solves
  parallel-branch racing; our model is domain-partitioned leads on a *shared* repo
  coordinated via Linear — a different problem. Not changing it.
- **Codex `app-server`/`remote-control` transport** — cleaner than send-keys in theory,
  but a different transport from the visible-pane model we just hardened. Defer.
- **A/B comparison, whole-workspace runtime flag, auto-wiring MCP, a `runtimes.json`
  file** — all rejected/deferred per YAGNI.
