import importlib.util
import json
import tempfile
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


if __name__ == "__main__":
    unittest.main()
