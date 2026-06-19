# Fleet Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `jumpcode fleet` command that shows every workspace and its status (active / idle / past / error) as a live auto-refreshing terminal dashboard.

**Architecture:** A pure classifier function decides a workspace's status from already-gathered data (manifest, liveness, panes, last-dispatch, config-check). A gather function assembles that data per workspace by reusing existing helpers (`load_manifest`, `_tmux_session_alive`, a refactored `scan_session`, `open_requests`, `_age_str`). A thin curses render loop paints it; `--json`/`--once` give non-TUI seams. The only change to existing behavior is factoring `cmd_health`'s pane loop into a shared `scan_session` helper.

**Tech Stack:** Python 3 stdlib only (`curses`, `json`, `subprocess`, `pathlib`), tmux CLI, existing `jumpcode` module. Tests via `unittest` loaded with `SourceFileLoader` (see `tests/test_health.py`).

**Module under edit:** `.jumpcode/bin/jumpcode` (single-file python CLI). All line numbers below are from the current file and will drift as you edit — re-grep before each change.

**Run all tests with:** `python3 -m unittest discover -s .jumpcode/tests` (from workspace root).

---

### Task 1: Refactor `cmd_health` pane scan into reusable `scan_session`

Behavior-preserving extraction so `health` and `fleet` share one pane-scanning + state path. No new behavior — `test_health.py` must stay green.

**Files:**
- Modify: `.jumpcode/bin/jumpcode` (the pane-loop block inside `cmd_health`, currently ~lines 953–982)

**Step 1: Read the current block**

Re-read `cmd_health` (grep `def cmd_health`) lines through the agent-append loop so your extraction matches the live code exactly.

**Step 2: Add the helper above `cmd_health`**

Insert a new function immediately before `def cmd_health`:

```python
def scan_session(session: str, subs: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    """Live pane scan for one tmux session — the shared core of `health` and `fleet`.

    Returns one dict per pane with role, pane id, liveness, runtime, classified
    `state` (working|waiting|idle|stopped via pane_state), and subagents. `subs` is
    the active-subagents map from active_subagents(); pass {} if not needed. Returns
    [] when the session has no panes or tmux is unavailable.
    """
    try:
        panes_text = subprocess.run(
            ["tmux", "list-panes", "-s", "-t", session, "-F",
             "#{pane_id}\t#{@jumpcode_role}\t#{pane_current_command}\t#{pane_dead}\t#{@jumpcode_runtime}"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    agents: List[Dict[str, Any]] = []
    for line in panes_text.splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        pane_id, role, cmd, dead = parts[0], parts[1].strip(), parts[2], parts[3]
        runtime = parts[4].strip() if len(parts) >= 5 else ""
        if not role:
            continue
        alive = dead != "1"
        state = "stopped" if not alive else pane_state(_tmux_capture(pane_id), runtime or "claude")
        agents.append({
            "role": role, "pane": pane_id, "alive": alive, "command": cmd,
            "runtime": runtime or "claude",
            "state": state, "subagents": subs.get(role, []),
        })
    return agents
```

**Step 3: Rewrite the `cmd_health` block to call it**

Replace the inline `panes_text = ...` fetch + the `for line in panes_text.splitlines()` loop (the part that builds `agents` from panes, NOT the later "roles absent from panes" loop) with:

```python
    agents: List[Dict[str, Any]] = []
    seen_roles = set()
    if session:
        for a in scan_session(session, subs):
            seen_roles.add(a["role"])
            agents.append({**a, **_seen_fields(a["role"])})
```

Leave everything after it (the `for role in sorted(... not in seen_roles ...)` absent-roles loop, clients count, printing) unchanged.

**Step 4: Run health tests**

Run: `python3 -m unittest discover -s .jumpcode/tests -k Health -v`
Expected: PASS (same as before — pure refactor).

**Step 5: Smoke-test live health**

Run: `./.jumpcode/bin/health`
Expected: same output shape as before (panes, states, visibility).

**Step 6: Commit**

```bash
cd .jumpcode && git add bin/jumpcode && git commit -m "refactor: extract scan_session from cmd_health for reuse"
```

---

### Task 2: Pure status classifier `classify_workspace`

The heart of the feature. Pure function: data in, status string out. No tmux, no IO — fully unit-testable.

**Files:**
- Modify: `.jumpcode/bin/jumpcode` (add function near the other pure helpers, e.g. after `_age_str`)
- Test: `.jumpcode/tests/test_fleet.py` (create)

**Step 1: Write the failing tests**

Create `.jumpcode/tests/test_fleet.py`:

```python
import importlib.util
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

_JUMPCODE = Path(__file__).resolve().parents[1] / "bin" / "jumpcode"
spec = importlib.util.spec_from_file_location(
    "jumpcode", _JUMPCODE, loader=SourceFileLoader("jumpcode", str(_JUMPCODE))
)
jumpcode = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jumpcode)

IDLE_SECS = 600  # 10 min


def wp(alive, agents=None, last_dispatch_age=None, open_loops=0, config_ok=True):
    """Build the classifier input dict for one workspace."""
    return {
        "alive": alive,
        "agents": agents or [],
        "last_dispatch_age_secs": last_dispatch_age,
        "stale_open_loops": open_loops,
        "config_ok": config_ok,
    }


class ClassifyTests(unittest.TestCase):
    def test_no_session_is_past(self):
        self.assertEqual(jumpcode.classify_workspace(wp(alive=False)), "past")

    def test_dead_session_past_even_if_config_broken(self):
        # config is only an error signal for a LIVE workspace
        self.assertEqual(
            jumpcode.classify_workspace(wp(alive=False, config_ok=False)), "past")

    def test_config_broken_while_alive_is_error(self):
        self.assertEqual(
            jumpcode.classify_workspace(wp(alive=True, config_ok=False)), "error")

    def test_stale_open_loop_is_error(self):
        self.assertEqual(
            jumpcode.classify_workspace(
                wp(alive=True, open_loops=1, last_dispatch_age=4000)), "error")

    def test_working_pane_is_active(self):
        self.assertEqual(
            jumpcode.classify_workspace(
                wp(alive=True, agents=[{"state": "working"}, {"state": "idle"}],
                   last_dispatch_age=9999)), "active")

    def test_recent_dispatch_is_active_even_if_all_idle(self):
        self.assertEqual(
            jumpcode.classify_workspace(
                wp(alive=True, agents=[{"state": "idle"}],
                   last_dispatch_age=120)), "active")

    def test_all_idle_and_quiet_is_idle(self):
        self.assertEqual(
            jumpcode.classify_workspace(
                wp(alive=True, agents=[{"state": "idle"}, {"state": "idle"}],
                   last_dispatch_age=4000)), "idle")

    def test_idle_boundary_just_under_threshold_is_active(self):
        self.assertEqual(
            jumpcode.classify_workspace(
                wp(alive=True, agents=[{"state": "idle"}],
                   last_dispatch_age=IDLE_SECS - 1)), "active")

    def test_idle_boundary_at_threshold_is_idle(self):
        self.assertEqual(
            jumpcode.classify_workspace(
                wp(alive=True, agents=[{"state": "idle"}],
                   last_dispatch_age=IDLE_SECS)), "idle")

    def test_alive_no_panes_no_activity_is_idle(self):
        # session exists but no panes scanned and never any dispatch -> not "active"
        self.assertEqual(
            jumpcode.classify_workspace(
                wp(alive=True, agents=[], last_dispatch_age=None)), "idle")

    def test_error_wins_over_active(self):
        self.assertEqual(
            jumpcode.classify_workspace(
                wp(alive=True, agents=[{"state": "working"}],
                   open_loops=1, last_dispatch_age=4000)), "error")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run to verify it fails**

Run: `python3 -m unittest discover -s .jumpcode/tests -k Classify -v`
Expected: FAIL — `AttributeError: module 'jumpcode' has no attribute 'classify_workspace'`.

**Step 3: Implement the classifier**

Add after `_age_str` (grep `def _age_str`):

```python
FLEET_IDLE_SECS = 600  # all panes idle AND no dispatch newer than this -> "idle"


def classify_workspace(w: Dict[str, Any]) -> str:
    """Pure status classifier for one workspace. First match wins:
    error -> active -> idle -> past. Input keys:
      alive (bool), agents (list of {state}), last_dispatch_age_secs (int|None),
      stale_open_loops (int), config_ok (bool).
    """
    if not w["alive"]:
        return "past"
    # error: only meaningful while alive
    if not w["config_ok"] or w["stale_open_loops"] > 0:
        return "error"
    age = w["last_dispatch_age_secs"]
    recent = age is not None and age < FLEET_IDLE_SECS
    if any(a.get("state") in ("working", "waiting") for a in w["agents"]) or recent:
        return "active"
    return "idle"
```

**Step 4: Run to verify it passes**

Run: `python3 -m unittest discover -s .jumpcode/tests -k Classify -v`
Expected: PASS (all 11 tests).

**Step 5: Commit**

```bash
cd .jumpcode && git add bin/jumpcode tests/test_fleet.py && git commit -m "feat: pure classify_workspace status classifier + tests"
```

---

### Task 3: Per-workspace data gatherer `gather_fleet`

Assembles the classifier input for every manifest, then attaches status + display fields. Tmux/IO lives here, kept thin.

**Files:**
- Modify: `.jumpcode/bin/jumpcode` (add `gather_fleet` near `scan_session`)
- Test: `.jumpcode/tests/test_fleet.py` (add config-check tests that don't need tmux)

**Step 1: Write a failing test for the config check helper**

Add to `test_fleet.py` a class that exercises the pure config check (factor it so it takes a home + workspace and returns bool). Use a tmp dir:

```python
import json
import tempfile


class ConfigCheckTests(unittest.TestCase):
    def test_missing_workspace_json_is_not_ok(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            (home / "state" / "sessions").mkdir(parents=True)
            manifest = {"workspace": "x", "session": "s-x", "roles": []}
            self.assertFalse(jumpcode.workspace_config_ok(home, "x", manifest))

    def test_role_cwd_missing_is_not_ok(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            manifest = {"workspace": "x", "session": "s-x",
                        "roles": [{"role": "backend-lead", "cwd": "/no/such/dir"}]}
            # even if workspace.json existed, a vanished cwd fails the check
            self.assertFalse(jumpcode.workspace_config_ok(home, "x", manifest))

    def test_all_present_is_ok(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            real = home / "wt"; real.mkdir()
            # stub workspace.json where load_workspace_settings looks
            wsdir = home / "workspaces" / "x"; wsdir.mkdir(parents=True)
            (wsdir / "workspace.json").write_text(json.dumps(
                {"workspace_root": str(real)}), encoding="utf-8")
            manifest = {"workspace": "x", "session": "s-x",
                        "roles": [{"role": "backend-lead", "cwd": str(real)}]}
            self.assertTrue(jumpcode.workspace_config_ok(home, "x", manifest))
```

NOTE: confirm where `workspace_json_path` / `load_workspace_settings` actually look (grep `_workspace_json_candidates`) and adjust the stub path in `test_all_present_is_ok` to match a real candidate location before asserting True. If the candidates are outside `home`, simplify this test to only assert the cwd + parse behavior you can control.

**Step 2: Run to verify it fails**

Run: `python3 -m unittest discover -s .jumpcode/tests -k ConfigCheck -v`
Expected: FAIL — no `workspace_config_ok`.

**Step 3: Implement `workspace_config_ok` and `gather_fleet`**

```python
def workspace_config_ok(home: Path, workspace: str, manifest: Dict[str, Any]) -> bool:
    """True if the workspace's config still resolves: workspace.json present+parseable
    and every recorded role cwd still exists. Used as a fleet 'error' signal."""
    try:
        settings = load_workspace_settings(home, workspace)
    except Exception:
        return False
    if not settings:
        return False
    for r in manifest.get("roles", []):
        cwd = r.get("cwd")
        if cwd and not Path(cwd).exists():
            return False
    return True


def gather_fleet(home: Path) -> List[Dict[str, Any]]:
    """One row per recorded workspace, classified. Reads all manifests + the dispatch
    log once, scans live sessions via scan_session, and runs the pure classifier."""
    all_dispatches = events(home, "dispatch")
    rows: List[Dict[str, Any]] = []
    sdir = sessions_dir(home)
    manifests = sorted(sdir.glob("*.json")) if sdir.exists() else []
    for f in manifests:
        workspace = f.stem
        manifest = load_manifest(home, workspace) or {}
        session = manifest.get("session") or ""
        alive = bool(session) and _tmux_session_alive(session)
        agents = scan_session(session, {}) if alive else []
        ws_dispatches = [d for d in all_dispatches if d.get("session") == session]
        last_ts = max((d.get("created_at") or "" for d in ws_dispatches), default="")
        age = _age_secs(last_ts) if last_ts else None
        stale = sum(1 for r in open_requests(ws_dispatches)
                    if (_age_secs(r.get("created_at") or "") or 0) >= FLEET_IDLE_SECS)
        config_ok = workspace_config_ok(home, workspace, manifest)
        status = classify_workspace({
            "alive": alive, "agents": agents, "last_dispatch_age_secs": age,
            "stale_open_loops": stale, "config_ok": config_ok,
        })
        rows.append({
            "workspace": workspace, "session": session, "status": status,
            "alive": alive, "agents": agents, "config_ok": config_ok,
            "stale_open_loops": stale, "last_dispatch": last_ts or None,
        })
    return rows
```

Also add a small `_age_secs` helper next to `_age_str` (returns int seconds or None) since the classifier works in seconds while `_age_str` returns a display string:

```python
def _age_secs(iso_ts: Optional[str]) -> Optional[int]:
    if not iso_ts:
        return None
    try:
        t = datetime.strptime(iso_ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return int((datetime.now(timezone.utc) - t).total_seconds())
```

**Step 4: Run config tests**

Run: `python3 -m unittest discover -s .jumpcode/tests -k ConfigCheck -v`
Expected: PASS.

**Step 5: Commit**

```bash
cd .jumpcode && git add bin/jumpcode tests/test_fleet.py && git commit -m "feat: gather_fleet + workspace_config_ok with config-check tests"
```

---

### Task 4: `cmd_fleet` with `--json` and `--once` (non-curses paths)

Wire the command and its JSON/plain-text seams first; curses comes next so the data path is testable without a TTY.

**Files:**
- Modify: `.jumpcode/bin/jumpcode` (add `cmd_fleet`, register subparser in `build_parser`, dispatch in `main`)

**Step 1: Add a render helper + `cmd_fleet` (json/once only for now)**

```python
_FLEET_GLYPH = {"active": "●", "idle": "◐", "error": "⚠", "past": "○"}
_FLEET_ORDER = {"active": 0, "idle": 1, "error": 2, "past": 3}


def _fleet_line(row: Dict[str, Any]) -> str:
    g = _FLEET_GLYPH.get(row["status"], "?")
    live = sum(1 for a in row["agents"] if a["alive"])
    total = len(row["agents"])
    panes = f"{live}/{total} panes" if total else "—"
    last = _age_str(row["last_dispatch"]) if row["last_dispatch"] else "—"
    note = ""
    if row["status"] == "error":
        note = "config!" if not row["config_ok"] else f"{row['stale_open_loops']} silent loop(s)"
    return f"{g}  {row['workspace']:<14} {row['status']:<7} {panes:<12} last {last:<7} {note}"


def _fleet_sorted(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(rows, key=lambda r: (_FLEET_ORDER.get(r["status"], 9),
                                       -(_age_secs(r["last_dispatch"]) or 1 << 30)))


def cmd_fleet(args: argparse.Namespace, home: Path) -> int:
    if args.json:
        print_json({"workspaces": _fleet_sorted(gather_fleet(home))})
        return 0
    if args.once:
        rows = _fleet_sorted(gather_fleet(home))
        print(f"JUMPCODE FLEET   {len(rows)} workspaces")
        for r in rows:
            print("  " + _fleet_line(r))
        return 0
    return _fleet_tui(home, args)  # implemented in Task 5
```

For now stub `_fleet_tui` to call the `--once` path so the module imports:

```python
def _fleet_tui(home: Path, args: argparse.Namespace) -> int:
    rows = _fleet_sorted(gather_fleet(home))
    for r in rows:
        print(_fleet_line(r))
    return 0
```

**Step 2: Register the subparser** in `build_parser` (mirror how `health` is registered — grep `add_parser("health"` or the health block):

```python
    fleet = sub.add_parser("fleet", help="dashboard of all workspaces + statuses")
    fleet.add_argument("--json", action="store_true", help="machine-readable dump")
    fleet.add_argument("--once", action="store_true", help="print once, no live loop")
    fleet.add_argument("--interval", type=int, default=30, help="TUI refresh seconds")
```

**Step 3: Dispatch in `main`** — find where commands route (grep `cmd_health(` in the dispatch section) and add:

```python
    if args.cmd == "fleet":
        return cmd_fleet(args, home)
```

**Step 4: Verify `--json` works live**

Run: `./.jumpcode/bin/jumpcode fleet --json | python3 -m json.tool | head -30`
(The `fleet` bin wrapper doesn't exist yet — call through `jumpcode` directly for now.)
Expected: JSON with a `workspaces` array, one entry per session file, each with a `status`. Eyeball that webapp/obs read plausibly and seo/heatmap read `past`.

**Step 5: Verify `--once`**

Run: `./.jumpcode/bin/jumpcode fleet --once`
Expected: one glyph line per workspace, sorted active→idle→error→past.

**Step 6: Commit**

```bash
cd .jumpcode && git add bin/jumpcode && git commit -m "feat: fleet command with --json and --once seams"
```

---

### Task 5: Curses live TUI

The render loop: alt-screen, repaint every `--interval` seconds, `r` refresh now, `q` quit. Thin and untested (standard for curses).

**Files:**
- Modify: `.jumpcode/bin/jumpcode` (replace the `_fleet_tui` stub; add `import curses` at top with the other stdlib imports)

**Step 1: Implement `_fleet_tui`**

```python
def _fleet_tui(home: Path, args: argparse.Namespace) -> int:
    import curses

    def _run(stdscr):
        curses.curs_set(0)
        stdscr.nodelay(True)
        if curses.has_colors():
            curses.start_color(); curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)   # active
            curses.init_pair(2, curses.COLOR_YELLOW, -1)  # idle
            curses.init_pair(3, curses.COLOR_RED, -1)     # error
            curses.init_pair(4, curses.COLOR_WHITE, -1)   # past (dim)
        pair = {"active": 1, "idle": 2, "error": 3, "past": 4}
        last_paint = 0.0
        rows = []
        while True:
            now = __import__("time").monotonic()
            if now - last_paint >= args.interval or last_paint == 0.0:
                rows = _fleet_sorted(gather_fleet(home))
                last_paint = now
                stdscr.erase()
                header = (f"JUMPCODE FLEET   {len(rows)} workspaces · "
                          f"{args.interval}s · r refresh · q quit")
                stdscr.addstr(0, 0, header[:curses.COLS - 1], curses.A_BOLD)
                for i, r in enumerate(rows, start=2):
                    attr = curses.color_pair(pair.get(r["status"], 4))
                    if r["status"] == "past":
                        attr |= curses.A_DIM
                    line = _fleet_line(r)[:curses.COLS - 1]
                    try:
                        stdscr.addstr(i, 0, line, attr)
                    except curses.error:
                        pass  # bottom-right cell write can raise; ignore
                stdscr.refresh()
            ch = stdscr.getch()
            if ch in (ord("q"), ord("Q")):
                return 0
            if ch in (ord("r"), ord("R")):
                last_paint = 0.0  # force immediate repaint next loop
            __import__("time").sleep(0.2)  # keep key latency low without busy-spin

    return curses.wrapper(_run)
```

(Use a top-level `import curses` instead of the inline import if the file's import style prefers it; either works. The `__import__("time")` calls can be a top-level `import time` — match the file's existing import block.)

**Step 2: Manual smoke test (interactive — you run it)**

Run: `./.jumpcode/bin/jumpcode fleet`
Expected: full-screen table, color by status, header line. Press `r` → repaints. Press `q` → clean exit back to shell with terminal restored. Confirm no traceback and the cursor/echo are normal afterward.

**Step 3: Confirm non-TTY safety**

Run: `./.jumpcode/bin/jumpcode fleet --once | cat`
Expected: plain text, no curses error (the `--once` path never touches curses).

**Step 4: Commit**

```bash
cd .jumpcode && git add bin/jumpcode && git commit -m "feat: curses live TUI for fleet dashboard"
```

---

### Task 6: `./.jumpcode/bin/fleet` wrapper + docs

Match the house pattern (every command has a thin bin wrapper) and document it.

**Files:**
- Create: `.jumpcode/bin/fleet`
- Modify: `.jumpcode/INSTRUCTIONS.md` (commands list), `.jumpcode/README.md` (commands), root `CLAUDE.md` (Commands block)

**Step 1: Create the wrapper** (copy the exact shape of `bin/health`):

```bash
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$DIR/jumpcode" fleet "$@"
```

**Step 2: Make it executable**

Run: `chmod +x .jumpcode/bin/fleet`

**Step 3: Verify the wrapper**

Run: `./.jumpcode/bin/fleet --once`
Expected: same output as `jumpcode fleet --once`.

**Step 4: Document** — add one line to each commands list, e.g. in `CLAUDE.md`:

```
./.jumpcode/bin/fleet                  # live dashboard of all workspaces + statuses (--json / --once)
```

Add matching lines to `INSTRUCTIONS.md` and `README.md` command sections.

**Step 5: Run the full suite**

Run: `python3 -m unittest discover -s .jumpcode/tests`
Expected: all PASS (health unchanged, fleet classifier + config-check green).

**Step 6: Commit**

```bash
cd .jumpcode && git add bin/fleet INSTRUCTIONS.md README.md ../CLAUDE.md && git commit -m "feat: fleet bin wrapper + docs"
```

---

## Done criteria

- `./.jumpcode/bin/fleet` shows all 8 workspaces, each classified active/idle/past/error.
- `fleet --json` and `fleet --once` work without a TTY.
- `r` refreshes, `q` exits cleanly, 30s auto-refresh.
- `python3 -m unittest discover -s .jumpcode/tests` all green, including unchanged `test_health.py`.
