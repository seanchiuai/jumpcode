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


class ResolvePaneTests(unittest.TestCase):
    SAMPLE = "%26\torchestrator\n%27\tfrontend-lead\n%28\tbackend-lead\n%29\tqa-lead\n"

    def test_resolves_exact_role(self):
        self.assertEqual(jumpcode.resolve_pane(self.SAMPLE, "backend-lead"), "%28")

    def test_unknown_role_returns_none(self):
        self.assertIsNone(jumpcode.resolve_pane(self.SAMPLE, "nope"))

    def test_ignores_panes_without_role(self):
        self.assertIsNone(jumpcode.resolve_pane("%30\t\n", "orchestrator"))


class InjectedTextPresentTests(unittest.TestCase):
    TEXT = "[dispatch dsp-20260606-022 from orchestrator] author testing SKILL.md"

    def test_present_plainly(self):
        cap = "❯ " + self.TEXT + "\n"
        self.assertTrue(jumpcode._injected_text_present(cap, self.TEXT))

    def test_present_even_when_wrapped_across_rows(self):
        # tmux wraps a long line in a narrow pane; whitespace/newlines are inserted.
        cap = "❯ [dispatch dsp-2026\n0606-022 from orch\nestrator] author te\nsting SKILL.md\n"
        self.assertTrue(jumpcode._injected_text_present(cap, self.TEXT))

    def test_absent_returns_false(self):
        cap = "❯ \n⏵⏵ auto mode on (shift+tab to cycle)   40262 tokens\n"
        self.assertFalse(jumpcode._injected_text_present(cap, self.TEXT))

    def test_empty_text_is_false(self):
        self.assertFalse(jumpcode._injected_text_present("anything", ""))


class ResolveSessionTests(unittest.TestCase):
    def test_prefers_explicit_env(self):
        with mock.patch.dict(jumpcode.os.environ, {"JUMPCODE_TMUX_SESSION": "macbook-webapp"}):
            self.assertEqual(jumpcode.resolve_session(), "macbook-webapp")

    def test_no_env_and_no_tmux_is_empty(self):
        env = {k: v for k, v in jumpcode.os.environ.items()
               if k not in ("JUMPCODE_TMUX_SESSION", "TMUX")}
        with mock.patch.dict(jumpcode.os.environ, env, clear=True):
            self.assertEqual(jumpcode.resolve_session(), "")


if __name__ == "__main__":
    unittest.main()
