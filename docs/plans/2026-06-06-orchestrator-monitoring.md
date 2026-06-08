# Orchestrator-as-Monitor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give the orchestrator the power to monitor and recover its leads by adding a single read-only `peek` command plus a "Monitoring & recovery" mandate in its charter.

**Architecture:** One new CLI verb `peek <role> [lines]` that resolves a role→pane (reusing `resolve_pane`/`resolve_session`) and prints `tmux capture-pane`, exposed via a `bin/peek` wrapper. No Stop hook, no watcher daemon, no new state. The orchestrator's charter tells it to watch its leads with `peek` + `dispatch log`, re-wake to retry transient errors, and escalate to Sean otherwise. Design doc: `docs/plans/2026-06-06-orchestrator-monitoring-design.md`.

**Tech Stack:** Python 3 (stdlib), bash, tmux. Tests via unittest. Local-scoped git in `.jumpcode/`.

**Pre-flight:** `.jumpcode/bin/jumpcode` currently has an unused `import re` (added intentionally by Sean) — leave it; `peek` does not need it. Run all commands from `/Users/seanchiu/Desktop/workspace-macbook`.

---

## Task 1: `peek` command — graceful when no session (TDD)

**Files:**
- Modify: `.jumpcode/tests/test_jumpcode.py` (make `run_cmd` hermetic from tmux; add peek test)
- Modify: `.jumpcode/bin/jumpcode` (add `cmd_peek`, parser entry, dispatch in `main`)

**Step 1: Make `run_cmd` ignore the ambient tmux, then write the failing test.**

In `.jumpcode/tests/test_jumpcode.py`, the helper already does `env.pop("JUMPCODE_TMUX_SESSION", None)`. Add right after it:

```python
    env.pop("TMUX", None)
```

Then add this test to `DispatchCliTests`:

```python
    def test_peek_without_session_is_graceful(self):
        r = run_cmd(self.tmp_path, "peek", "backend-lead", check=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no jumpcode tmux session", r.stderr)
        self.assertEqual(r.stdout, "")
```

**Step 2: Run test to verify it fails**

Run: `python3 .jumpcode/tests/test_jumpcode.py -k test_peek_without_session_is_graceful -v`
Expected: FAIL — argparse errors with `invalid choice: 'peek'` (exit 2, not 1).

**Step 3: Implement `cmd_peek` + wire it up.**

Add this function to `.jumpcode/bin/jumpcode` just above `def build_parser()`:

```python
def cmd_peek(args: argparse.Namespace, home: Path) -> int:
    """Read-only view of a role's pane, so the orchestrator can see what a lead is doing.

    Never sends keys. To act on what it sees, the orchestrator uses `dispatch send`.
    """
    session = resolve_session()
    if not session:
        print(
            "peek: no jumpcode tmux session (is the workspace running? "
            "set JUMPCODE_TMUX_SESSION)",
            file=sys.stderr,
        )
        return 1
    try:
        panes = subprocess.run(
            ["tmux", "list-panes", "-t", session, "-F", "#{pane_id}\t#{@jumpcode_role}"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"peek: tmux session '{session}' not found", file=sys.stderr)
        return 1
    pane = resolve_pane(panes, args.role)
    if not pane:
        print(f"peek: no pane for role '{args.role}' in session '{session}'", file=sys.stderr)
        return 1
    cap = subprocess.run(
        ["tmux", "capture-pane", "-p", "-S", f"-{args.lines}", "-t", pane],
        capture_output=True, text=True, check=False,
    ).stdout
    print(cap, end="")
    return 0
```

In `build_parser()`, after the `dispatch` parser block (just before `return parser`), add:

```python
    pk = sub.add_parser("peek", help="read a role's pane, read-only")
    pk.add_argument("role")
    pk.add_argument("lines", nargs="?", type=int, default=50)
```

In `main()`, after the `if args.cmd == "dispatch":` block, add:

```python
    if args.cmd == "peek":
        return cmd_peek(args, home)
```

**Step 4: Run test to verify it passes**

Run: `python3 .jumpcode/tests/test_jumpcode.py -v`
Expected: PASS (all dispatch tests + the new peek test).

**Step 5: Commit**

```bash
cd /Users/seanchiu/Desktop/workspace-macbook/.jumpcode
git add bin/jumpcode tests/test_jumpcode.py
git commit -m "feat(peek): read-only pane view for orchestrator monitoring (TDD)"
```

---

## Task 2: `bin/peek` wrapper

**Files:**
- Create: `.jumpcode/bin/peek`

**Step 1: Create the wrapper**

```bash
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$DIR/jumpcode" peek "$@"
```

**Step 2: Make executable + syntax check**

```bash
cd /Users/seanchiu/Desktop/workspace-macbook
chmod +x .jumpcode/bin/peek
bash -n .jumpcode/bin/peek && echo OK
```
Expected: `OK`.

**Step 3: Smoke (graceful path, no tmux)**

```bash
env -u TMUX -u JUMPCODE_TMUX_SESSION ./.jumpcode/bin/peek backend-lead; echo "exit=$?"
```
Expected: stderr `peek: no jumpcode tmux session ...`, `exit=1`.

**Step 4: Commit**

```bash
cd /Users/seanchiu/Desktop/workspace-macbook/.jumpcode
git add bin/peek
git commit -m "feat(peek): bin/peek wrapper"
```

---

## Task 3: Orchestrator charter — Monitoring & recovery

**Files:**
- Modify: `.jumpcode/roles/orchestrator.md` (add a section)
- Modify: `.jumpcode/roles/_PROTOCOL.md` (one-line pointer)

**Step 1:** In `.jumpcode/roles/orchestrator.md`, insert a new section between section 3 (Domain conventions) and section 4 (Interaction rules):

```markdown
## 3b. Monitoring & recovery

You own watching your leads — do not assume a dispatched task is progressing or done.

- **See a lead:** `./.jumpcode/bin/peek <role>` prints that lead's pane (read-only).
  Reading it: advancing spinner/timer = working; static empty `❯` prompt = idle/finished
  its turn; an error banner = errored; a shell prompt (no `claude`) = crashed.
- **Track open loops:** `./.jumpcode/bin/dispatch log` shows what you asked vs. what
  came back. A `request` you sent with no matching `report-done`/`report-blocked` from
  that lead is still open.
- **When to check:** after you dispatch work, when a lead reports back, or when Sean asks.
  You are a sitting agent — you only check when awake; that is expected.
- **Conservative recovery:** if a lead looks stalled or shows a transient error
  (rate-limit, overloaded, a flaky tool call), **re-wake it to retry**:
  `./.jumpcode/bin/dispatch send --from orchestrator --to <role> --task <T>
  "status? continue/retry <T>"`. If it still fails after ~2 nudges, or the problem is
  non-transient (auth/quota exhausted, crashed pane, a bug in the jumpcode CLI itself),
  **escalate to Sean** with the diagnosis you read from the pane. Do **not** auto-answer
  permission dialogs, respawn panes, or edit the jumpcode tooling — that is Hermes's job.
```

**Step 2:** In `.jumpcode/roles/_PROTOCOL.md`, under the "Reporting" area (or near the topology section), add one line so leads know they may be peeked/re-pinged:

```markdown
The orchestrator may `peek` your pane (read-only) and re-ping you if a task goes quiet —
so always finish by reporting (`report-done`/`report-blocked`); silence reads as stalled.
```

**Step 3: Verify** the orchestrator charter now names `peek`, conservative recovery, and the escalation boundary.

```bash
grep -n "peek\|Conservative recovery\|escalate to Sean" .jumpcode/roles/orchestrator.md
```
Expected: matches present.

**Step 4: Commit**

```bash
cd /Users/seanchiu/Desktop/workspace-macbook/.jumpcode
git add roles/orchestrator.md roles/_PROTOCOL.md
git commit -m "docs(roles): orchestrator monitoring & conservative recovery mandate"
```

---

## Task 4: Allow `peek` in workspace permissions

**Files:**
- Modify: `/Users/seanchiu/Desktop/workspace-macbook/.claude/settings.local.json`

**Why:** So panes can run `peek` without a permission prompt. (This file is outside the `.jumpcode` git scope — no commit step.)

**Step 1:** Add `"Bash(./.jumpcode/bin/peek *)"` to the `permissions.allow` array.

**Step 2: Verify** it is valid JSON:

```bash
python3 -c "import json; json.load(open('/Users/seanchiu/Desktop/workspace-macbook/.claude/settings.local.json')); print('valid')"
```
Expected: `valid`.

---

## Task 5: Live verification

**Why:** Prove `peek` reads a real pane and the orchestrator can use it.

**Step 1:** Ensure the workspace is running (relaunch if needed): `./.jumpcode/bin/start-webapp` (or reuse the live `macbook-webapp` session).

**Step 2:** From the shell (external sender):

```bash
JUMPCODE_TMUX_SESSION=macbook-webapp ./.jumpcode/bin/peek backend-lead 30
```
Expected: prints the backend-lead pane's recent content (charter text / prompt / spinner).

**Step 3:** Negative check:

```bash
JUMPCODE_TMUX_SESSION=macbook-webapp ./.jumpcode/bin/peek nope; echo "exit=$?"
```
Expected: stderr `peek: no pane for role 'nope' ...`, `exit=1`.

**Step 4 (optional, full loop):** Dispatch the orchestrator to exercise it:
`dispatch send --from hermes --to orchestrator "peek backend-lead and tell me its current state."` Confirm the orchestrator runs `peek` and reports the state.

---

## Out of scope (deferred, per design)

- Stop hook to *prevent* silent-finish.
- Computed `dispatch status` (open-loops + working/idle/dead classification).
- launchd watcher + orchestrator-down notification to Sean.
