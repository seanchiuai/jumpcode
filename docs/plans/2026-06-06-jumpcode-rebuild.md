# Jumpcode Rebuild Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild the jumpcode to match the grilled design — a working dispatch (live-wake + durable-log) system over visible orchestrator/team-lead panes, with projects/tasks delegated entirely to the external tracker (GitHub issues).

**Architecture:** Slim the Python CLI down to *dispatch* only (retire the local run/task/project/report registry — GitHub issues is the system of record per ADR 0006). Make the wake mechanism actually work by targeting panes via a machine-readable `@jumpcode_role` tmux option instead of the Claude-overwritten pane title. Restructure role prompts into thin charters + one shared protocol. Always launch fresh (ADR 0004); agents orient from the tracker + the dispatch log.

**Tech Stack:** Python 3 (stdlib only), bash, tmux, Claude Code CLI, the tracker MCP (used by the agents, not the jumpcode).

**Authoritative design refs (read before starting):**
- `.jumpcode/CONTEXT.md` (glossary)
- `.jumpcode/docs/adr/0001`–`0004`

---

## Pre-flight notes (deviations from the writing-plans defaults)

- **Not a git repo + no worktree.** The skill assumes both. Decision needed (Task 0). Until then, "Commit" steps are written as `git ...` but are **no-ops if git isn't initialized** — do Task 0 first or skip the commit steps.
- **The jumpcode never calls the tracker.** The tracker is the *agents'* responsibility via their Claude Code tracker MCP. No tracker code lands in the Python CLI. "Wiring the tracker" = MCP availability for panes + charter instructions.
- **tmux/wake is hard to unit-test.** We isolate the *pure* part (mapping a role → pane id from `tmux list-panes` output) so it's TDD-able; the actual `send-keys` is a thin, manually-verified wrapper.
- A live `macbook-webapp` tmux session and a stale `bb-ambassador` session predate this plan. Kill `bb-ambassador`; relaunch `macbook-webapp` only after Task 6.

---

## Task 0: Decide + set up version control

**Why:** This is a large rework that deletes/renames many files. Local version control is worth it. This is *local* git (never pushed), which does not violate "don't commit to the BuilderBase repo."

**Step 1:** Ask Sean: initialize a local-only git repo at `/Users/seanchiu/Desktop/workspace-macbook`? (Recommended: yes.)

**Step 2 (if yes):**
```bash
cd /Users/seanchiu/Desktop/workspace-macbook
git init
printf '%s\n' '.jumpcode/state/' '.jumpcode/shared/' '__pycache__/' '*.pyc' > .gitignore
git add -A && git commit -m "chore: snapshot jumpcode before grilled-design rebuild"
```

**Step 3 (if no):** Note that "Commit" steps below are skipped; rely on manual backups. Make one now:
```bash
cp -r .jumpcode ".jumpcode.bak.20260606"
```

---

## Task 1: Add a machine-readable role id to panes (wake foundation)

**Files:**
- Modify: `.jumpcode/bin/start-webapp` (the `tmux set-option ... @role` block)

**Why:** Wake must target a stable id. Claude overwrites pane *titles*; the pretty `@role` label is for humans. Add a parallel machine id `@jumpcode_role` = canonical role (`orchestrator`, `frontend-lead`, `backend-lead`, `qa-lead`).

**Step 1:** After each existing `tmux set-option -pt "$PANE" @role "..."` line, add a sibling:
```bash
tmux set-option -pt "$ORCH"  @jumpcode_role "orchestrator"
tmux set-option -pt "$FRONT" @jumpcode_role "frontend-lead"
tmux set-option -pt "$BACK"  @jumpcode_role "backend-lead"
tmux set-option -pt "$QA"    @jumpcode_role "qa-lead"
```

**Step 2: Verify (manual, against the live session after a relaunch in Task 6).** For now just syntax-check:
```bash
bash -n .jumpcode/bin/start-webapp
```
Expected: no output (valid).

**Step 3: Commit**
```bash
git add .jumpcode/bin/start-webapp && git commit -m "feat(wake): tag panes with machine-readable @jumpcode_role"
```

---

## Task 2: Pure role→pane resolver (TDD)

**Files:**
- Create: `.jumpcode/bin/jumpcode` — add `resolve_pane(panes_text, role)` function
- Test: `.jumpcode/tests/test_wake.py`

**Step 1: Write the failing test**
```python
# .jumpcode/tests/test_wake.py
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
import importlib.util
spec = importlib.util.spec_from_file_location("jumpcode", Path(__file__).resolve().parents[1] / "bin" / "jumpcode")
jumpcode = importlib.util.module_from_spec(spec); spec.loader.exec_module(jumpcode)

class ResolvePaneTests(unittest.TestCase):
    SAMPLE = "%26\torchestrator\n%27\tfrontend-lead\n%28\tbackend-lead\n%29\tqa-lead\n"
    def test_resolves_exact_role(self):
        self.assertEqual(jumpcode.resolve_pane(self.SAMPLE, "backend-lead"), "%28")
    def test_unknown_role_returns_none(self):
        self.assertIsNone(jumpcode.resolve_pane(self.SAMPLE, "nope"))
    def test_ignores_panes_without_role(self):
        self.assertIsNone(jumpcode.resolve_pane("%30\t\n", "orchestrator"))

if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**
Run: `python3 .jumpcode/tests/test_wake.py -v`
Expected: FAIL (`AttributeError: module 'jumpcode' has no attribute 'resolve_pane'`)

**Step 3: Write minimal implementation** (add near the top of `jumpcode`, after imports)
```python
def resolve_pane(panes_text: str, role: str) -> Optional[str]:
    """Map a canonical role to a tmux pane id, given `list-panes -F '#{pane_id}\t#{@jumpcode_role}'` output."""
    for line in panes_text.splitlines():
        if "\t" not in line:
            continue
        pane_id, pane_role = line.split("\t", 1)
        if pane_role.strip() == role:
            return pane_id.strip()
    return None
```

**Step 4: Run test to verify it passes**
Run: `python3 .jumpcode/tests/test_wake.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**
```bash
git add .jumpcode/bin/jumpcode .jumpcode/tests/test_wake.py
git commit -m "feat(wake): pure role->pane resolver with tests"
```

---

## Task 3: Wake wrapper (inject into a pane)

**Files:**
- Modify: `.jumpcode/bin/jumpcode` — add `wake_pane(session, role, text)`

**Why:** The thin side-effect layer. Not unit-tested (needs tmux); verified manually in Task 8.

**Step 1: Implement**
```python
import subprocess

def wake_pane(session: str, role: str, text: str) -> bool:
    """Inject a one-line nudge into the role's pane. Returns True if a pane was found+sent."""
    if not session:
        return False
    try:
        out = subprocess.run(
            ["tmux", "list-panes", "-t", session, "-F", "#{pane_id}\t#{@jumpcode_role}"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    pane = resolve_pane(out, role)
    if not pane:
        return False
    subprocess.run(["tmux", "send-keys", "-t", pane, "--", text], check=False)
    subprocess.run(["tmux", "send-keys", "-t", pane, "Enter"], check=False)
    return True
```

**Step 2: Syntax check**
Run: `python3 -m py_compile .jumpcode/bin/jumpcode`
Expected: no output.

**Step 3: Commit**
```bash
git add .jumpcode/bin/jumpcode && git commit -m "feat(wake): tmux send-keys wrapper targeting @jumpcode_role"
```

---

## Task 4: Add concurrency-safe append + id generation (TDD)

**Files:**
- Modify: `.jumpcode/bin/jumpcode` — wrap `append_event` write and `make_id` read-modify-write in `fcntl.flock`
- Test: `.jumpcode/tests/test_concurrency.py`

**Why:** Multiple lead panes can dispatch simultaneously; the audit's id-collision bug is real for the dispatch log.

**Step 1: Write the failing test** (spawns parallel id generations, asserts all unique)
```python
# .jumpcode/tests/test_concurrency.py
import os, sys, tempfile, unittest, concurrent.futures, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("jumpcode", Path(__file__).resolve().parents[1] / "bin" / "jumpcode")
jumpcode = importlib.util.module_from_spec(spec); spec.loader.exec_module(jumpcode)

class ConcurrencyTests(unittest.TestCase):
    def test_parallel_appends_unique_ids(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d) / ".jumpcode"
            def one(i):
                ev = {"type": "dispatch.sent", "dispatch_id": jumpcode.make_id(home, "dsp", "dispatch")}
                jumpcode.append_event(home, "dispatch", ev)
                return ev["dispatch_id"]
            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
                ids = list(ex.map(one, range(64)))
            self.assertEqual(len(ids), len(set(ids)), "duplicate ids generated under concurrency")
```

**Step 2: Run test to verify it fails**
Run: `python3 .jumpcode/tests/test_concurrency.py -v`
Expected: FAIL (duplicate ids) — note: may be flaky pre-fix; that's the point.

**Step 3: Implement** — add a lock helper and use it. Update `EVENT_FILES` to include `"dispatch": "dispatches.jsonl"`. Wrap the critical region:
```python
import fcntl
from contextlib import contextmanager

@contextmanager
def _lock(home: Path):
    ensure_dirs(home)
    lock_path = home / "state" / ".lock"
    with lock_path.open("w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)
```
Then make `make_id` + its caller's `append_event` happen inside a single `_lock(home)` for dispatch sends (combine id-mint + append so they're atomic together).

**Step 4: Run test to verify it passes**
Run: `python3 .jumpcode/tests/test_concurrency.py -v`
Expected: PASS

**Step 5: Commit**
```bash
git add .jumpcode/bin/jumpcode .jumpcode/tests/test_concurrency.py
git commit -m "fix(concurrency): flock id-mint+append to prevent dispatch id collisions"
```

---

## Task 5: Replace mail/run/task/report with `dispatch` (TDD)

**Files:**
- Modify: `.jumpcode/bin/jumpcode` — remove `cmd_run`, `cmd_task`, `cmd_report`, `reconstruct_tasks`, `current_run*`; rebuild `cmd_dispatch`
- Modify: `.jumpcode/tests/test_jumpcode.py` — drop run/task/report tests; add dispatch tests
- Delete: `.jumpcode/bin/{run,task,report,mail}`; Create: `.jumpcode/bin/dispatch`
- Delete (state): `runs.jsonl`, `tasks.jsonl`, `reports.jsonl`, `current_run.json`

**Target command surface:**
```
dispatch send --from R --to R [--project P] [--task T] [--subject S]
             [--kind request|reply|report-done|report-blocked|notice] [--no-wake] BODY...
dispatch inbox R [--json]      # recovery/review: dispatches addressed to R
dispatch show DID [--json]
dispatch log [N]               # human-readable feed (also exposed via `convo`)
```

**Step 1: Write failing tests** (in `test_jumpcode.py`, replacing removed ones)
```python
def test_dispatch_send_logs_and_is_in_inbox(self):
    sent = json.loads(run_cmd(self.tmp_path, "dispatch", "send",
        "--from", "orchestrator", "--to", "backend-lead",
        "--task", "ENG-12", "--subject", "Build auth", "--no-wake",
        "Implement the auth endpoints.").stdout)
    self.assertEqual(sent["type"], "dispatch.sent")
    self.assertTrue(sent["dispatch_id"].startswith("dsp-"))
    self.assertEqual(sent["task"], "ENG-12")
    inbox = json.loads(run_cmd(self.tmp_path, "dispatch", "inbox", "backend-lead", "--json").stdout)
    self.assertEqual([m["dispatch_id"] for m in inbox], [sent["dispatch_id"]])

def test_report_kind_is_just_a_dispatch(self):
    sent = json.loads(run_cmd(self.tmp_path, "dispatch", "send",
        "--from", "backend-lead", "--to", "orchestrator",
        "--kind", "report-done", "--task", "ISSUE-12", "--no-wake",
        "Done; updated ISSUE-12 in the tracker.").stdout)
    self.assertEqual(sent["kind"], "report-done")
```
(`--no-wake` lets tests avoid tmux.)

**Step 2: Run to verify fail**
Run: `python3 .jumpcode/tests/test_jumpcode.py -v`
Expected: FAIL (unknown command `dispatch`, plus removed-test references error)

**Step 3: Implement** — rewrite `cmd_dispatch` (adapt the old `cmd_mail`): build the event with fields `{type:"dispatch.sent", dispatch_id, project, task, from, to, kind, subject, body, reply_to, created_at}`, append under kind `"dispatch"`, mirror to `conversation.log`, and unless `--no-wake`, call `wake_pane(os.environ.get("JUMPCODE_TMUX_SESSION",""), to, f"[dispatch from {from_}] {subject or body[:80]} — run ./.jumpcode/bin/dispatch inbox {to}")`. Remove run/task/report parsers + handlers from `build_parser`/`main`. Delete obsolete wrappers; create `bin/dispatch` mirroring the `bin/mail` one-liner but calling `dispatch`.

**Step 4: Run tests**
Run: `python3 .jumpcode/tests/test_jumpcode.py && python3 .jumpcode/tests/test_wake.py && python3 .jumpcode/tests/test_concurrency.py`
Expected: all PASS

**Step 5: Clean up obsolete state + wrappers**
```bash
cd /Users/seanchiu/Desktop/workspace-macbook
rm -f .jumpcode/bin/run .jumpcode/bin/task .jumpcode/bin/report .jumpcode/bin/mail
rm -f .jumpcode/state/runs.jsonl .jumpcode/state/tasks.jsonl .jumpcode/state/reports.jsonl .jumpcode/state/current_run.json
```

**Step 6: Commit**
```bash
git add -A && git commit -m "feat(dispatch): replace mail/run/task/report with dispatch; GitHub issues own tasks"
```

---

## Task 6: Update `status`, `convo`, `ask`, `start-webapp` wrappers

**Files:**
- Modify: `.jumpcode/bin/status` (no more `run summary`), `.jumpcode/bin/ask`, `.jumpcode/bin/start-webapp`
- Delete: `.jumpcode/bin/ask` if redundant with `dispatch send` (decide)

**Step 1:** `status` → print a dispatch-log summary instead of run summary:
```bash
exec python3 "$DIR/jumpcode" dispatch log "${1:-40}"
```
**Step 2:** `ask` → make it a thin alias for `dispatch send --from ${JUMPCODE_FROM:-human} --to $1` (wake included by default), or delete it and standardize on `dispatch`. Recommended: delete `ask`; the dispatch verb now covers it.

**Step 3:** `start-webapp` → the initial `send_initial` prompts should point agents at the **shared protocol + their charter** (Task 7 paths) and tell them to read the **tracker (GitHub issues)**, not the retired `task`/`status` registry. Replace the per-pane send text accordingly. Keep the iTerm-open + monitor window. Confirm it still kills/relaunches cleanly.

**Step 4: Verify**
```bash
bash -n .jumpcode/bin/start-webapp .jumpcode/bin/status .jumpcode/bin/convo
```
Expected: clean.

**Step 5: Commit**
```bash
git add -A && git commit -m "chore: point wrappers + launcher at dispatch/tracker/charters"
```

---

## Task 7: Charters + shared protocol (ADR-aligned docs)

**Files:**
- Create: `.jumpcode/roles/_PROTOCOL.md` (shared protocol — common interaction rules)
- Rewrite: `.jumpcode/roles/{orchestrator,frontend-lead,backend-lead,qa-lead}.md` as **thin charters** (4 sections: identity+domain, editable territory & soft guardrails, domain conventions, pointer to `_PROTOCOL.md`)

**Step 1:** Write `_PROTOCOL.md` covering: the dispatch model (live + logged), how to read your inbox on a wake, how to report (dispatch `--kind report-done|report-blocked` **and** update the tracker issue), relay rules (leads can't talk to leads; ask the orchestrator), the topology (ADR 0001), and that work/tasks live in the **tracker (GitHub issues)**.

**Step 2:** Rewrite each role file to the 4-section thin charter. Backend lead territory e.g. `backend/**, api/**` (soft); frontend `frontend/**, ui/**`; qa `tests/**`. Each ends with "See `_PROTOCOL.md` for interaction rules."

**Step 3: Verify** the orchestrator charter encodes: creates/decomposes work into the tracker, dispatches leads, integrates, has general tracker access, is the only relay.

**Step 4: Commit**
```bash
git add .jumpcode/roles && git commit -m "docs(roles): thin charters + shared protocol per ADR 0001/0002"
```

---

## Task 8: Reconcile stale top-level docs

**Files:**
- Rewrite: `.jumpcode/{README,INSTRUCTIONS,HANDOFF}.md`, `ORCHESTRATION.md`, `AGENTS.md`
- Fix: `HANDOFF.md` corrupted token `任务/task`

**Step 1:** Purge "run", "mail", "task registry", "report command" language. Replace with: dispatch, tracker-owned tasks, fresh-launch, charters/protocol, the 3-layer model (orchestrator/leads/subagents), and the human→lead direct path. Point readers to `CONTEXT.md` + `docs/adr/`.

**Step 2: Verify** no stale terms remain:
```bash
cd /Users/seanchiu/Desktop/workspace-macbook
grep -rniE '\b(mail|\brun start\b|tasks?\.jsonl|specialist)\b' .jumpcode/*.md *.md .jumpcode/roles || echo "clean"
```
Expected: `clean` (or only intentional historical mentions).

**Step 3: Commit**
```bash
git add -A && git commit -m "docs: reconcile all prose with grilled design"
```

---

## Task 9: Tracker MCP availability for panes (verify, don't assume)

**Why:** Orchestrator + leads must reach the tracker. The jumpcode doesn't call the tracker; the *panes'* Claude Code must have the tracker MCP. Sean previously did not want `.mcp.json` in the repo — so prefer user-level config.

**Step 1:** Check whether `claude` panes already see tracker tools (the operator has it). Launch one throwaway pane and inspect, or check `~/.claude` / project MCP config. Document the finding.

**Step 2:** If not available, decide with Sean: user-level MCP (`~/.claude`) vs a repo `.mcp.json` (he disliked this). Configure the chosen one.

**Step 3:** No commit unless config files changed; if so commit them.

---

## Task 10: End-to-end live verification (closes the original open thread)

**Why:** Prove the live loop works — the thing that was never verified.

**Step 1:** Kill stale session: `tmux kill-session -t bb-ambassador 2>/dev/null || true`

**Step 2:** Relaunch: `./.jumpcode/bin/start-webapp`

**Step 3:** Confirm panes carry machine roles:
```bash
tmux list-panes -t macbook-webapp:roles -F '#{@jumpcode_role}'
```
Expected: orchestrator / frontend-lead / backend-lead / qa-lead

**Step 4: Drive the loop.** From Sean:
```bash
./.jumpcode/bin/dispatch send --from human --to orchestrator --subject "smoke" "Create a tracker issue for a trivial task, dispatch backend-lead to do it, and report back."
```
Watch: orchestrator pane wakes → dispatches backend-lead → backend-lead pane wakes → does it → reports (dispatch + tracker) → orchestrator integrates. Confirm each `wake` landed and each step appears in `dispatch log` + the tracker.

**Step 5:** If a wake doesn't land, debug `wake_pane` against live `@jumpcode_role` output (the usual cause is a session-name/`JUMPCODE_TMUX_SESSION` mismatch).

**Step 6: Commit** any fixes, then update `jumpcode-open-thread` memory: live loop verified.

---

## Out of scope (deferred, per grill)

- Hard guardrails (Claude Code deny rules / hooks) — soft only in v1.
- Output eval/rating — open user-ask; needs a research spike first.
- Watcher-daemon wake — sender-triggered wake only in v1.
- Resume — never (always fresh, ADR 0004).
