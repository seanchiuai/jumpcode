> **SUPERSEDED (2026-06-06):** This audit predates the grilled-design rebuild. The dispatch rewrite and Linear-as-system-of-record (see CONTEXT.md + docs/adr/0001–0004 + docs/plans/2026-06-06-jumpcode-rebuild.md) resolved or obsoleted most items here. Kept for history.

# Jumpcode — Code Audit & Roadmap

Date: 2026-06-06. Author: Hermes (dev takeover). Status: review only, no system changes made.

## Summary

The jumpcode is well-built: a clean ~446-line single-file Python core (`bin/jumpcode`), event-sourced append-only JSONL, deterministic state reconstruction, thin bash wrappers, 5 passing tests. Design discipline is good (mail = source of truth; no daemon/db/cloud; only DONE/BLOCKED reports in v1).

**Proven strength — continuity works.** The recurring pain across every session is "I lost the agent I was working with." This system exists to survive that, and it does: full project state (runs, tasks, mail, reports) was rebuilt from disk + the Hermes session DB during this takeover with nothing lost. That is the system's most important property and it is solid.

## The #1 issue: no working agent-wake path (likely-broken live loop)

The unverified "live agent-to-agent comms" item is not merely untested — reading the code, it will probably **stall**, and the root cause is a missing wake mechanism, not the mailbox (mechanics work fine):

1. A lead's Claude pane runs `mail inbox` once at startup, sees nothing, and idles at its prompt. Nothing re-triggers it (no daemon, no poll loop).
2. The intended cross-pane wake is `bin/ask`, whose tmux injection finds the target pane by `#{pane_title}`. But Claude overwrites pane titles to "✳ Claude Code" (confirmed in the live pane dump). The launcher moved to stable pane-**border** `@role` labels — `ask` was never updated to match. So the wake silently no-ops.
3. Net: orchestrator → lead mail lands in JSONL, but the lead never learns to read it. The loop hangs.

**Prediction to verify:** when the live loop is tested, expect it to stall on agent-wake. Fix `ask` to target panes via the `@role` option (`tmux list-panes -F '#{pane_id} #{@role}'`) instead of `pane_title`. Note the canonical path is agents running `mail`/`report` directly in their own panes (no `ask` involved); the specific gap is **cross-pane notification** — telling an idle pane that new mail arrived.

## Correctness under concurrency (the stated goal is "many agents at once")

- **ID collision (certain bug):** `make_id()` does read-existing → compute-next-number → write, with no lock. Two panes creating a task/message at the same time independently compute the same next id and collide. This is guaranteed under real parallelism, independent of write atomicity.
- **Append interleave (lower risk):** `append_event()` is unlocked; oversized report lines (>4KB) could interleave under simultaneous writes. Most events flush in one write, so this is secondary.
- **Fix (one change):** wrap the read-modify-write in `make_id` and the `append_event` write in an `fcntl.flock` on a lock file. Lead with the collision; the corruption is a bonus.

## Usability / footguns

- **No unread cursor in `mail inbox`:** every read returns the agent's entire history. Live agents re-process old mail on every poll. Add `--unread`/`--since` or a read/ack event. (Pairs with the wake fix to make the loop actually usable.)
- **No participant/role validation:** a typo in `--to`/`--owner`/inbox agent silently creates orphan mail or an empty inbox — a silent failure for agents typing commands. Validate against run participants and warn (don't hard-fail).
- **No routing enforcement:** role prompts declare allowed routes (orchestrator ↔ leads only), but the CLI lets anyone mail anyone. Advisory only. Acceptable for v1; flag it.
- **`report done` trusts `--task`:** it auto-completes whatever task id is passed with no existence check. Minor.

## Architecture vs. the end-goal (multiple projects in parallel)

- **Single global current run:** `state/current_run.json` is one file, so there is exactly one "current run" per `.jumpcode` home. The stated vision is multiple projects running in parallel. This is **the** architectural decision that blocks the vision. Options: (a) one `.jumpcode` per workspace selected via `JUMPCODE_HOME`, or (b) scope current-run + state by workspace id. Decide before scaling past one project.

## Open user-asks (not "deferred" — actively requested)

- **Reliable output rating/eval:** asked in two separate sessions, with a pointer to existing tools (Claude Code/Codex integrations). Currently absent. Reports carry `checks_run` so eval can layer on, but the actual rating solution is unresolved and needs research.
- **Liveness:** intentionally deferred in v1; revisit alongside the wake fix (a liveness/poll loop is a natural place to also surface new mail).

## Test gaps

Coverage is happy-path only. Missing: concurrent id generation, unread/inbox-cursor behavior, `ask` wake targeting.

## Minor

- `HANDOFF.md` primitives block has a corrupted token `任务/task` (stray CJK) — relevant since that is the continuity doc.
- Stale `bb-ambassador` tmux session lingering from an earlier iteration; safe to kill.

## Proposed order of work

1. **Fix the wake path** (`ask` → `@role` targeting) + add `mail inbox --unread`, then run the live orchestrator→lead→report→read loop end-to-end. Closes the open thread and makes the jumpcode actually usable by live agents.
2. **Add `flock`** around `make_id`/`append_event` (concurrency correctness) + a concurrency test.
3. **Decide multi-project model** (per-workspace home vs. workspace-scoped runs) — unblocks the parallel-projects vision.
4. **Research + spike output eval/rating** (the twice-asked open request).
5. **Cleanup:** participant validation + warnings, fix `HANDOFF.md` token, kill stale tmux session.
