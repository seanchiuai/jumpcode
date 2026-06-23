# Jumpcode Instructions

The local operator manual for Sean and any visible Claude Code pane (the
orchestrator and team leads). Canonical terms live in [`CONTEXT.md`](CONTEXT.md); the
reasoning lives in [`docs/adr/`](docs/adr/); the shared interaction rules for leads live
in [`roles/_PROTOCOL.md`](roles/_PROTOCOL.md).

## When to use Jumpcode

Use it whenever coordination needs to be **delivered live and remembered**:

- multi-agent work across visible panes (orchestrator / leads / their subagents)
- work likely to span context compaction or a fresh relaunch
- any time an agent needs to be woken to act, or a message needs to survive in the log

For tiny one-shot answers, do not send dispatches.

## Where work lives: GitHub issues, not here

A **project** is a GitHub repo/milestone; a **task** is a GitHub issue (ADR 0006). Read and
write them with the `gh` CLI. There is **no local task/project/run registry** — the
jumpcode owns only delivery (wake) and the dispatch log. "Done" is informal: update the
GitHub issue and report via dispatch.

## Source of truth

Machine-readable dispatch record:

```text
.jumpcode/state/dispatches.jsonl
```

Human-readable feed:

```text
.jumpcode/shared/conversation.log
```

## Command contract

Run commands from the workspace root:

```bash
cd /Users/seanchiu/Desktop/workspace-macbook
```

The single verb is `dispatch`:

```bash
# send a dispatch (live wake + durable log)
./.jumpcode/bin/dispatch send --from orchestrator --to backend-lead \
  --task #42 --subject "Start work" "Please implement X."

# report (close the loop): pair the report to its request with --reply-to
./.jumpcode/bin/dispatch send --from backend-lead --to orchestrator \
  --kind report-done --task #42 --reply-to <REQUEST-DISPATCH-ID> "Done; …"

# inspect
./.jumpcode/bin/dispatch inbox backend-lead
./.jumpcode/bin/dispatch show <dispatch-id>
./.jumpcode/bin/dispatch log 40

# wrappers
./.jumpcode/bin/status        # open loops: requests with no matching report (+ pane state)
./.jumpcode/bin/health        # per-role: alive · working/waiting/idle · runtime · subagents
./.jumpcode/bin/fleet         # live dashboard of ALL workspaces + status (active/idle/past/error); --json / --once
./.jumpcode/bin/peek <role> [n] # read-only view of a role's pane (never wakes it)
./.jumpcode/bin/convo 80      # tail the conversation feed
./.jumpcode/bin/start-webapp  # launch the webapp grid (fresh)
```

## Session scoping (concurrent workspaces)

A dispatch identity is **(session, role)**, not a bare role name: concurrent workspaces
(e.g. `macbook-ambassador`, `macbook-heatmap`, `macbook-seo`) all have a `backend-lead`,
and they are *different agents*. Every `dispatch send` tags its event with the sender's
tmux session (from `$JUMPCODE_TMUX_SESSION`, set in every pane; an external sender
sets it or passes `--session <name>`). `inbox`, `log`, `status` (open-loop pairing)
and `health` (subagents / last-seen) read **only the caller's session's events**. The
wake likewise resolves panes inside that one session, across all its windows.

`--all-sessions` on the read commands gives the unscoped global view; it is also the
only view that still shows **untagged legacy events** (dispatches sent before scoping
existed). A send with no resolvable session logs untagged with a warning and is not
delivered.

## Reporting discipline

When a unit of work finishes or stalls, send a dispatch back to whoever assigned it
**and** update the GitHub issue:

```bash
# done
./.jumpcode/bin/dispatch send --from backend-lead --to orchestrator \
  --kind report-done --task #42 \
  "Summary; what changed; checks run; open concerns; recommended next step."

# blocked
./.jumpcode/bin/dispatch send --from backend-lead --to orchestrator \
  --kind report-blocked --task #42 \
  "Blocker; why; what you tried; what you need from the orchestrator."
```

A Claude pane cannot poll its own inbox — it acts when woken. After a wake, read the
full message with `dispatch inbox <role>` / `dispatch show <id>`.

## Topology

Hub-and-spoke (ADR 0001): Sean (the Human) may type into any pane; leads report only to
the orchestrator and request a **relay** to reach another lead. The Human (Sean) never
addresses subagents directly.

## Continuity

Bare `start-webapp` launches panes **fresh** (ADR 0004) — reconstruct context from GitHub
issues and the dispatch log (`./.jumpcode/bin/dispatch log 40`).

To reopen a workspace **resumed** instead (each role reconnecting to its prior session),
use `revive` (ADR 0005):

```bash
./.jumpcode/bin/revive <ws>          # reopen RESUMED from state/sessions/<ws>.json
./.jumpcode/bin/revive <ws> --fresh  # clean restart (new sessions)
./.jumpcode/bin/revive <ws> --force  # kill+relaunch even if it's already running
./.jumpcode/bin/revive list          # recorded sessions per workspace + live/closed
```

`revive` refuses to clobber a running workspace without `--force`. Session ids are recorded
to `state/sessions/<ws>.json` on every launch; the resume launch re-records them, so relogin
recovery is just `revive <ws>`.

## Testing after changes

```bash
python3 -m py_compile .jumpcode/bin/jumpcode
bash -n .jumpcode/bin/dispatch .jumpcode/bin/convo .jumpcode/bin/status .jumpcode/bin/start-webapp
python3 .jumpcode/tests/test_jumpcode.py
```
