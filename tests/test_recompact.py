import importlib.util
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock

_JUMPCODE = Path(__file__).resolve().parents[1] / "bin" / "jumpcode"
spec = importlib.util.spec_from_file_location(
    "jumpcode", _JUMPCODE, loader=SourceFileLoader("jumpcode", str(_JUMPCODE))
)
jumpcode = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jumpcode)

PANES = "%93\torchestrator\n%94\tbackend-lead\n%95\tfrontend-lead\n"


def _fake_run(panes_text):
    """A subprocess.run stub: list-panes returns panes_text; everything else records argv."""
    calls = []

    def run(argv, *a, **k):
        calls.append(argv)
        out = mock.Mock()
        out.stdout = panes_text if "list-panes" in argv else ""
        return out

    return run, calls


class RecompactPaneTests(unittest.TestCase):
    def test_sends_compact_then_queues_follow_up_message(self):
        run, calls = _fake_run(PANES)
        with mock.patch.object(jumpcode.subprocess, "run", side_effect=run), \
             mock.patch.object(jumpcode.time, "sleep"):
            ok = jumpcode.recompact_pane("macbook-bugsmash", "backend-lead", "re-read charter, report open loops")
        self.assertTrue(ok)
        sends = [c for c in calls if "send-keys" in c]
        # all keystrokes target the backend-lead pane (%94), include Escape, /compact, and
        # the queued follow-up message — Enter must appear for BOTH submissions.
        self.assertTrue(all("%94" in c for c in sends))
        flat = [tok for c in sends for tok in c]
        self.assertIn("Escape", flat)
        self.assertIn("/compact", flat)
        self.assertIn("re-read charter, report open loops", flat)
        self.assertEqual(flat.count("Enter"), 2)  # /compact submit + follow-up submit
        # the follow-up message is queued AFTER /compact + its Enter
        self.assertGreater(flat.index("re-read charter, report open loops"), flat.index("/compact"))

    def test_unknown_role_sends_nothing_and_fails(self):
        run, calls = _fake_run(PANES)
        with mock.patch.object(jumpcode.subprocess, "run", side_effect=run), \
             mock.patch.object(jumpcode.time, "sleep"):
            ok = jumpcode.recompact_pane("macbook-bugsmash", "nope-lead", "msg")
        self.assertFalse(ok)
        self.assertFalse([c for c in calls if "send-keys" in c])  # no keys sent

    def test_empty_session_fails_fast(self):
        run, calls = _fake_run(PANES)
        with mock.patch.object(jumpcode.subprocess, "run", side_effect=run), \
             mock.patch.object(jumpcode.time, "sleep"):
            self.assertFalse(jumpcode.recompact_pane("", "backend-lead", "msg"))
        self.assertEqual(calls, [])  # never even calls tmux


if __name__ == "__main__":
    unittest.main()
