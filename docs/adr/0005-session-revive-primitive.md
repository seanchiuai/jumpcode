# Session Revive Primitive

> **SUPERSEDED (2026-07-17) by [ADR 0008](0008-native-claude-code-orchestration.md).** The
> custom `revive` verb and per-workspace session manifest are retired in favor of native
> `claude --resume`. The intent — reopen a session with its prior reasoning intact — survives;
> only the custom implementation is gone. Kept for history.


A workspace can be reopened **resumed** — each claude role reconnecting to the session it
last ran under — via a dedicated `revive` verb, not just launched fresh. This refines (does
not overturn) ADR 0004.

## Why

ADR 0004 made "always launch fresh" the default and dropped resume to keep the launcher
simple and lean on durable sources (the external tracker, the dispatch log). That default stands. But in
practice some reopens want the agents' *own* prior context back — a team mid-thought after a
window close or relogin, where reconstructing from the tracker loses the in-flight reasoning. We
already record every launched session id to a per-workspace manifest
(`state/sessions/<ws>.json`), and `claude --resume` preserves the id (verified: ids recorded
weeks ago are still the live, appended-to transcripts), so the brittleness ADR 0004 feared
hasn't materialised.

## Decision

- **Bare `start-webapp` stays fresh.** ADR 0004's default is untouched.
- **`JUMPCODE_RESUME=1`** is an opt-in mode on `start-webapp`: each claude role reuses its
  recorded session id and launches on the existing `--resume $sid || --session-id $sid`
  path. Role discovery remains the source of truth for *who* runs; the manifest only supplies
  the id for *whom*. A role with no recorded id (added since last launch, codex, first ever
  launch) falls back to fresh.
- **`revive` is the user-facing verb.** `revive <ws>` resumes; `revive <ws> --fresh` is a
  clean restart; `revive list` shows recorded sessions and liveness. It refuses to clobber a
  running workspace without `--force`.

## Consequence

The launch manifest earns a second job: not just a forensic record but the input to resume.
Because the resume launch re-records the manifest, **relogin recovery is now just
`revive <ws>`** — closing the gap where manual `claude --resume` left the manifest unrefreshed.
The dispatch log (ADR 0002) remains the continuity source for a *fresh* start; revive is the
path when restoring agent memory is worth more than a clean slate.
