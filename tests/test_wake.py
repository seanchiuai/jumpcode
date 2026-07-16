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


class StagedRemnantTests(unittest.TestCase):
    TEXT = ("[dispatch dsp-20260716-001 from orchestrator] fix the thing "
            "— full text: ./.jumpcode/bin/dispatch show dsp-20260716-001 "
            "(inbox: ./.jumpcode/bin/dispatch inbox backend-lead)")

    def test_full_text_staged_is_remnant(self):
        cap = "❯ " + self.TEXT + "\n"
        self.assertTrue(jumpcode._staged_remnant(cap, self.TEXT))

    def test_partial_tail_staged_is_remnant(self):
        # The observed stall signature: only a fragment of the wake text survives
        # at the prompt after a swallowed Enter.
        for tail in ("atch", "inbox", "dispatch"):
            cap = f"❯ {tail}\n⏵⏵ auto mode on (shift+tab to cycle)\n"
            self.assertTrue(jumpcode._staged_remnant(cap, self.TEXT), tail)

    def test_empty_composer_is_submitted(self):
        cap = "> [dispatch dsp-20260716-001 …] fix the thing\n✻ Thinking…\n❯ \n"
        self.assertFalse(jumpcode._staged_remnant(cap, self.TEXT))

    def test_menu_cursor_is_not_a_remnant(self):
        # A permission dialog after a successful submit uses '❯' as its cursor.
        cap = "Do you want to allow this?\n❯ 1. Yes\n  2. No\n"
        self.assertFalse(jumpcode._staged_remnant(cap, self.TEXT))

    def test_wrapped_staged_line_is_remnant(self):
        # Narrow pane: composer wraps; the prompt row holds the leading slice.
        cap = "❯ [dispatch dsp-2026\n0716-001 from orch\n"
        self.assertTrue(jumpcode._staged_remnant(cap, self.TEXT))

    def test_codex_prompt_char(self):
        self.assertTrue(jumpcode._staged_remnant("› inbox\n", self.TEXT))

    def test_no_prompt_line_is_not_staged(self):
        self.assertFalse(jumpcode._staged_remnant("some full-screen dialog\n", self.TEXT))

    def test_empty_text_is_false(self):
        self.assertFalse(jumpcode._staged_remnant("❯ atch\n", ""))


class WakePaneSubmitTests(unittest.TestCase):
    """wake_pane must verify the SUBMIT, not just the typing: woke=True means the
    composer actually cleared after Enter. A swallowed Enter gets one retry."""

    TEXT = "[dispatch dsp-20260716-001 from orchestrator] fix the thing"
    STAGED = "❯ [dispatch dsp-20260716-001 from orchestrator] fix the thing\n"
    REMNANT = "❯ atch\n⏵⏵ auto mode on (shift+tab to cycle)\n"
    SUBMITTED = "> [dispatch dsp-20260716-001 …] fix the thing\n✻ Thinking…\n❯ \n"
    EMPTY = "❯ \n⏵⏵ auto mode on (shift+tab to cycle)\n"

    def _run_wake(self, captures):
        cmds = []

        def fake_run(cmd, **kwargs):
            cmds.append(cmd)
            r = mock.Mock()
            r.stdout = "%1\tbackend-lead\n" if "list-panes" in cmd else ""
            return r

        with mock.patch.object(jumpcode.subprocess, "run", side_effect=fake_run), \
             mock.patch.object(jumpcode, "_tmux_capture", side_effect=list(captures)), \
             mock.patch.object(jumpcode.time, "sleep"):
            woke = jumpcode.wake_pane("macbook-x", "backend-lead", self.TEXT)
        enters = sum(1 for c in cmds if c[-1] == "Enter")
        return woke, enters

    def test_verified_submit_first_try(self):
        woke, enters = self._run_wake([self.STAGED, self.SUBMITTED])
        self.assertTrue(woke)
        self.assertEqual(enters, 1)

    def test_swallowed_enter_retried_then_verified(self):
        woke, enters = self._run_wake([self.STAGED, self.REMNANT, self.SUBMITTED])
        self.assertTrue(woke)
        self.assertEqual(enters, 2)

    def test_never_submits_reports_false(self):
        # Both Enters swallowed on both type attempts → woke must be False.
        woke, enters = self._run_wake(
            [self.STAGED, self.REMNANT, self.REMNANT,
             self.STAGED, self.REMNANT, self.REMNANT])
        self.assertFalse(woke)
        self.assertEqual(enters, 4)

    def test_text_never_lands_reports_false(self):
        woke, enters = self._run_wake([self.EMPTY, self.EMPTY])
        self.assertFalse(woke)
        self.assertEqual(enters, 0)


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
