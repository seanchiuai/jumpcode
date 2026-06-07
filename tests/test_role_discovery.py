import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COCKPIT = ROOT / "bin" / "cockpit"


def write(path, text="prompt"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class RoleDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.home = self.tmp / "cockpit"
        self.workspace = "webapp"
        self.workspace_root = self.tmp / "repo"
        self.central_roles = self.home / "roles"
        self.local_roles = self.workspace_root / ".agent-cockpit" / "roles"
        (self.home / "workspaces" / self.workspace).mkdir(parents=True)
        (self.home / "workspaces" / self.workspace / "workspace.json").write_text(
            json.dumps({"workspace_root": str(self.workspace_root), "role_runtimes": {}}),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def run_discover(self, check=True):
        env = os.environ.copy()
        env["COCKPIT_HOME"] = str(self.home)
        result = subprocess.run(
            [sys.executable, str(COCKPIT), "roles", "discover", "--workspace", self.workspace, "--json"],
            cwd=self.tmp,
            env=env,
            text=True,
            capture_output=True,
        )
        if check and result.returncode != 0:
            raise AssertionError(f"discover failed\nstdout={result.stdout}\nstderr={result.stderr}")
        return result

    def seed_minimal(self):
        write(self.central_roles / "_PROTOCOL.md", "central protocol")
        write(self.central_roles / "🧭 orchestrator.md", "orchestrator")

    def roles_by_id(self):
        return {r["id"]: r for r in json.loads(self.run_discover().stdout)["roles"]}

    def test_emoji_and_plain_filenames_parse_to_canonical_ids(self):
        self.seed_minimal()
        write(self.central_roles / "🎨 frontend-lead.md")
        write(self.central_roles / "backend-lead.md")
        roles = self.roles_by_id()
        self.assertEqual(roles["frontend-lead"]["display"], "🎨 frontend-lead")
        self.assertEqual(roles["backend-lead"]["display"], "backend-lead")
        self.assertEqual(roles["orchestrator"]["kind"], "orchestrator")
        self.assertEqual(roles["frontend-lead"]["kind"], "lead")

    def test_duplicate_id_failure_within_source(self):
        self.seed_minimal()
        write(self.central_roles / "🎨 frontend-lead.md")
        write(self.central_roles / "frontend-lead.md")
        r = self.run_discover(check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("duplicate role id 'frontend-lead'", r.stderr)

    def test_invalid_id_failure(self):
        self.seed_minimal()
        write(self.central_roles / "Bad_Role.md")
        r = self.run_discover(check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("invalid role id", r.stderr)

    def test_missing_orchestrator_failure(self):
        write(self.central_roles / "_PROTOCOL.md", "central protocol")
        write(self.central_roles / "backend-lead.md")
        r = self.run_discover(check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("missing required role", r.stderr)

    def test_missing_protocol_failure(self):
        write(self.central_roles / "🧭 orchestrator.md")
        r = self.run_discover(check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("missing shared protocol", r.stderr)

    def test_repo_local_overlays_central_by_id(self):
        self.seed_minimal()
        write(self.central_roles / "🎨 frontend-lead.md", "central frontend")
        write(self.local_roles / "frontend-lead.md", "local frontend")
        roles = self.roles_by_id()
        self.assertEqual(Path(roles["frontend-lead"]["prompt"]), (self.local_roles / "frontend-lead.md").resolve())
        self.assertEqual(roles["frontend-lead"]["display"], "frontend-lead")

    def test_central_protocol_fallback_when_repo_local_absent(self):
        self.seed_minimal()
        write(self.local_roles / "backend-lead.md")
        payload = json.loads(self.run_discover().stdout)
        self.assertEqual(Path(payload["protocol"]), (self.central_roles / "_PROTOCOL.md").resolve())

    def test_repo_local_protocol_overrides_central_when_present(self):
        self.seed_minimal()
        write(self.local_roles / "_PROTOCOL.md", "local protocol")
        payload = json.loads(self.run_discover().stdout)
        self.assertEqual(Path(payload["protocol"]), (self.local_roles / "_PROTOCOL.md").resolve())

    def test_runtime_override_and_unknown_runtime_failure(self):
        self.seed_minimal()
        write(self.central_roles / "backend-lead.md")
        settings = self.home / "workspaces" / self.workspace / "workspace.json"
        settings.write_text(json.dumps({
            "workspace_root": str(self.workspace_root),
            "role_runtimes": {"backend-lead": "codex"},
        }), encoding="utf-8")
        roles = self.roles_by_id()
        self.assertEqual(roles["backend-lead"]["runtime"], "codex")

        settings.write_text(json.dumps({
            "workspace_root": str(self.workspace_root),
            "role_runtimes": {"backend-lead": "bogus"},
        }), encoding="utf-8")
        r = self.run_discover(check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unknown runtime 'bogus'", r.stderr)

        settings.write_text(json.dumps({
            "workspace_root": str(self.workspace_root),
            "role_runtimes": {"missing-lead": "bogus"},
        }), encoding="utf-8")
        r = self.run_discover(check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unknown runtime 'bogus'", r.stderr)

    def test_runtime_override_unknown_role_failure(self):
        self.seed_minimal()
        settings = self.home / "workspaces" / self.workspace / "workspace.json"
        settings.write_text(json.dumps({
            "workspace_root": str(self.workspace_root),
            "role_runtimes": {"missing-lead": "codex"},
        }), encoding="utf-8")
        r = self.run_discover(check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("role_runtimes references unknown role 'missing-lead'", r.stderr)


if __name__ == "__main__":
    unittest.main()
