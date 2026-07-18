"""Validate the native agent pack: frontmatter is well-formed and the browser boundary holds.

The migration (ADR 0008) replaced the custom dispatch CLI with native Claude Code subagents
defined in .claude/agents/*.md. These tests lock in the invariants that make that pack
correct — above all the *critical* rule that only the reviewer and tester own browser
automation, and the coding leads are denied it at the frontmatter level.

Pure stdlib; no external YAML dependency (frontmatter fields are simple single-line values).
"""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO / ".claude" / "agents"

# The browser MCP servers a coding lead must be denied and a reviewer/tester must own.
BROWSER_SERVERS = ("mcp__claude-in-chrome", "mcp__playwright")

CODING_LEADS = {"backend-lead", "frontend-lead", "devops-lead"}
BROWSER_OWNERS = {"code-reviewer", "qa-tester"}


def parse_frontmatter(path: Path) -> dict:
    """Return the YAML frontmatter as a dict of raw string values (single-line fields only)."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, f"{path.name}: missing --- frontmatter block"
    body = m.group(1)
    fields, key = {}, None
    for line in body.splitlines():
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:", line):
            key, _, val = line.partition(":")
            key = key.strip()
            fields[key] = val.strip()
        elif key is not None and line.strip():
            # continuation of a folded (>-) or wrapped value
            fields[key] += " " + line.strip()
    return fields


def agent_files():
    return sorted(AGENTS_DIR.glob("*.md"))


class TestAgentPack(unittest.TestCase):
    def test_agents_dir_exists_with_expected_roster(self):
        self.assertTrue(AGENTS_DIR.is_dir(), ".claude/agents/ must exist")
        names = {p.stem for p in agent_files()}
        self.assertEqual(
            names,
            CODING_LEADS | BROWSER_OWNERS,
            "agent roster drifted from the five expected specialists",
        )

    def test_every_agent_has_required_frontmatter(self):
        for path in agent_files():
            fm = parse_frontmatter(path)
            self.assertIn("name", fm, f"{path.name}: name is required")
            self.assertIn("description", fm, f"{path.name}: description is required")
            self.assertEqual(
                fm["name"], path.stem,
                f"{path.name}: frontmatter name must match filename stem",
            )

    def test_coding_leads_are_denied_browser(self):
        for path in agent_files():
            fm = parse_frontmatter(path)
            if fm["name"] not in CODING_LEADS:
                continue
            denied = fm.get("disallowedTools", "")
            for server in BROWSER_SERVERS:
                self.assertIn(
                    server, denied,
                    f"{path.name}: coding lead must deny {server} in disallowedTools",
                )
            # A lead must not also grant browser via an allowlist.
            self.assertNotIn(
                "mcp__claude-in-chrome", fm.get("tools", ""),
                f"{path.name}: coding lead must not grant browser tools",
            )

    def test_reviewer_and_tester_own_browser(self):
        for path in agent_files():
            fm = parse_frontmatter(path)
            if fm["name"] not in BROWSER_OWNERS:
                continue
            tools = fm.get("tools", "")
            self.assertIn(
                "mcp__claude-in-chrome__*", tools,
                f"{path.name}: browser owner must grant Claude in Chrome",
            )
            self.assertIn(
                "mcp__playwright", tools,
                f"{path.name}: browser owner must grant Playwright",
            )
            # And they must never be denied the browser they own.
            self.assertNotIn(
                "mcp__claude-in-chrome", fm.get("disallowedTools", ""),
                f"{path.name}: browser owner must not deny its own browser tools",
            )

    def test_exactly_two_agents_own_browser(self):
        owners = set()
        for path in agent_files():
            fm = parse_frontmatter(path)
            if "mcp__claude-in-chrome__*" in fm.get("tools", ""):
                owners.add(fm["name"])
        self.assertEqual(
            owners, BROWSER_OWNERS,
            "browser automation must be owned by exactly the reviewer and tester",
        )


if __name__ == "__main__":
    unittest.main()
