"""The adoption helper must deliver the pack where Claude Code discovers it (ADR 0008)."""
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INSTALLER = REPO / "bin" / "jumpcode-install"


class TestInstaller(unittest.TestCase):
    def test_installer_exists_and_is_executable(self):
        self.assertTrue(INSTALLER.exists(), "bin/jumpcode-install must exist")
        mode = INSTALLER.stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR, "installer must be executable")

    def test_installer_has_valid_bash_syntax(self):
        r = subprocess.run(["bash", "-n", str(INSTALLER)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_project_install_copies_the_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(
                [str(INSTALLER), "--project", tmp],
                capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            agents = Path(tmp) / ".claude" / "agents"
            installed = {p.stem for p in agents.glob("*.md")}
            self.assertEqual(
                installed,
                {"backend-lead", "frontend-lead", "devops-lead", "code-reviewer", "qa-tester"},
                "all five specialist agents must be delivered",
            )
            # Orchestrator charter + protocol land next to the agents for a fresh session.
            self.assertTrue((agents / "jumpcode" / "orchestrator.md").exists())
            self.assertTrue((agents / "jumpcode" / "_PROTOCOL.md").exists())

    def test_requires_a_target(self):
        r = subprocess.run([str(INSTALLER)], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0, "installer must refuse with no target")


if __name__ == "__main__":
    unittest.main()
