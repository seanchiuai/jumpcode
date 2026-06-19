# Fleet dashboard — live workspace status TUI

**Date:** 2026-06-19
**Status:** Design approved

## Problem

There is no single view of all jumpcode workspaces. `health` shows live pane state but
is scoped to one tmux session at a time. Sean wants a dashboard that shows every
workspace and its status — past, active, error (and idle) — at a glance.

## Decisions

- **Form:** live TUI (curses, alt-screen), built on python stdlib only — no new deps.
- **Refresh:** auto every 30s, plus manual `r` to refresh now, `q` to quit.
- **Idle threshold:** 10 minutes of quiet (both signals required — see classifier).
- **Statuses:** `active` / `idle` / `past` / `error`.

## Status taxonomy

A workspace is any `state/sessions/*.json` manifest (the universe of launched
workspaces). Each manifest carries a `session` field mapping it to a tmux session.

| Status | Meaning | Detection |
|--------|---------|-----------|
| 🟢 `active` | alive + doing work / recently active | live tmux session AND (any pane `working`/`waiting` OR last dispatch < 10 min) |
| 🟡 `idle` | alive but quiet a sustained window | live session AND all alive panes `idle` AND no dispatch in last 10 min |
| ⚪ `past` | recorded but not running now | no live tmux session for the manifest's `session` |
| 🔴 `error` | something wrong while alive | live session AND (stale silent open loop OR config check failed) |

**Classifier order (first match wins):** `error` → `active` → `idle` → `past`.

The 10-min-AND-all-idle requirement for `idle` avoids false positives: a momentary
between-turns "idle" won't trip it because the dispatch log will still be fresh.

`error` signals (per Sean): a **silent open loop** (a role was woken but never replied
and the request has stayed open past a staleness threshold) OR a **config problem**
(`workspace.json` missing/unparseable, role-overlay dir absent, or a role's `cwd` no
longer exists on disk). Dead panes alone are not flagged as error in v1.

## Invocation

New `fleet` subcommand in the `jumpcode` python CLI + a thin `./.jumpcode/bin/fleet`
wrapper (matching every other bin). One code path, three modes:

- `fleet` → live TUI.
- `fleet --json` → one-shot machine-readable dump (tests + scripting; no curses).
- `fleet --once` → one-shot plain-text paint, no loop (cheap glance / non-tty safe).

## Data flow (per refresh)

1. **Enumerate** every `state/sessions/*.json` manifest.
2. **Liveness** — `tmux ls` once; for each manifest's `session`, `_tmux_session_alive()`
   then `list-panes` for the live ones.
3. **Activity** — last dispatch timestamp per session from `dispatches.jsonl`
   (aggregate `last_seen_by_role` to a per-workspace max).
4. **Config check** — `workspace.json` resolves + parses, role-overlay dir exists, each
   role `cwd` exists.
5. **Classify** via the pure classifier above.

## Layout

Sorted active → idle → error → past, then by recency:

```
JUMPCODE FLEET                          8 workspaces · 30s · r refresh · q quit
●  webapp       active   6/6 panes   working:2 idle:4   last 2m    ⊙ visible
●  obs          active   5/5 panes   working:1 idle:4   last 14m   ⊙ headless
⚠  ambassador   error    silent loop: backend-lead woken 47m ago   last 47m
◐  bugsmash     idle     5/5 panes   idle:5             last 1h12m
○  seo          past     —                              last 2d
```

Color via curses color pairs (green/yellow/red/dim). Footer carries the `health`-style
"⚠ headless" warning for alive-but-no-window sessions.

## Refactor

`cmd_health`'s pane-scanning block (~lines 953–992) factors into a reusable
`scan_session(session) -> agents[]` so `health` (one session) and `fleet` (all
sessions) share one classifier — no logic drift. Behavior-preserving for `health`.

## Testing

`fleet --json` is the test seam. Unit tests in `.jumpcode/tests/` feed synthetic
manifests + fake tmux/dispatch fixtures and assert the classifier returns the right
status for each of the 4 states, plus edges: alive-no-panes, manifest with missing
`cwd`, stale-vs-fresh dispatch boundary. The classifier is pure (data in, status
string out) so it tests without tmux. The curses render layer stays thin and untested.
