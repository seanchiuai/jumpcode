# Multi-runtime Support (add Codex) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let any jumpcode role run **Codex** instead of Claude Code, chosen per-role in `workspace.json`, without changing the dispatch/wake/Linear layers.

**Architecture:** Add a per-role `role_runtimes` map (default `claude`) read by the launcher; an inline, data-shaped runtime descriptor that maps a runtime name → `{program, markers}`; tag each pane with a `@jumpcode_runtime` tmux option (mirroring `@jumpcode_role`); and make `pane_state()` runtime-keyed so health classifies Codex panes correctly. Everything already runtime-agnostic (dispatch log, `wake_pane`, `@jumpcode_role`, hub-and-spoke) is untouched.

**Tech Stack:** Python 3 stdlib (`bin/jumpcode`), bash (`bin/start-webapp`), tmux, `unittest`. Design doc: `docs/plans/2026-06-07-codex-runtime-design.md`.

**Conventions you must follow (read before starting):**
- Tests run with `python3 -m unittest discover -s tests -v` from `.jumpcode/` (there is no pytest; `bin/jumpcode` has no `.py` extension, so tests import it via `SourceFileLoader` — see any `tests/test_*.py` header).
- Git is **local-only**, scoped to `.jumpcode/`. Never push. Commit messages end with the `Co-Authored-By` trailer used in `git log`.
- Run every command from `/Users/seanchiu/Desktop/workspace-macbook/.jumpcode`.
- The launcher's live tmux session is `macbook-webapp`. **Never kill or relaunch it** as part of a test — all headless launcher tests use a throwaway session name and `CLAUDE_BIN=cat`/`CODEX_BIN=cat` (the established geometry-test pattern).

---

### Task 1: Make `pane_state()` runtime-keyed

**Files:**
- Modify: `bin/jumpcode:286-298` (the `_BUSY_MARKER`/`_WAITING_MARKERS` globals and `pane_state`)
- Test: `tests/test_health.py:14-25` (extend `PaneStateTests`)

**Step 1: Write the failing tests**

Add to `tests/test_health.py` inside `PaneStateTests`:

```python
    def test_claude_default_runtime_unchanged(self):
        # existing three tests already cover claude; this pins the default arg explicitly
        screen = "✳ Crunching… (26s · esc to interrupt)\n❯ \n"
        self.assertEqual(jumpcode.pane_state(screen, "claude"), "working")

    def test_codex_trust_prompt_is_waiting(self):
        # captured live from codex 0.137.0-alpha.4 on 2026-06-07
        screen = ("  Do you trust the contents of this directory?\n"
                  "› 1. Yes, continue\n  2. No, quit\n  Press enter to continue\n")
        self.assertEqual(jumpcode.pane_state(screen, "codex"), "waiting")

    def test_codex_idle_composer(self):
        # captured live: empty composer shows the greyed placeholder
        screen = ("╭─────╮\n│ >_ OpenAI Codex (v0.137.0-alpha.4) │\n╰─────╯\n"
                  "› Explain this codebase\n  gpt-5.5 high · /tmp/x\n")
        self.assertEqual(jumpcode.pane_state(screen, "codex"), "idle")

    def test_codex_busy_marker(self):
        # TO-VERIFY live (design doc): web sources show "Working (… esc to interrupt)".
        # If the live launch (Task 6) shows a different string, update _RUNTIME_MARKERS["codex"]["busy"].
        screen = "Working (1m 4s • esc to interrupt)\n› \n"
        self.assertEqual(jumpcode.pane_state(screen, "codex"), "working")

    def test_unknown_runtime_falls_back_to_claude(self):
        screen = "Do you want to proceed?\n❯ 1. Yes\n  2. No\n"
        self.assertEqual(jumpcode.pane_state(screen, "gemini"), "waiting")
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_health -v`
Expected: the new tests FAIL — `pane_state()` currently takes one argument, so `pane_state(screen, "codex")` raises `TypeError: pane_state() takes 1 positional argument but 2 were given`.

**Step 3: Implement — replace the two marker globals + `pane_state` with a per-runtime table**

Replace `bin/jumpcode:286-298` with:

```python
# Per-runtime status-line markers. Health reads a pane's @jumpcode_runtime to pick the
# right set. Claude and Codex overlap heavily (both surface "esc to interrupt" while
# working and numbered "1. Yes" approval prompts), but keep them separate so future
# divergence — or a third runtime — is a data edit, not a code change.
_RUNTIME_MARKERS = {
    "claude": {
        "busy": ("esc to interrupt",),
        "waiting": ("Do you want", "❯ 1.", "1. Yes", "Allow this"),
    },
    "codex": {
        # busy ("Working … esc to interrupt") is TO-VERIFY on 0.137.0-alpha.4 (see design doc).
        "busy": ("esc to interrupt",),
        "waiting": ("Do you trust", "1. Yes", "› 1.", "Allow command"),
    },
}


def pane_state(capture_text: str, runtime: str = "claude") -> str:
    """Classify a captured agent pane as 'working' | 'waiting' | 'idle' for its runtime.

    An unknown/empty runtime falls back to the claude marker set (the markers overlap, so
    this is safe and keeps health useful even if @jumpcode_runtime was never set).
    """
    markers = _RUNTIME_MARKERS.get(runtime) or _RUNTIME_MARKERS["claude"]
    if any(m in capture_text for m in markers["busy"]):
        return "working"
    if any(m in capture_text for m in markers["waiting"]):
        return "waiting"
    return "idle"
```

**Step 4: Run the full suite**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS — all new health tests green, and the three pre-existing `PaneStateTests` (which call `pane_state(screen)` with no runtime) still pass via the `runtime="claude"` default.

**Step 5: Commit**

```bash
git add bin/jumpcode tests/test_health.py
git commit -m "feat(health): runtime-keyed pane_state (claude|codex marker sets)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Wire `@jumpcode_runtime` into `cmd_health`

**Files:**
- Modify: `bin/jumpcode:355-382` (the `list-panes` format string in `cmd_health` and the per-line parse loop)

**Step 1: Extend the tmux format string**

In `cmd_health`, change the `list-panes -F` format (currently `bin/jumpcode:359-360`) from:

```python
                ["tmux", "list-panes", "-t", session, "-F",
                 "#{pane_id}\t#{@jumpcode_role}\t#{pane_current_command}\t#{pane_dead}"],
```

to add a fifth field:

```python
                ["tmux", "list-panes", "-t", session, "-F",
                 "#{pane_id}\t#{@jumpcode_role}\t#{pane_current_command}\t#{pane_dead}\t#{@jumpcode_runtime}"],
```

**Step 2: Parse the runtime and pass it through**

In the parse loop (`bin/jumpcode:368-382`), the current guard `if len(parts) < 4: continue` stays. Read the optional fifth field and pass it to `pane_state`:

```python
    for line in panes_text.splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        pane_id, role, cmd, dead = parts[0], parts[1].strip(), parts[2], parts[3]
        runtime = parts[4].strip() if len(parts) >= 5 else ""
        if not role:
            continue
        seen_roles.add(role)
        alive = dead != "1"
        state = "stopped" if not alive else pane_state(_tmux_capture(pane_id), runtime or "claude")
        agents.append({
            "role": role, "pane": pane_id, "alive": alive, "command": cmd,
            "runtime": runtime or "claude",
            "state": state, "subagents": subs.get(role, []),
            "last_seen": last_seen.get(role),
        })
```

**Step 3: Surface runtime in the human-readable output**

In the text-output loop (`bin/jumpcode:412-416`), include the runtime so a mixed team is visible at a glance:

```python
    for a in agents:
        dot = "●" if a["alive"] else "○"
        sub = ("  subagents=" + ", ".join(a["subagents"])) if a["subagents"] else ""
        print(f"  {dot} {a['role']:<16} {a.get('runtime','claude'):<7} {a['state']:<8} "
              f"last_seen={a['last_seen'] or '-'}{sub}")
```

**Step 4: Verify no regressions + behavior on the live session**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS (this task is tmux-IO wiring; `pane_state` logic is already unit-covered in Task 1, matching the repo precedent that `cmd_health` is verified live).

Run (only if `macbook-webapp` is already running — do NOT start it for this): `./bin/health`
Expected: each row now shows a runtime column (`claude` for all current panes, since none are codex yet) and still classifies state. If the session isn't running, this prints the graceful "no jumpcode panes" message — that's fine.

**Step 5: Commit**

```bash
git add bin/jumpcode
git commit -m "feat(health): read @jumpcode_runtime per pane; show runtime column

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Read `role_runtimes` in the launcher's role emitter

**Files:**
- Modify: `workspaces/webapp/workspace.json` (add an empty `role_runtimes` to document the knob)
- Modify: `bin/start-webapp:74-99` (the lead-emitter python block + the bash array read) and `bin/start-webapp:59-72` (orchestrator block)

**Step 1: Add the knob to the webapp workspace (default unchanged behavior)**

Add a `role_runtimes` object to `workspaces/webapp/workspace.json` after `role_emojis`. Leave it empty so the default launch stays all-Claude (Codex requires Sean's prerequisites — Linear MCP, trusted dirs):

```json
  "role_emojis": {
    "orchestrator": "🧭",
    "frontend-lead": "🎨",
    "backend-lead": "🛠",
    "qa-lead": "✅",
    "devops-lead": "🚀",
    "mcp-lead": "🔌"
  },
  "role_runtimes": {}
```

(Don't forget the comma after the `role_emojis` block.)

**Step 2: Emit a runtime column from the lead-emitter python**

In `bin/start-webapp:80-98`, the embedded python prints `role\tprompt\temoji`. Add runtimes. Change the python body to:

```python
import json, sys
ws = json.load(open(sys.argv[1]))
prompts = ws.get("role_prompts", {})
emojis = ws.get("role_emojis", {})
runtimes = ws.get("role_runtimes", {})
pool = ["🧩", "📦", "🔭", "🛰", "🧪", "⚙", "📚", "🧰", "🔬", "🗂"]
order = list(prompts.keys()) + list(ws.get("default_participants", []))
seen = set()
fb = 0
for role in order:
    if role in ("hermes", "human", "orchestrator") or role in seen:
        continue
    seen.add(role)
    em = emojis.get(role)
    if not em:
        em = pool[fb % len(pool)]
        fb += 1
    rt = runtimes.get(role, "claude")
    print("%s\t%s\t%s\t%s" % (role, prompts.get(role, ".jumpcode/roles/%s.md" % role), em, rt))
```

**Step 3: Read the runtime field into a parallel bash array**

In `bin/start-webapp:76-79`, extend the arrays and the read loop:

```bash
LEAD_ROLES=(); LEAD_PROMPTS=(); LEAD_EMOJIS=(); LEAD_RUNTIMES=()
while IFS=$'\t' read -r role pf emoji runtime; do
  [[ -z "$role" ]] && continue
  LEAD_ROLES+=("$role"); LEAD_PROMPTS+=("$pf"); LEAD_EMOJIS+=("$emoji")
  LEAD_RUNTIMES+=("${runtime:-claude}")
done < <(python3 - "$WS_JSON" <<'PY'
... (the python from Step 2) ...
PY
)
```

**Step 4: Resolve the orchestrator's runtime**

After the `ORCH_EMOJI` block (`bin/start-webapp:67-72`), add an `ORCH_RUNTIME` resolver:

```bash
ORCH_RUNTIME=$(python3 - "$WS_JSON" <<'PY'
import json, sys
ws = json.load(open(sys.argv[1]))
print(ws.get("role_runtimes", {}).get("orchestrator", "claude"))
PY
)
```

**Step 5: Verify the emitter parses (headless, no panes yet)**

Run:
```bash
python3 - "workspaces/webapp/workspace.json" <<'PY'
import json
ws = json.load(open("workspaces/webapp/workspace.json"))
print("role_runtimes:", ws.get("role_runtimes"))
PY
```
Expected: `role_runtimes: {}` (valid JSON, key present).

**Step 6: Commit**

```bash
git add bin/start-webapp workspaces/webapp/workspace.json
git commit -m "feat(launcher): read per-role role_runtimes from workspace.json (default claude)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Runtime descriptor, program selection, preflight, and `@jumpcode_runtime` tagging

**Files:**
- Modify: `bin/start-webapp` — `CLAUDE_BIN` block (`:6`), preflight (`:16-19`), `agent_cmd` (`:30-43`), orchestrator launch (`:105`), lead launches (`:122-124`, `:136-138`), label loop (`:144-156`)

**Step 1: Add `CODEX_BIN` default + a runtime→program resolver**

After `bin/start-webapp:6` (`CLAUDE_BIN=...`), add:

```bash
CODEX_BIN="${CODEX_BIN:-/Applications/Codex.app/Contents/Resources/codex}"

# Runtime registry (inline, data-shaped — borrow Claude Squad's "profile" idea without a
# new config file). Maps a runtime name to the program that fills a pane. Add a third
# runtime here when one actually arrives.
runtime_program() {
  case "$1" in
    claude) printf '%s' "$CLAUDE_BIN" ;;
    codex)  printf '%s' "$CODEX_BIN" ;;
    *)      printf '' ;;   # unknown runtime
  esac
}
```

**Step 2: Make `agent_cmd` take a runtime and `exec` its program**

Replace `agent_cmd` (`bin/start-webapp:30-43`) so it picks the program by runtime (defaulting unknown → claude with a warning baked into the launched pane is overkill; instead validate in preflight, Step 3). New signature `agent_cmd <role> <prompt_file> <runtime>`:

```bash
agent_cmd() {
  local role="$1"
  local prompt_file="$2"
  local runtime="${3:-claude}"
  local program
  program="$(runtime_program "$runtime")"
  [[ -z "$program" ]] && program="$CLAUDE_BIN"   # safety net; preflight already validated
  cat <<EOF
cd "$ROOT"
export JUMPCODE_TMUX_SESSION="$SESSION"
printf '\\033]2;%s\\033\\\\' "$role"
clear
printf 'MacBook webapp jumpcode role: %s (%s)\\n' "$role" "$runtime"
printf 'Prompt file: %s\\n\\n' "$prompt_file"
printf '%s will start now. Initial instructions will be injected by tmux.\\n' "$runtime"
exec "$program"
EOF
}
```

**Step 3: Preflight — validate every runtime actually referenced by this workspace**

Replace the single Claude check (`bin/start-webapp:16-19`) with a check that runs *after* the lead/orch runtimes are known. Move this block to just after `ORCH_RUNTIME` is resolved (Task 3 Step 4) and the `LEAD_RUNTIMES` array is built (Task 3 Step 3):

```bash
# Validate the program for every runtime this workspace uses, before creating any pane.
declare -A _RT_SEEN=()
for rt in "$ORCH_RUNTIME" "${LEAD_RUNTIMES[@]:-}"; do
  [[ -z "$rt" || -n "${_RT_SEEN[$rt]:-}" ]] && continue
  _RT_SEEN[$rt]=1
  prog="$(runtime_program "$rt")"
  if [[ -z "$prog" ]]; then
    echo "unknown runtime '$rt' in role_runtimes — use 'claude' or 'codex'" >&2
    exit 1
  fi
  if ! command -v "$prog" >/dev/null 2>&1 && [[ ! -x "$prog" ]]; then
    echo "runtime '$rt' program not found/executable: $prog" >&2
    echo "  (for codex, set CODEX_BIN or reinstall; default is the app-bundled binary)" >&2
    exit 1
  fi
done
```

Delete the old `if ! command -v "$CLAUDE_BIN" ...` block at `:16-19` (this loop supersedes it). Keep the `tmux` check at `:11-14`.

**Step 4: Pass runtime to every `agent_cmd` call**

- Orchestrator (`bin/start-webapp:105`): append `"$ORCH_RUNTIME"`:
  ```bash
  ORCH=$(tmux new-session -d -P -F '#{pane_id}' -x "${JUMPCODE_COLS:-260}" -y "${JUMPCODE_ROWS:-72}" -s "$SESSION" -n roles -c "$ROOT" "$(agent_cmd orchestrator "$ORCH_PROMPT" "$ORCH_RUNTIME")")
  ```
- Column-head leads (`:122-124`): append `"${LEAD_RUNTIMES[$idx]}"`:
  ```bash
  "$(agent_cmd "${LEAD_ROLES[$idx]}" "${LEAD_PROMPTS[$idx]}" "${LEAD_RUNTIMES[$idx]}")") \
  ```
- Stacked leads (`:136-138`): append `"${LEAD_RUNTIMES[$idx]}"`:
  ```bash
  "$(agent_cmd "${LEAD_ROLES[$idx]}" "${LEAD_PROMPTS[$idx]}" "${LEAD_RUNTIMES[$idx]}")") \
  ```

**Step 5: Tag each pane with `@jumpcode_runtime`**

In the lead label loop (`bin/start-webapp:144-151`), after the `@jumpcode_role` set-option, add:

```bash
  tmux set-option -pt "$p" @jumpcode_runtime "${LEAD_RUNTIMES[$i]}"
```

For the orchestrator (`bin/start-webapp:153-156`), after its `@jumpcode_role`:

```bash
tmux set-option -pt "$ORCH" @jumpcode_runtime "$ORCH_RUNTIME"
```

**Step 6: Headless launcher test — `@jumpcode_runtime` is set per pane and unknown→fail**

Run this throwaway-session test (uses `cat` as both programs so no real agent starts; never touches `macbook-webapp`):

```bash
TESTWS=$(mktemp -d)/ws && mkdir -p "$TESTWS"
# minimal workspace with a mixed team
cat > /tmp/jumpcode-rt-test.json <<'JSON'
{ "default_participants": ["orchestrator","alpha-lead","beta-lead"],
  "role_prompts": {"orchestrator":".jumpcode/roles/🧭 orchestrator.md",
                   "alpha-lead":".jumpcode/roles/🎨 frontend-lead.md",
                   "beta-lead":".jumpcode/roles/🛠 backend-lead.md"},
  "role_emojis": {},
  "role_runtimes": {"beta-lead":"codex"} }
JSON
mkdir -p "workspaces/_rttest" && cp /tmp/jumpcode-rt-test.json "workspaces/_rttest/workspace.json"

CLAUDE_BIN=cat CODEX_BIN=cat JUMPCODE_WORKSPACE=_rttest JUMPCODE_TMUX_SESSION=jumpcode-rttest \
  JUMPCODE_OPEN_ITERM=0 JUMPCODE_CLAUDE_START_DELAY=0 ./bin/start-webapp >/dev/null 2>&1 || true
sleep 1
echo "=== @jumpcode_runtime per pane ==="
tmux list-panes -t jumpcode-rttest:roles -F '#{@jumpcode_role} -> #{@jumpcode_runtime}'
tmux kill-session -t jumpcode-rttest 2>/dev/null || true
rm -rf "workspaces/_rttest" /tmp/jumpcode-rt-test.json
```

Expected: lines including `beta-lead -> codex`, `alpha-lead -> claude`, `orchestrator -> claude`. (Before Step 5 the runtime column is blank → that's the failing state; after, it's populated.)

Then confirm the unknown-runtime guard:
```bash
# temporarily point a role at a bogus runtime and assert the launcher refuses
mkdir -p workspaces/_rttest && python3 - <<'PY'
import json,io
p="workspaces/_rttest/workspace.json"
import os; os.makedirs("workspaces/_rttest",exist_ok=True)
json.dump({"default_participants":["orchestrator","alpha-lead"],
 "role_prompts":{"orchestrator":".jumpcode/roles/🧭 orchestrator.md","alpha-lead":".jumpcode/roles/🎨 frontend-lead.md"},
 "role_emojis":{}, "role_runtimes":{"alpha-lead":"gemini"}}, open(p,"w"))
PY
CLAUDE_BIN=cat JUMPCODE_WORKSPACE=_rttest JUMPCODE_TMUX_SESSION=jumpcode-rttest2 \
  JUMPCODE_OPEN_ITERM=0 ./bin/start-webapp; echo "exit=$?"
tmux kill-session -t jumpcode-rttest2 2>/dev/null || true
rm -rf workspaces/_rttest
```
Expected: prints `unknown runtime 'gemini' ...` and `exit=1` (no session created).

**Step 7: Commit**

```bash
git add bin/start-webapp
git commit -m "feat(launcher): per-runtime program selection + preflight + @jumpcode_runtime tag

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Charter / protocol notes (subagents optional, Linear-MCP assumption)

**Files:**
- Modify: `roles/_PROTOCOL.md` (the Health & subagent self-report section)

**Step 1: Add two short notes**

In `roles/_PROTOCOL.md`, under the existing health/subagent section, append:

```markdown
### Runtime note (Claude Code vs Codex)

Leads behave identically regardless of which runtime fills their pane. Two caveats:

- **Subagents are optional.** A Codex lead may not spawn subagents the way Claude Code
  does. The `subagent:start`/`subagent:end` self-report convention is advisory — absence
  of subagents is normal, not an error.
- **Linear access depends on the runtime's MCP.** Linear is the system of record. A Codex
  lead can only read/update Linear if `~/.codex/config.toml` has a `[mcp_servers.linear]`
  entry. If yours does not, report progress via `dispatch` and let the orchestrator make
  the Linear writes.
```

**Step 2: Verify the docs render (no tooling — just read it back)**

Run: `sed -n '1,200p' roles/_PROTOCOL.md | grep -n "Runtime note"`
Expected: one match — the new heading is present.

**Step 3: Commit**

```bash
git add roles/_PROTOCOL.md
git commit -m "docs(protocol): note Codex runtime caveats (optional subagents, Linear MCP)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Live mixed-launch verification (closes the busy-marker TO-VERIFY gap)

> This task needs Sean's prerequisites in place (a runnable codex binary, and ideally
> Linear MCP + trusted dirs). It is the one task that consumes Codex quota. Do it with
> Sean present; if prerequisites aren't ready, stop and report — do not block the plan.

**Files:** none (verification only; may update `_RUNTIME_MARKERS["codex"]["busy"]` if the live busy string differs).

**Step 1: Launch a mixed team**

Temporarily set one lead to codex in the webapp workspace (or use a throwaway workspace), then launch:

```bash
# e.g. set "role_runtimes": {"backend-lead": "codex"} in workspaces/webapp/workspace.json
./bin/start-webapp
```

**Step 2: Confirm the pane runs codex and is tagged**

Run: `tmux list-panes -t macbook-webapp:roles -F '#{@jumpcode_role} #{@jumpcode_runtime} #{pane_current_command}'`
Expected: the chosen lead shows `... codex codex` (runtime tag = codex, current command = codex).

**Step 3: Drive a dispatch and read `woke`**

Run: `./bin/dispatch send --from orchestrator --to backend-lead --subject "[codex smoke] ping" "reply with: codex ack"`
Expected: JSON with `"woke": true` (verified delivery — confirms `wake_pane` C-u/type/verify/Enter works against a live Codex pane, including Enter-submission, which the spike did not test).

**Step 4: Confirm health classifies the Codex pane — and capture the real busy string**

While the Codex lead is mid-turn, run: `./bin/health`
Expected: the codex lead shows `codex working`. **Read its pane** (`tmux capture-pane -p -t <pane>`) and confirm the busy line contains `esc to interrupt`. If the actual string differs, update `_RUNTIME_MARKERS["codex"]["busy"]` in `bin/jumpcode`, re-run `python3 -m unittest tests.test_health`, and commit that fix.

When idle again, `./bin/health` should show `codex idle`; at an approval/trust prompt, `codex waiting`.

**Step 5: Confirm a round-trip**

Have the Codex lead reply via `dispatch send --from backend-lead --to orchestrator --kind report-done ...` and confirm it appears in `./bin/dispatch log`. This proves a Codex lead is a full participant in hub-and-spoke.

**Step 6: Revert the temporary config (if used) and commit any marker fix**

If `_RUNTIME_MARKERS["codex"]["busy"]` was corrected:
```bash
git add bin/jumpcode tests/test_health.py
git commit -m "fix(health): correct codex busy marker from live 0.137.0-alpha.4 capture

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
Revert any throwaway `role_runtimes` edit you don't want to keep (the default committed config stays all-claude unless Sean wants a permanent Codex lead).

---

## Done criteria

- `python3 -m unittest discover -s tests -v` is green (runtime-keyed `pane_state` covered for claude + codex + unknown-fallback).
- A mixed `role_runtimes` launches the right program per pane, tags `@jumpcode_runtime`, and refuses unknown runtimes / missing binaries at preflight.
- `./bin/health` shows a runtime column and classifies a live Codex pane (busy string confirmed from the live launch, not assumed).
- A dispatch to a Codex lead returns `woke: true` and a round-trip report-done lands in the log.
- Deferred items (event-hook state, worktree isolation, app-server transport) remain unbuilt, as designed.
