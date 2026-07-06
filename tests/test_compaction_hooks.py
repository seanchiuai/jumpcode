"""Tests for the compaction hooks that live in ~/.claude/hooks (outside this repo).

The hook scripts are global, so we load the pure functions via importlib and skip when they
are not installed (keeps the public repo's `unittest discover` green on a fresh clone). The
tmux-dependent main() glue is verified by the smoke tests in the implementation plan.
"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HOOKS = Path.home() / ".claude" / "hooks"
REMINDER = HOOKS / "orchestrator-compact-reminder.py"
REHYDRATE = HOOKS / "jumpcode-rehydrate-after-compact.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_transcript(directory, name, tokens):
    p = Path(directory) / f"{name}.jsonl"
    p.write_text(json.dumps({
        "message": {"usage": {
            "input_tokens": tokens,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        }}}) + "\n", encoding="utf-8")
    return p


@unittest.skipUnless(REMINDER.exists(), "global reminder hook not installed")
class ScanTeamContextTests(unittest.TestCase):
    def setUp(self):
        self.mod = _load(REMINDER, "reminder_hook")

    def test_reports_only_leads_over_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_transcript(tmp, "sid-backend", 210000)
            _write_transcript(tmp, "sid-qa", 5000)
            state = {"roles": [
                {"role": "orchestrator", "session_id": "sid-orch"},
                {"role": "backend-lead", "session_id": "sid-backend"},
                {"role": "qa-lead", "session_id": "sid-qa"},
            ]}
            over = self.mod.scan_team_context(state, tmp, threshold=200000)
            self.assertEqual(over, [("backend-lead", 210000)])

    def test_orchestrator_own_window_is_excluded_from_team(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_transcript(tmp, "sid-orch", 999999)
            state = {"roles": [{"role": "orchestrator", "session_id": "sid-orch"}]}
            self.assertEqual(self.mod.scan_team_context(state, tmp, 200000), [])

    def test_missing_transcript_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = {"roles": [{"role": "backend-lead", "session_id": "absent"}]}
            self.assertEqual(self.mod.scan_team_context(state, tmp, 200000), [])


@unittest.skipUnless(REHYDRATE.exists(), "rehydrate hook not installed")
class RehydrateCardTests(unittest.TestCase):
    def setUp(self):
        self.mod = _load(REHYDRATE, "rehydrate_hook")

    def test_lead_card_tells_it_to_report_back_and_announce(self):
        card = self.mod.rehydrate_card("backend-lead", "bugsmash", "/root", "/jc")
        self.assertIn("backend-lead", card)
        self.assertIn("report-done", card)
        self.assertIn("compaction complete", card)   # announces it is back (refinement 1)
        self.assertIn("_PROTOCOL.md", card)

    def test_orchestrator_card_has_no_self_notify(self):
        card = self.mod.rehydrate_card("orchestrator", "bugsmash", "/root", "/jc")
        self.assertIn("dispatch status", card)
        self.assertNotIn("compaction complete", card)  # never notifies itself

    def test_state_for_session_matches_on_session_field(self):
        with tempfile.TemporaryDirectory() as home:
            sdir = Path(home) / "state" / "sessions"
            sdir.mkdir(parents=True)
            (sdir / "bugsmash.json").write_text(
                json.dumps({"session": "macbook-bugsmash", "workspace": "bugsmash"}),
                encoding="utf-8")
            import os
            with unittest.mock.patch.dict(os.environ, {"JUMPCODE_HOME": home}):
                got = self.mod.state_for_session("macbook-bugsmash")
                self.assertEqual(got.get("workspace"), "bugsmash")
                self.assertIsNone(self.mod.state_for_session("macbook-other"))


import unittest.mock  # noqa: E402  (used above)


if __name__ == "__main__":
    unittest.main()
