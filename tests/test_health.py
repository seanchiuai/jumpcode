import importlib.util
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

_COCKPIT = Path(__file__).resolve().parents[1] / "bin" / "cockpit"
spec = importlib.util.spec_from_file_location(
    "cockpit", _COCKPIT, loader=SourceFileLoader("cockpit", str(_COCKPIT))
)
cockpit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cockpit)


class PaneStateTests(unittest.TestCase):
    def test_working_when_interrupt_hint_present(self):
        screen = "✳ Crunching… (26s · ↑ 958 tokens · esc to interrupt)\n❯ \n"
        self.assertEqual(cockpit.pane_state(screen), "working")

    def test_waiting_on_a_confirm_prompt(self):
        screen = "Do you want to proceed?\n❯ 1. Yes\n  2. No\n"
        self.assertEqual(cockpit.pane_state(screen), "waiting")

    def test_idle_otherwise(self):
        screen = "❯ \n⏵⏵ auto mode on (shift+tab to cycle)        40262 tokens\n"
        self.assertEqual(cockpit.pane_state(screen), "idle")

    def test_claude_default_runtime_unchanged(self):
        # existing three tests cover claude implicitly; this pins the explicit arg
        screen = "✳ Crunching… (26s · esc to interrupt)\n❯ \n"
        self.assertEqual(cockpit.pane_state(screen, "claude"), "working")

    def test_codex_trust_prompt_is_waiting(self):
        # captured live from codex 0.137.0-alpha.4 on 2026-06-07
        screen = ("  Do you trust the contents of this directory?\n"
                  "› 1. Yes, continue\n  2. No, quit\n  Press enter to continue\n")
        self.assertEqual(cockpit.pane_state(screen, "codex"), "waiting")

    def test_codex_idle_composer(self):
        # captured live: empty composer shows the greyed placeholder
        screen = ("╭─────╮\n│ >_ OpenAI Codex (v0.137.0-alpha.4) │\n╰─────╯\n"
                  "› Explain this codebase\n  gpt-5.5 high · /tmp/x\n")
        self.assertEqual(cockpit.pane_state(screen, "codex"), "idle")

    def test_codex_busy_marker(self):
        # confirmed live on codex 0.137.0-alpha.4 (2026-06-07): "• Working (Ns • esc to interrupt)"
        screen = "• Working (1m 4s • esc to interrupt)\n› \n"
        self.assertEqual(cockpit.pane_state(screen, "codex"), "working")

    def test_unknown_runtime_falls_back_to_claude(self):
        screen = "Do you want to proceed?\n❯ 1. Yes\n  2. No\n"
        self.assertEqual(cockpit.pane_state(screen, "gemini"), "waiting")


class ActiveSubagentsTests(unittest.TestCase):
    def _notice(self, frm, subject):
        return {"type": "dispatch.sent", "kind": "notice", "from": frm, "subject": subject}

    def test_start_then_end_nets_to_empty(self):
        d = [
            self._notice("backend-lead", "subagent:start code-reviewer"),
            self._notice("backend-lead", "subagent:end code-reviewer"),
        ]
        self.assertEqual(cockpit.active_subagents(d), {})

    def test_open_subagent_is_reported_per_role(self):
        d = [
            self._notice("backend-lead", "subagent:start code-reviewer"),
            self._notice("frontend-lead", "subagent:start a11y-auditor"),
            self._notice("backend-lead", "subagent:start migration-writer"),
        ]
        self.assertEqual(
            cockpit.active_subagents(d),
            {"backend-lead": ["code-reviewer", "migration-writer"],
             "frontend-lead": ["a11y-auditor"]},
        )

    def test_non_subagent_notices_and_other_kinds_ignored(self):
        d = [
            self._notice("backend-lead", "just an fyi"),
            {"type": "dispatch.sent", "kind": "request", "from": "orchestrator",
             "subject": "subagent:start nope"},  # wrong kind, ignored
        ]
        self.assertEqual(cockpit.active_subagents(d), {})


if __name__ == "__main__":
    unittest.main()
