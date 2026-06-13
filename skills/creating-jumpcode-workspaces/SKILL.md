---
name: creating-jumpcode-workspaces
description: Use when creating, spinning up, or firing up a new jumpcode workspace / agent team for a repo — guides the Goal Contract (define purpose first), the worktree + workspace.json + role overlay, validation, launch, and the strongly-recommended /goal kickoff.
---

# Creating a Jumpcode Workspace

A jumpcode workspace is a dedicated, visible team of agents (one orchestrator + team leads in
tmux panes) bound to **one repo** and **one clearly defined goal**. This skill is the
operational procedure for standing one up correctly the first time.

Authoritative background, read alongside this skill:
- `$JUMPCODE_HOME/README.md` → **"Creating a workspace: the Goal Contract"** (the contract this
  skill implements; 🔒 = hard gate).
- `$JUMPCODE_HOME/INSTRUCTIONS.md` (commands, session scoping, reporting).
- `$JUMPCODE_HOME/CLAUDE.md` house rules (Linear team policy; commit/push only when asked).

<HARD-GATE>
Define the goal and gather repo context BEFORE creating anything. Charters and the roster all
depend on the mission — launching on a vague or wrongly-scoped goal wastes the whole team's work
in the wrong direction. Do not create the worktree until the contract's 🔒 fields are resolved.
</HARD-GATE>

## Checklist

Create a TodoWrite item per step and do them in order.

1. **Resolve the Goal Contract** (see README). The 🔒 hard gates you cannot launch without:
   - **Goal** — one or two sentences: what this workspace achieves.
   - **Final state** — an observable/verifiable done-condition (a test passes, a metric hits N,
     a feature behaves like Y).
   - **Scope forks** — the decisive ambiguous choices only the human can make. Ask these.
   - **Repo** — the git repo this binds to.
   Derive the rest (slug, base branch=`staging` unless the repo has none, roster) and confirm
   only where genuinely in doubt. Convert any relative dates to absolute when you record them.

2. **Gather repo context** — inspect the target repo enough to scope the work and the roster
   (stack, existing relevant tooling, test command). This is YOUR research, not the team's; keep
   it to what the contract needs. (For the work itself, the team does the deep dive after launch.)

3. **Pick the system of record.** Default is **Linear** (team given by the human; never the
   personal `SEA` team; never auto-create a team). A workspace may instead use **GitHub issues**
   (`gh`) — if so, it MUST be enforced by a thin orchestrator overlay (step 5), because the
   launcher's init prompt and the central charter both assume Linear.

4. **Offer and STRONGLY RECOMMEND the `/goal` kickoff.** When creating any workspace, present the
   `/goal` command as the preferred way to start the orchestrator and strongly recommend it (see
   "The /goal kickoff" below). It gives the orchestrator a clean decompose → file-issues →
   dispatch → integrate → review-gate loop from a single mission string.

5. **Create the worktree** off the base branch, isolated from other teams:
   ```bash
   git -C <repo> worktree add <repo>/.worktrees/<slug> -b <slug> <base-branch>
   mkdir -p <repo>/.worktrees/<slug>/.jumpcode/roles   # .jumpcode is git-excluded in the repo
   ```

6. **Write `workspaces/<slug>/workspace.json`** (settings only — there is no roster here):
   ```json
   {
     "title": "<Human-facing goal label for the orchestrator pane border>",
     "_comment": "<durable description: goal, final state, repo+worktree, session, system of record, team>",
     "workspace_root": "<repo>/.worktrees/<slug>",
     "role_runtimes": { "orchestrator": "claude", "backend-lead": "claude", "...": "claude" }
   }
   ```
   `role_runtimes` keys must be the central base set you keep plus any overlay leads. Default
   runtime `claude` (a lead can be `codex`, but codex is laggy for jumpcode).

7. **Add role overlays** in `<worktree>/.jumpcode/roles/` (overlay overrides central by role id;
   it can ADD or OVERRIDE but cannot subtract a central basic). Two common cases:
   - **System-of-record override** → a *thin* `🧭 orchestrator.md` that says "follow the central
     charter at `$JUMPCODE_HOME/roles/🧭 orchestrator.md` EXCEPT: system of record is GitHub issues
     in `<owner/repo>` via `gh`, not Linear; ignore the Linear line in the launch prompt." Add any
     other per-workspace gates here (e.g. an API-key pause gate). Keep it thin and reference the
     central charter — do not duplicate it.
   - **Specialist lead** → a full charter `<emoji> <id>-lead.md` for a domain the base set doesn't
     cover (see seo's `content-lead`, ambassador's `integrity-lead`).

8. **Validate before launching:**
   ```bash
   ./.jumpcode/bin/jumpcode roles discover --workspace <slug>
   ```
   Confirm: workspace_root is the worktree, the orchestrator resolves to your overlay (if any),
   every expected lead appears, and the protocol resolves. Fix mismatches before launch.

9. **Launch the grid:**
   ```bash
   JUMPCODE_WORKSPACE=<slug> ./.jumpcode/bin/start-webapp
   ```
   Session is `macbook-<slug>`; an iTerm window opens to attach. NOTE: `start-webapp` needs
   bash 4+ (`declare -A`); if `env bash` resolves to macOS's 3.2, run it with
   `/opt/homebrew/bin/bash ./.jumpcode/bin/start-webapp`.

10. **Kick off with `/goal`** (preferred). Wait for the orchestrator pane to finish bootstrapping
    and go idle (it announces it is standing by), then send the mission:
    ```bash
    tmux send-keys -t <orchestrator-pane-id> -- "/goal <full mission>"
    sleep 0.5; tmux send-keys -t <orchestrator-pane-id> Enter
    ```
    Find the orchestrator pane id from the launcher's printed "Roles panes" list (the
    `orchestrator` one), or `tmux list-panes -t macbook-<slug>:roles`. Peek with
    `tmux capture-pane -p -t <pane>` to confirm it accepted the goal. Encode the FULL flow in the
    mission (audit → research via context7 → design → implement → API-key pause gate → tests →
    review gate) so the orchestrator self-drives.

11. **Record memory** — a `project`-type memory for the new workspace (goal, repo+worktree,
    session, system of record, roster) and update the memory index.

## The /goal kickoff

`/goal <mission>` is a global Claude command (`~/.claude/commands/goal.md`; canonical copy shipped
at `$JUMPCODE_HOME/commands/goal.md`). Typed into an orchestrator pane, it runs the orchestrator's
operating loop: confirm roster via `health`, restate + decompose the mission, file one tracking
issue per workstream in the workspace's system of record (it checks the charter to know GitHub vs
Linear), dispatch the right leads, integrate + enforce the review gate, report to the human.

Ensure it is installed before launch:
```bash
[ -f ~/.claude/commands/goal.md ] || cp "$JUMPCODE_HOME/commands/goal.md" ~/.claude/commands/goal.md
```

This is the **preferred and strongly recommended** way to start a workspace's orchestrator —
offer it every time. The alternative (typing a freeform directive) loses the structured loop.

## Don'ts

- Don't create a workspace on a vague goal, or skip repo-context gathering (the hard gate).
- Don't file work in the personal `SEA` Linear team, and never auto-create a Linear team.
- Don't push the `.jumpcode` repo automatically — commit/push only when the human asks (the repo
  has a public remote).
- Don't duplicate the central orchestrator charter in an overlay — reference it and state deltas.
