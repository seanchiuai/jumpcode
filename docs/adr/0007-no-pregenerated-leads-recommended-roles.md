# No Pre-Generated Leads — Central Roles Are Recommendations

> **SUPERSEDED (2026-07-17) by [ADR 0008](0008-native-claude-code-orchestration.md).** The
> `discover_roles` engine, `enabled_roles`, `role_runtimes`, and overlay-charter mechanics are
> retired. The *spirit* is now native and stronger: a team is simply the subset of
> `.claude/agents/*.md` specialists the orchestrator chooses to spawn — nothing runs without a
> reason to. Kept for history.


Status: **Accepted** (2026-06-27). **Refines the role-discovery model** (the "central base set always launches" behavior described in earlier docs).

A workspace launches the **orchestrator alone** by default. There are **no pre-generated leads**. The central `roles/*.md` leads (backend / frontend / qa / devops / code-review) are *recommendations*, not a forced base set. A lead joins a team only when the workspace asks for it, from one of two opt-in sources:

- **`enabled_roles`** — a list in `workspace.json` naming which *recommended central* leads to launch.
- **Overlay charters** — any `*.md` a workspace authors in `<workspace_root>/.jumpcode/roles/` launches automatically (writing the charter is the opt-in) and overrides a central role of the same canonical id.

## Why

Not every workspace needs the full five-lead team. A define/plan workspace, a single-issue fix, or a narrow specialist team paid a tax: the engine forced every central lead into every grid, and the only escape ("remove it from the central base set") was global, not per-workspace. Treating the central set as a *library of recommendations* makes the common case (pick what the goal needs) the easy case, and makes a minimal team the natural default rather than a special configuration.

This also removes the old "the overlay cannot subtract a basic" wart: there is nothing to subtract, because nothing is added without being asked for.

## Mechanics

`discover_roles` computes the launch set as: `orchestrator` (always) ∪ every repo-local overlay role ∪ every central role named in `enabled_roles`. `enabled_roles` validates against discovered role ids; absent or `[]` ⇒ orchestrator only. `role_runtimes` keys must reference roles that actually launch.

## Consequences

- **Existing workspaces must declare `enabled_roles`.** A workspace whose `role_runtimes` names leads but omits `enabled_roles` now **fails discovery** (the runtimes reference non-launched roles). The committed `cleanup` and `jumpstudy` workspaces were migrated to `enabled_roles: [all five leads]` to preserve their teams.
- Workspace creation (the canonical `jumpcode` skill) now picks the team via `enabled_roles` + overlay charters instead of inheriting all.
- `workspace.json` settings surface is `workspace_root`, `role_runtimes`, `enabled_roles` — still no roster *prompts*.

## Related

Paired with the compaction follow-up enforcement (`recompact --message` is mandatory): a lead is never left idle after a compaction, just as a workspace is never given a lead it did not ask for. Both express the same principle — no agent runs without a reason to.
