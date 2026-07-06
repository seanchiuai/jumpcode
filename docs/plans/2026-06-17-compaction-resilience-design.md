# Compaction Resilience for the Jumpcode Team — Design

Date: 2026-06-17
Status: approved (brainstorm), pending implementation plan

## Problem

Three failures around context-window compaction degrade a running jumpcode team:

1. **Leads are invisible at the context ceiling.** The existing `UserPromptSubmit` hook
   (`~/.claude/hooks/orchestrator-compact-reminder.py`) only nudges the *orchestrator* about
   *its own* window. A lead can blow past the 200k threshold and nothing ever flags it — the
   orchestrator has no visibility into any lead's occupancy, so it never knows to act.

2. **Post-compaction amnesia makes leads go silent.** When a lead's context is compacted it
   loses the dispatch protocol, so it "finishes" work but forgets to `report-done` to the
   orchestrator — the open loop never closes.

3. **The orchestrator forgets itself on self-compaction.** After compacting, it loses its
   identity, its job, and how it talks to the team (dispatch), and drifts.

## Constraints

- **Jumpcode-only.** The hooks must be a hard no-op for every non-jumpcode Claude session —
  including the user's own ad-hoc `claude` sessions in the same worktrees, and anyone else
  who clones the repo. Achieved by: (a) hooks live in `~/.claude/` user-global config (never
  committed to any repo's `.claude/settings.json`, so they don't exist for other people or for
  non-jumpcode sessions in those repos); (b) double in-process gate — the firing pane must
  carry the `@jumpcode_role` tmux option (set only by `start-webapp`/`revive`) AND a matching
  `state/sessions/<session>.json` must exist for the current tmux session.
- **House rule:** commit/push the `.jumpcode` repo only when Sean asks.
- A Claude pane **cannot self-`/compact`** (it is a user keystroke action) and cannot poll its
  own inbox — both reasons the orchestrator must drive lead compaction.

## Design — three independent components

### Component 1 — Team-wide context visibility (fixes #1)

Extend the existing `orchestrator-compact-reminder.py` (`UserPromptSubmit`, already orchestrator
-scoped). When it fires in the orchestrator pane:

- Resolve the workspace via `state/sessions/<session>.json` matched on the current tmux session
  name (this also serves as scoping gate (b)).
- For each **lead** in that file, compute window occupancy from
  `dirname(orchestrator_transcript_path)/<lead_session_id>.jsonl` using the same metric already
  used for the orchestrator: `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`
  from the last usage-bearing assistant turn. All roles share one project dir (same cwd), so the
  orchestrator's own transcript dir locates every lead's transcript.
- The `additionalContext` (agent) and `systemMessage` (human) now report the whole team and call
  out leads over threshold, e.g.:
  > ⚠ Context: orchestrator ~140k. Over threshold: **backend-lead ~210k**, qa-lead ~205k.
  > Drive their compaction (`recompact`) once each is idle.

Leads remain orchestrator-managed (they cannot self-compact or poll), consistent with
hub-and-spoke. The orchestrator's own threshold reminder is unchanged. Missing/locked lead
transcripts are skipped silently (never block a prompt).

### Component 2 — Auto-rehydration after any compaction (fixes #2 + #3)

New hook `~/.claude/hooks/jumpcode-rehydrate-after-compact.py` registered on `SessionStart`
with `matcher: compact`. Fires in **any** jumpcode pane right after a compaction completes;
hard-gated by (a)+(b) above. It reads `@jumpcode_role` and the workspace from the state file,
then injects role-conditional `additionalContext`:

- **Common (all roles):** "You just compacted. You are the **<role>** in jumpcode workspace
  **<ws>** (root `<workspace_root>`). Re-read your charter (`<roles/<role>.md>`, overlay path
  preferred when present) and the protocol (`roles/_PROTOCOL.md`). You are woken only by
  dispatch — you cannot poll your inbox."
- **Lead variant** adds: "When you finish a task, `dispatch send --kind report-done --reply-to
  <the request DSP-ID>` to the orchestrator. **Right now, tell the orchestrator you're back:**
  `dispatch send --from <role> --to orchestrator --kind notice \"compaction complete —
  rehydrated, resuming\"`."  ← Refinement 1: lead announces compaction-complete so the
  orchestrator gets a live signal instead of silence.
- **Orchestrator variant** adds: "Re-check `dispatch status` for open loops and `health` for
  the team before resuming." (No self-notify.)

Identity comes from the existing charters (DRY) — no separate hand-authored per-role card.
Non-jumpcode panes no-op.

### Component 3 — Orchestrator drives a lead's compaction (the trigger that links #1 → #2)

New verb `jumpcode recompact --role <lead>` (in `.jumpcode/bin/jumpcode`), reusing
`resolve_pane`: into the lead's pane it sends `Escape` (clear any open menu) → types `/compact`
→ `Enter`. No follow-up message is needed — Component 2 auto-rehydrates and (for leads) makes
the lead self-announce. Exposed via a thin `.jumpcode/bin/recompact` wrapper for symmetry with
`dispatch`/`peek`.

The **central orchestrator charter** (`.jumpcode/roles/🧭 orchestrator.md`) gains a short
"Compaction management" section: when the Component-1 hook flags a lead over threshold, wait
until that lead is **idle** (`dispatch status` / `health`) so compaction does not interrupt
in-flight work, then `recompact` it; expect a `notice` that it is back before re-dispatching.

## Data flow

```
orchestrator woken (UserPromptSubmit)
   └─ Component 1 hook: scan team windows → reports "backend-lead ~210k over"
        └─ orchestrator waits for backend-lead idle, runs `recompact --role backend-lead`
             └─ /compact typed into lead pane → compaction runs
                  └─ Component 2 hook (SessionStart=compact) in lead pane:
                       injects rehydrate card → lead re-reads charter, then
                       `dispatch ... --kind notice "compaction complete"`  → orchestrator
```

Orchestrator self-compaction triggers only Component 2 (orchestrator variant).

## Testing

Unit tests under `.jumpcode/tests/` (run `python3 -m unittest discover -s .jumpcode/tests`):

- **Component 1:** multi-role state file + synthetic transcripts → correct per-lead occupancy
  and over-threshold selection; missing/locked transcript is skipped; non-orchestrator pane and
  missing state file → no output.
- **Component 2:** role resolution → correct lead vs orchestrator card; scoping gates (no
  `@jumpcode_role` / no state file) → no output; source != compact → no output.
- **Component 3:** `recompact` resolves the right pane and emits the expected keystroke sequence
  (mock `subprocess`); unknown role → clean error.

Hook scripts are validated by direct invocation with crafted stdin JSON (mirroring the existing
hook's manual-test approach).

## Scope

Shared/global: improves every workspace (bugsmash, obs, seo, ambassador, heatmap,
mobile-native, webapp) at once. Nothing is added to any repo's `.claude/settings.json`.

## Out of scope / YAGNI

- No per-role hand-authored rehydration cards (charters are the source of truth).
- No automatic lead compaction without orchestrator involvement (orchestrator stays the hub;
  avoids interrupting in-flight lead work).
- No change to the 200k threshold or the occupancy metric.
```
