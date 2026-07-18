# Example Workspace

A reference workspace record for Jumpcode. `workspace.json` here is a lightweight,
human-readable note of a goal's binding — repo, worktree, tracker, and the team of specialists
the orchestrator will spawn. **No engine reads it**; there is no launcher. For canonical terms
see [`../../CONTEXT.md`](../../CONTEXT.md); for the decisions see
[`../../docs/adr/`](../../docs/adr/).

> Real workspaces are **not** committed to this repo — only this example is. A real workspace's
> worktree lives in its own project repo; the agent pack is installed into that worktree's
> `.claude/agents/` (see below). This repo ships the pack plus this example record.

## How the team is chosen

There is no discovery engine. The team is simply the subset of the `.claude/agents/*.md`
specialists the orchestrator decides to spawn for the goal:

- `backend-lead`, `frontend-lead`, `devops-lead` — coding leads (no browser).
- `code-reviewer` — independent merge-gate; **owns browser automation**.
- `qa-tester` — independent verification; **owns browser automation**.

`workspace.json`'s `team` field just records which ones this goal expects; the orchestrator
spawns them as work arises. The orchestrator itself is your main Claude Code session, governed by
[`../../roles/orchestrator.md`](../../roles/orchestrator.md).

## Topology

```text
You (Sean)
  -> orchestrator (your main session)   the only relay
      -> specialists                    subagents spawned via the Agent tool
```

Hub-and-spoke (ADR 0001), enforced by the substrate: subagents return to the orchestrator and
cannot address each other — a specialist asks the orchestrator to relay. Projects and tasks live
in **GitHub Issues** (ADR 0006); Jumpcode keeps no local task state.

## Launch

```bash
# 1. install the pack into the target worktree
../../bin/jumpcode-install --project ~/Desktop/<repo>/.worktrees/<slug>

# 2. start Claude Code in that worktree — this session is the orchestrator
cd ~/Desktop/<repo>/.worktrees/<slug> && claude

# 3. have it read .claude/agents/jumpcode/orchestrator.md, then hand it the goal
```

A fresh session reorients from GitHub Issues + git state (ADR 0004/0008); `claude --resume`
restores a prior session when its own reasoning is worth keeping.
