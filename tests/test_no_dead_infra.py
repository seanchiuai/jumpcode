"""Guard against contradictory compatibility claims after the ADR-0008 migration.

The retired infrastructure (the dispatch CLI, tmux wake, start-webapp, revive, recompact,
the JSONL dispatch log) is gone. The operator-facing docs and the agent pack must not tell a
user to run those commands. Historical docs (docs/plans/*, AUDIT.md) and the migration ADR
itself are allowed to *describe* the retired mechanics as history — they are excluded here.
"""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Operator-facing surfaces that must describe only the native system.
OPERATOR_DOCS = [
    "README.md",
    "CONTEXT.md",
    "INSTRUCTIONS.md",
    "HANDOFF.md",
    "roles/orchestrator.md",
    "roles/_PROTOCOL.md",
]

# Command-shaped tokens from the retired CLI. We match these as *commands*, not bare words,
# to avoid tripping on prose that merely mentions the old model.
FORBIDDEN_COMMAND_TOKENS = [
    "dispatch send",
    "dispatch inbox",
    "bin/dispatch",
    "bin/start-webapp",
    "start-webapp",
    "bin/revive",
    "bin/recompact",
    "bin/health",
    "bin/peek",
    "bin/fleet",
    "dispatches.jsonl",
    "@jumpcode_role",
    "enabled_roles",
    "role_runtimes",
]


class TestNoDeadInfra(unittest.TestCase):
    def test_operator_docs_have_no_retired_commands(self):
        for rel in OPERATOR_DOCS:
            path = REPO / rel
            self.assertTrue(path.exists(), f"expected operator doc missing: {rel}")
            text = path.read_text(encoding="utf-8")
            for token in FORBIDDEN_COMMAND_TOKENS:
                self.assertNotIn(
                    token, text,
                    f"{rel} still references retired infrastructure token '{token}'",
                )

    def test_agent_pack_has_no_retired_commands(self):
        for path in (REPO / ".claude" / "agents").glob("*.md"):
            text = path.read_text(encoding="utf-8")
            for token in ("dispatch send", "bin/dispatch", "@jumpcode_role"):
                self.assertNotIn(
                    token, text,
                    f"{path.name} still references retired infrastructure token '{token}'",
                )

    def test_bin_holds_only_the_installer(self):
        bin_dir = REPO / "bin"
        scripts = sorted(p.name for p in bin_dir.iterdir() if p.is_file())
        self.assertEqual(
            scripts, ["jumpcode-install"],
            "bin/ must contain only the adoption helper; the retired CLI is removed",
        )

    def test_retired_cli_source_is_gone(self):
        for gone in ("bin/jumpcode", "bin/dispatch", "bin/start-webapp", "bin/revive"):
            self.assertFalse(
                (REPO / gone).exists(), f"retired script still present: {gone}"
            )


if __name__ == "__main__":
    unittest.main()
