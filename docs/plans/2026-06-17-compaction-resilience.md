# Compaction Resilience Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make a running jumpcode team survive context compaction — give the orchestrator visibility into every lead's window, auto-rehydrate any pane's identity/protocol after compaction, and let the orchestrator drive a lead's compaction.

**Architecture:** Three independent pieces. (1) Extend the global `UserPromptSubmit` reminder hook so the orchestrator pane also reports each lead's window occupancy. (2) A new global `SessionStart(matcher=compact)` hook auto-injects a role-aware rehydration card into any jumpcode pane after compaction; leads additionally announce "compaction complete" back to the orchestrator via dispatch. (3) A new `recompact` verb in the jumpcode CLI types `/compact` into a lead's pane. All hooks are user-global (`~/.claude/`) and hard-gated to jumpcode panes (`@jumpcode_role` option + matching `state/sessions/<session>.json`).

**Tech Stack:** Python 3 (stdlib only), tmux, bash wrappers, `unittest` (`python3 -m unittest discover -s .jumpcode/tests`).

**Design doc:** `.jumpcode/docs/plans/2026-06-17-compaction-resilience-design.md`

**House rule:** commit the `.jumpcode` repo only — and the global `~/.claude` files are outside any repo (do not try to `git add` them). Do NOT push. Commit `.jumpcode` changes locally at each step; pushing is public and only on Sean's explicit ask.

---

## Reference facts (verified 2026-06-17)

- Existing reminder hook: `~/.claude/hooks/orchestrator-compact-reminder.py`. Metric =
  `input_tokens + cache_creation_input_tokens + cache_read_input_tokens` from the last
  usage-bearing assistant turn (`context_tokens()`). Threshold `JUMPCODE_COMPACT_THRESHOLD`
  (default 200000). Scoped via `@jumpcode_role == "orchestrator"`.
- State file: `.jumpcode/state/sessions/<workspace>.json` with top-level `session`,
  `workspace_root`, and `roles: [{role, pane, runtime, session_id}]`.
- All roles in a workspace share ONE Claude project dir (same cwd); a lead's transcript is
  `dirname(<orchestrator transcript_path>)/<lead session_id>.jsonl`.
- CLI: `.jumpcode/bin/jumpcode` (single python script). Subcommands are `sub.add_parser(...)`
  with `cmd_<name>(args, home)` handlers; `resolve_pane(panes_text, role)` (line ~195) and
  `wake_pane(session, role, text)` (line ~220) already do role→pane via
  `tmux list-panes -s -t <session> -F '#{pane_id}\t#{@jumpcode_role}'`.
- Test patterns: `tests/test_jumpcode.py` runs `bin/jumpcode` as a subprocess with a temp
  `JUMPCODE_HOME`; `tests/test_wake.py` stubs `tmux` (read it before Task 5 to copy the stub).
- Central charter: `.jumpcode/roles/🧭 orchestrator.md`. Protocol: `.jumpcode/roles/_PROTOCOL.md`.

---

## Task 1: Pure function — scan the team's context windows (Component 1 core)

**Files:**
- Modify: `~/.claude/hooks/orchestrator-compact-reminder.py`
- Test: `.jumpcode/tests/test_compaction_hooks.py` (Create)

**Step 1: Write the failing test**

Create `.jumpcode/tests/test_compaction_hooks.py`:

```python
import importlib.util
import json
import os
import unittest
from pathlib import Path

HOOKS = Path.home() / ".claude" / "hooks"
REMINDER = HOOKS / "orchestrator-compact-reminder.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(REMINDER.exists(), "global reminder hook not installed")
class ScanTeamContextTests(unittest.TestCase):
    def setUp(self):
        self.mod = _load(REMINDER, "reminder_hook")

    def _transcript(self, tmp, name, tokens):
        p = Path(tmp) / f"{name}.jsonl"
        p.write_text(json.dumps({
            "message": {"usage": {
                "input_tokens": tokens, "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0}}}) + "\n", encoding="utf-8")
        return p

    def test_reports_only_leads_over_threshold(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self._transcript(tmp, "sid-backend", 210000)
            self._transcript(tmp, "sid-qa", 5000)
            state = {"roles": [
                {"role": "orchestrator", "session_id": "sid-orch"},
                {"role": "backend-lead", "session_id": "sid-backend"},
                {"role": "qa-lead", "session_id": "sid-qa"},
            ]}
            over = self.mod.scan_team_context(state, tmp, threshold=200000)
            self.assertEqual(over, [("backend-lead", 210000)])

    def test_missing_transcript_is_skipped(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            state = {"roles": [{"role": "backend-lead", "session_id": "absent"}]}
            self.assertEqual(self.mod.scan_team_context(state, tmp, 200000), [])
```

**Step 2: Run it, verify it fails**

Run: `python3 -m unittest tests.test_compaction_hooks -v` (from `.jumpcode/`)
Expected: FAIL — `AttributeError: module 'reminder_hook' has no attribute 'scan_team_context'`.

**Step 3: Implement `scan_team_context` in the reminder hook**

Add to `~/.claude/hooks/orchestrator-compact-reminder.py` (after `context_tokens`):

```python
LEAD_ROLES_EXCLUDED = {"orchestrator"}


def scan_team_context(state, transcript_dir, threshold):
    """[(role, tokens), ...] for non-orchestrator roles whose window is >= threshold.

    transcript_dir is the dir holding every role's <session_id>.jsonl (all roles share the
    orchestrator's project dir). Missing/unreadable transcripts are skipped.
    """
    over = []
    for entry in state.get("roles", []):
        role = entry.get("role", "")
        if role in LEAD_ROLES_EXCLUDED:
            continue
        sid = entry.get("session_id", "")
        if not sid:
            continue
        path = os.path.join(transcript_dir, f"{sid}.jsonl")
        if not os.path.exists(path):
            continue
        toks = context_tokens(path)
        if toks >= threshold:
            over.append((role, toks))
    return over
```

**Step 4: Run test, verify pass**

Run: `python3 -m unittest tests.test_compaction_hooks -v`
Expected: PASS (2 tests).

**Step 5: Commit**

```bash
cd /Users/seanchiu/Desktop/workspace-macbook/.jumpcode
git add tests/test_compaction_hooks.py
git commit -m "test: team-wide context scan for the compaction reminder hook"
```
(The hook script itself is in `~/.claude` and outside the repo — not added.)

---

## Task 2: Wire the team scan into the reminder hook's output (Component 1 glue)

**Files:**
- Modify: `~/.claude/hooks/orchestrator-compact-reminder.py` (`main()`)

**Step 1: Load the state file + locate the transcript dir in `main()`**

In `main()`, after `transcript = payload.get("transcript_path")` and after computing the
orchestrator's own `ctx`, add the team scan. Resolve the workspace state file by matching the
current tmux session name:

```python
def _state_for_session(session):
    """The .jumpcode state/sessions/<ws>.json whose `session` == this tmux session, or None."""
    home = os.environ.get("JUMPCODE_HOME")
    if not home:
        return None
    sdir = os.path.join(home, "state", "sessions")
    try:
        names = os.listdir(sdir)
    except OSError:
        return None
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(sdir, name), encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("session") == session:
            return data
    return None
```

Then in `main()` (after `session = ...` is resolved, before building `agent_msg`):

```python
    state = _state_for_session(session)
    team_over = []
    if state and transcript:
        team_over = scan_team_context(state, os.path.dirname(transcript), THRESHOLD)
```

Gate (b): if both `ctx < THRESHOLD` AND `not team_over`, return 0 (nothing to report). Replace
the existing early `if ctx < THRESHOLD: return 0` with:

```python
    if ctx < THRESHOLD and not team_over:
        return 0
```

**Step 2: Extend the messages to include leads**

Build a leads clause and fold it into both `agent_msg` and `systemMessage`:

```python
    if team_over:
        leads = ", ".join(f"{r} ~{round(t/1000)}k" for r, t in team_over)
        team_clause = (
            f" TEAM: leads over the {thr_k}k threshold — {leads}. For each, wait until it is "
            f"idle (dispatch status / health), then `recompact --role <lead>` so it compacts; "
            f"it will auto-rehydrate and send you a 'compaction complete' notice."
        )
    else:
        team_clause = ""
```

Append `team_clause` to `agent_msg`. When the orchestrator itself is under threshold but leads
are over, lead with the team line in `systemMessage`:

```python
    if ctx >= THRESHOLD:
        sys_msg = f"⚠ {session} orchestrator context ~{ctx_k}k (>{thr_k}k) — recommend /compact"
    else:
        sys_msg = f"⚠ {session} leads over context threshold — see dispatch"
    if team_over:
        sys_msg += " · over: " + ", ".join(f"{r} ~{round(t/1000)}k" for r, t in team_over)
```

Use `sys_msg` for the `systemMessage` field. Keep `suppressOutput: True`.

**Step 3: Manual smoke test (no tmux fixture needed)**

Run from `.jumpcode/`:
```bash
JUMPCODE_HOME="$PWD" python3 - <<'PY'
import importlib.util, os
from pathlib import Path
m = importlib.util.spec_from_file_location("h", Path.home()/".claude/hooks/orchestrator-compact-reminder.py")
mod = importlib.util.module_from_spec(m); m.loader.exec_module(mod)
print("scan_team_context" in dir(mod), "_state_for_session" in dir(mod))
PY
```
Expected: `True True`.

**Step 4: Regression — existing reminder behaviour unchanged**

Confirm an orchestrator over threshold with no leads still returns the original recommendation
(reads `additionalContext` contains "STRONGLY RECOMMENDED"). Verify by eye against the diff.

**Step 5: Commit**

```bash
cd /Users/seanchiu/Desktop/workspace-macbook/.jumpcode
git commit --allow-empty -m "feat: orchestrator reminder reports leads over context threshold

Hook script lives in ~/.claude (outside repo); this records the design+test change."
```

---

## Task 3: Rehydration card pure functions (Component 2 core)

**Files:**
- Create: `~/.claude/hooks/jumpcode-rehydrate-after-compact.py`
- Test: `.jumpcode/tests/test_compaction_hooks.py` (extend)

**Step 1: Write the failing test**

Append to `test_compaction_hooks.py`:

```python
REHYDRATE = HOOKS / "jumpcode-rehydrate-after-compact.py"


@unittest.skipUnless(REHYDRATE.exists(), "rehydrate hook not installed")
class RehydrateCardTests(unittest.TestCase):
    def setUp(self):
        self.mod = _load(REHYDRATE, "rehydrate_hook")

    def test_lead_card_tells_it_to_report_back_and_announce(self):
        card = self.mod.rehydrate_card("backend-lead", "bugsmash", "/root", "/root/.jumpcode")
        self.assertIn("backend-lead", card)
        self.assertIn("report-done", card)
        self.assertIn("compaction complete", card)        # announces it is back
        self.assertIn("_PROTOCOL.md", card)

    def test_orchestrator_card_has_no_self_notify(self):
        card = self.mod.rehydrate_card("orchestrator", "bugsmash", "/root", "/root/.jumpcode")
        self.assertIn("dispatch status", card)
        self.assertNotIn("compaction complete", card)     # never notifies itself
```

**Step 2: Run, verify fail**

Run: `python3 -m unittest tests.test_compaction_hooks -v`
Expected: FAIL — file/module not found / no `rehydrate_card`.

**Step 3: Create the hook with the pure renderer**

Create `~/.claude/hooks/jumpcode-rehydrate-after-compact.py` (mark executable, `chmod +x`):

```python
#!/usr/bin/env python3
"""SessionStart(matcher=compact) hook: after a jumpcode pane compacts, re-inject its identity
and the dispatch protocol so it does not drift or go silent.

Hard-gated to jumpcode panes: requires the firing pane's @jumpcode_role tmux option AND a
state/sessions/<ws>.json whose `session` matches the current tmux session. Any other Claude
session (no tmux, no role, or unknown session) prints nothing and exits 0.
"""
import json
import os
import subprocess
import sys


def tmux(*args):
    try:
        return subprocess.run(["tmux", *args], capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return ""


def charter_dir(workspace_root):
    """Overlay roles dir if it exists (overlay wins), else the central JUMPCODE_HOME roles."""
    overlay = os.path.join(workspace_root, ".jumpcode", "roles")
    if os.path.isdir(overlay):
        return overlay
    return os.path.join(os.environ.get("JUMPCODE_HOME", ""), "roles")


def rehydrate_card(role, ws, workspace_root, jumpcode_home):
    proto = os.path.join(jumpcode_home, "roles", "_PROTOCOL.md")
    base = (
        f"You just COMPACTED — your context was summarized. Restore yourself before acting. "
        f"You are the **{role}** in jumpcode workspace **{ws}** (root `{workspace_root}`). "
        f"Re-read your charter in `{charter_dir(workspace_root)}/` and the protocol `{proto}`. "
        f"You are woken ONLY by dispatch; you cannot poll your own inbox."
    )
    if role == "orchestrator":
        return base + (
            " Re-check `dispatch status` (open loops) and `health` (team state) before you "
            "resume relaying work."
        )
    return base + (
        f" When you FINISH a task, report back with "
        f"`$JUMPCODE_HOME/bin/dispatch send --from {role} --to orchestrator "
        f"--kind report-done --reply-to <the request's DSP-ID>`. RIGHT NOW, tell the "
        f"orchestrator you are back: `$JUMPCODE_HOME/bin/dispatch send --from {role} "
        f"--to orchestrator --kind notice \"compaction complete — rehydrated, resuming\"`."
    )


def state_for_session(session):
    home = os.environ.get("JUMPCODE_HOME")
    if not home or not session:
        return None
    sdir = os.path.join(home, "state", "sessions")
    try:
        names = os.listdir(sdir)
    except OSError:
        return None
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(sdir, name), encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("session") == session:
            return data
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("source") != "compact":
        return 0
    pane = os.environ.get("TMUX_PANE", "")
    if not pane:
        return 0
    role = tmux("show-options", "-pqv", "-t", pane, "@jumpcode_role")
    if not role:
        return 0
    session = (os.environ.get("JUMPCODE_TMUX_SESSION")
               or tmux("display-message", "-p", "-t", pane, "#{session_name}"))
    state = state_for_session(session)
    if not state:           # gate (b): unknown session → not a jumpcode workspace
        return 0
    card = rehydrate_card(role, state.get("workspace", session),
                          state.get("workspace_root", ""),
                          os.environ.get("JUMPCODE_HOME", ""))
    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": card},
        "suppressOutput": True,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Then: `chmod +x ~/.claude/hooks/jumpcode-rehydrate-after-compact.py`.

Note: the state file lacks an explicit `workspace` key in some records — it does have
`workspace` per `bugsmash.json`; fall back to `session` if absent (done above).

**Step 4: Run test, verify pass**

Run: `python3 -m unittest tests.test_compaction_hooks -v`
Expected: PASS (all 4+ tests).

**Step 5: Commit**

```bash
cd /Users/seanchiu/Desktop/workspace-macbook/.jumpcode
git add tests/test_compaction_hooks.py
git commit -m "test: rehydration card (lead reports back + announces; orchestrator self-checks)"
```

---

## Task 4: Register the SessionStart hook in global settings (Component 2 glue)

**Files:**
- Modify: `~/.claude/settings.json`

**Step 1: Add the SessionStart hook entry**

Add a `SessionStart` block alongside the existing `UserPromptSubmit`. Final `hooks` shape:

```json
"SessionStart": [
  {
    "matcher": "compact",
    "hooks": [
      {
        "type": "command",
        "command": "~/.claude/hooks/jumpcode-rehydrate-after-compact.py",
        "timeout": 10
      }
    ]
  }
]
```

Edit carefully (preserve the existing `UserPromptSubmit` array). Validate JSON:
`python3 -c "import json; json.load(open('$HOME/.claude/settings.json'))"` → no output = valid.

**Step 2: Smoke test the gating with a crafted payload (no tmux)**

```bash
echo '{"source":"compact"}' | ~/.claude/hooks/jumpcode-rehydrate-after-compact.py; echo "exit=$?"
```
Expected: no stdout, `exit=0` (no `TMUX_PANE` → gated out). Confirms non-jumpcode sessions no-op.

**Step 3: Live verification (in the running bugsmash team)**

In a lead pane (e.g. backend-lead `%94`) that is idle, run `/compact`. After it finishes, the
pane's next context should contain the rehydrate card; the lead should emit a `notice`
dispatch. Confirm via `./.jumpcode/bin/dispatch log` (a "compaction complete" notice appears).
If `/hooks` was never opened in that pane, the hook may not be loaded until restart — note in
the activation caveat (same as the reminder hook).

**Step 4: Commit (settings.json is outside the repo — record intent only)**

```bash
cd /Users/seanchiu/Desktop/workspace-macbook/.jumpcode
git commit --allow-empty -m "feat: SessionStart(compact) rehydration hook registered globally"
```

---

## Task 5: `recompact` CLI verb (Component 3)

**Files:**
- Modify: `.jumpcode/bin/jumpcode` (add `cmd_recompact` + subparser)
- Create: `.jumpcode/bin/recompact` (bash wrapper)
- Test: `.jumpcode/tests/test_recompact.py` (Create — model on `tests/test_wake.py`)

**Step 0: Read the tmux-stub pattern**

Read `.jumpcode/tests/test_wake.py` fully to copy how it stubs `tmux` (PATH shim / fake binary)
and how it invokes `bin/jumpcode` as a subprocess.

**Step 1: Write the failing test**

Create `.jumpcode/tests/test_recompact.py` mirroring `test_wake.py`'s harness. Assert that
`jumpcode recompact --role backend-lead` resolves the pane via `@jumpcode_role` and sends the
keystroke sequence `Escape`, `/compact`, `Enter` to that pane (capture the fake tmux's recorded
argv). Assert an unknown role exits non-zero with a clear message and sends NO keys.

**Step 2: Run, verify fail**

Run: `python3 -m unittest tests.test_recompact -v`
Expected: FAIL — `invalid choice: 'recompact'`.

**Step 3: Implement `cmd_recompact` + subparser**

Add near `wake_pane` in `.jumpcode/bin/jumpcode`:

```python
def recompact_pane(session: str, role: str) -> bool:
    """Type /compact into a role's pane. Identity/protocol is restored by the SessionStart
    rehydrate hook, so no follow-up message is queued here."""
    if not session:
        return False
    try:
        out = subprocess.run(
            ["tmux", "list-panes", "-s", "-t", session, "-F", "#{pane_id}\t#{@jumpcode_role}"],
            capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    pane = resolve_pane(out, role)
    if not pane:
        return False
    subprocess.run(["tmux", "send-keys", "-t", pane, "Escape"], check=False)      # clear menu
    subprocess.run(["tmux", "send-keys", "-t", pane, "C-u"], check=False)         # clear input
    subprocess.run(["tmux", "send-keys", "-t", pane, "--", "/compact"], check=False)
    subprocess.run(["tmux", "send-keys", "-t", pane, "Enter"], check=False)
    return True


def cmd_recompact(args: argparse.Namespace, home: Path) -> int:
    session = resolve_session()
    if recompact_pane(session, args.role):
        print(f"sent /compact to {args.role}")
        return 0
    print(f"recompact: could not resolve pane for role '{args.role}' in session '{session}'",
          file=sys.stderr)
    return 1
```

Register the subparser (near the `peek` parser) and dispatch it in the command table:

```python
    rc = sub.add_parser("recompact", help="type /compact into a role's pane (orchestrator-driven)")
    rc.add_argument("--role", required=True, help="role whose pane should compact")
    rc.set_defaults(func=cmd_recompact)
```

(If the script dispatches via `if args.cmd == ...` rather than `func`, add a matching branch:
`elif args.cmd == "recompact": return cmd_recompact(args, home)`.)

**Step 4: Run test, verify pass**

Run: `python3 -m unittest tests.test_recompact -v`
Expected: PASS.

**Step 5: Create the bash wrapper**

Create `.jumpcode/bin/recompact` (mirror `.jumpcode/bin/dispatch`), then `chmod +x`:

```bash
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$DIR/jumpcode" recompact "$@"
```

**Step 6: Full suite + commit**

```bash
cd /Users/seanchiu/Desktop/workspace-macbook
python3 -m unittest discover -s .jumpcode/tests
cd .jumpcode
git add bin/jumpcode bin/recompact tests/test_recompact.py
git commit -m "feat: recompact verb — orchestrator types /compact into a lead's pane"
```

---

## Task 6: Orchestrator charter — "Compaction management" section

**Files:**
- Modify: `.jumpcode/roles/🧭 orchestrator.md`

**Step 1: Add the section**

Add a concise subsection to the central orchestrator charter:

```markdown
## Compaction management

A `UserPromptSubmit` hook reports, on every wake, any LEAD whose context window is over the
threshold (default 200k). When a lead is flagged:

1. Wait until that lead is **idle** (`dispatch status` shows no in-flight request, or `health`
   shows it idle) so compaction does not interrupt in-flight work.
2. `$JUMPCODE_HOME/bin/recompact --role <lead>` — this types `/compact` into its pane.
3. The lead auto-rehydrates (a `SessionStart` hook re-reads its charter + protocol) and sends
   you a `notice` "compaction complete — rehydrated, resuming". Wait for that notice before
   re-dispatching work to it.

When YOUR OWN context is flagged, checkpoint open loops to the system of record + dispatch log,
then `/compact` (or ask the human). After you compact, the same SessionStart hook restores your
identity and tells you to re-check `dispatch status` / `health`.
```

**Step 2: Validate charter still resolves**

Run: `./.jumpcode/bin/jumpcode roles discover --workspace bugsmash`
Expected: orchestrator + all leads + protocol resolve (no errors).

**Step 3: Commit**

```bash
cd /Users/seanchiu/Desktop/workspace-macbook/.jumpcode
git add "roles/🧭 orchestrator.md"
git commit -m "docs(charter): orchestrator drives lead compaction + post-compaction rehydrate"
```

---

## Task 7: Full regression + memory

**Step 1: Run the whole suite**

Run: `cd /Users/seanchiu/Desktop/workspace-macbook && python3 -m unittest discover -s .jumpcode/tests`
Expected: all tests pass (existing + `test_compaction_hooks` + `test_recompact`).

**Step 2: Update the hook memory note**

Update `~/.claude/projects/.../memory/orchestrator-compact-reminder-hook.md` to record: the hook
now also reports leads over threshold; the new `SessionStart(compact)` rehydrate hook; the
`recompact` verb; and the double scoping gate. Add the index line if a new memory file is made.

**Step 3: Final commit**

```bash
cd /Users/seanchiu/Desktop/workspace-macbook/.jumpcode
git add docs/plans/2026-06-17-compaction-resilience*.md
git commit -m "docs: compaction resilience design + plan"
```

(Do NOT push — public remote; Sean pushes on explicit ask.)

---

## Definition of done

- `python3 -m unittest discover -s .jumpcode/tests` is green.
- Orchestrator wake reports any lead over threshold; `recompact --role <lead>` compacts a lead.
- A compacted lead re-reads its charter and emits a "compaction complete" notice; a compacted
  orchestrator is told to re-check `dispatch status`/`health`.
- Both hooks no-op for any non-jumpcode session (no `@jumpcode_role` or unknown session).
- Nothing added to any repo's `.claude/settings.json`; `.jumpcode` committed locally, not pushed.
```
