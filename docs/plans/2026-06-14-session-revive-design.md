# Session Revive / Restart — Design

**Date:** 2026-06-14
**Status:** implemented

## Problem

Reopening a closed workspace always started **fresh** (ADR 0004): new Claude sessions, no
prior agent context. Sean wants the option to reopen **resumed** — bring each role back on
its own prior session — and wants session ids saved reliably so resume is dependable. Framed
generally: a primitive to *restart or revive* workspace sessions, reusable for various
purposes (reopen a closed workspace, relogin/crash recovery, reviving one team).

## What already existed

- `start-webapp` pins a fresh `--session-id` per claude role each launch and records all ids
  to `state/sessions/<ws>.json`.
- `agent_cmd` already had a resume path (`--resume $sid || --session-id $sid`), used only by
  the reconcile/respawn pass for stragglers.
- Audit of all 6 live manifests: every recorded id has a live transcript (0 missing).
  `claude --resume` preserves the id, so manifests stay valid across resumes.

The only gap was that nothing *resumed* on a normal reopen.

## Design

A general **`revive`** verb plus a gated resume mode on the launcher.

- **`JUMPCODE_RESUME=1` on `start-webapp`** — read the prior manifest into a role→sid map;
  each claude role reuses its recorded id and launches on the resume path. Role discovery
  stays the source of truth for *who*; the manifest only supplies the id for *whom*. No
  recorded id → fresh fallback (safe: the resume path itself falls back). Bare `start-webapp`
  is unchanged (ADR 0004 default intact). The post-launch recording rewrites the manifest
  (`recorded_by: start-webapp-resume`), closing the relogin gap.
- **`revive` bin → `jumpcode revive` subcommand**:
  - `revive <ws>` — reopen resumed (sets `JUMPCODE_RESUME=1`, execs `start-webapp`).
  - `revive <ws> --fresh` — clean restart.
  - `revive <ws> --force` — kill+relaunch even if running.
  - `revive list` — recorded sessions per workspace + live/closed + transcript presence.
  - Refuses to clobber a running workspace without `--force`.

## Why this shape

Standalone verb matches the bin-per-verb topology (dispatch/health/peek/status) and keeps
ADR 0004 unambiguous — `start-webapp` = fresh, `revive` = resume. Reusing `start-webapp`'s
grid/layout/reconcile/record machinery via an env flag avoids duplicating hundreds of lines.

## Verification

- `python3 -m unittest discover -s .jumpcode/tests` → 59 OK.
- `py_compile` / `bash -n` clean on all three touched files.
- `revive list` lists all 6 workspaces correctly; guards refuse live-workspace resume (exit 2)
  and missing manifest (exit 1).
- Resume sid-selection logic verified under bash 5: 8 ids loaded, each role → its own id,
  unknown role → fresh. (`declare -A` matches the launcher's existing bash-4+ baseline.)

## Follow-ups (not built — YAGNI)

- Single-role revive (`revive <ws> <role>`) for reviving/restarting one pane. Deferred until a
  concrete need; the reconcile path already respawns single panes internally.
