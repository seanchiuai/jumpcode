import importlib.util
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

_JUMPCODE = Path(__file__).resolve().parents[1] / "bin" / "jumpcode"
spec = importlib.util.spec_from_file_location(
    "jumpcode", _JUMPCODE, loader=SourceFileLoader("jumpcode", str(_JUMPCODE))
)
jumpcode = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jumpcode)


class PaneStateTests(unittest.TestCase):
    def test_working_when_interrupt_hint_present(self):
        screen = "✳ Crunching… (26s · ↑ 958 tokens · esc to interrupt)\n❯ \n"
        self.assertEqual(jumpcode.pane_state(screen), "working")

    def test_waiting_on_a_confirm_prompt(self):
        screen = "Do you want to proceed?\n❯ 1. Yes\n  2. No\n"
        self.assertEqual(jumpcode.pane_state(screen), "waiting")

    def test_idle_otherwise(self):
        screen = "❯ \n⏵⏵ auto mode on (shift+tab to cycle)        40262 tokens\n"
        self.assertEqual(jumpcode.pane_state(screen), "idle")

    def test_idle_auto_mode_footer_with_rotating_esc_hint_is_idle(self):
        # LIVE-CONFIRMED 2026-06-07 (Claude Code 2.1.168): the auto-mode footer rotates
        # a hint that can read "· esc to interrupt" even at an idle empty composer. That
        # must NOT be read as the working spinner.
        screen = (
            "  ⎿  Tip: Continue your session in Claude Code Desktop with /desktop\n"
            "──────────────────────────────\n"
            "❯ \n"
            "──────────────────────────────\n"
            "  ⏵⏵ auto mode on (shift+tab to cycle) · esc to interrupt          45765 tokens\n"
        )
        self.assertEqual(jumpcode.pane_state(screen), "idle")

    def test_working_spinner_wins_even_with_auto_mode_footer(self):
        # When truly working, the spinner line carries 'esc to interrupt' and must win
        # even though the auto-mode footer (also containing it) is present below.
        screen = (
            "✶ Ideating… (36s · ↓ 2.0k tokens · esc to interrupt)\n"
            "❯ \n"
            "  ⏵⏵ auto mode on (shift+tab to cycle) · esc to interrupt          43470 tokens\n"
        )
        self.assertEqual(jumpcode.pane_state(screen), "working")

    def test_claude_default_runtime_unchanged(self):
        # existing three tests cover claude implicitly; this pins the explicit arg
        screen = "✳ Crunching… (26s · esc to interrupt)\n❯ \n"
        self.assertEqual(jumpcode.pane_state(screen, "claude"), "working")

    def test_codex_trust_prompt_is_waiting(self):
        # captured live from codex 0.137.0-alpha.4 on 2026-06-07
        screen = ("  Do you trust the contents of this directory?\n"
                  "› 1. Yes, continue\n  2. No, quit\n  Press enter to continue\n")
        self.assertEqual(jumpcode.pane_state(screen, "codex"), "waiting")

    def test_codex_idle_composer(self):
        # captured live: empty composer shows the greyed placeholder
        screen = ("╭─────╮\n│ >_ OpenAI Codex (v0.137.0-alpha.4) │\n╰─────╯\n"
                  "› Explain this codebase\n  gpt-5.5 high · /tmp/x\n")
        self.assertEqual(jumpcode.pane_state(screen, "codex"), "idle")

    def test_codex_busy_marker(self):
        # confirmed live on codex 0.137.0-alpha.4 (2026-06-07): "• Working (Ns • esc to interrupt)"
        screen = "• Working (1m 4s • esc to interrupt)\n› \n"
        self.assertEqual(jumpcode.pane_state(screen, "codex"), "working")

    def test_unknown_runtime_falls_back_to_claude(self):
        screen = "Do you want to proceed?\n❯ 1. Yes\n  2. No\n"
        self.assertEqual(jumpcode.pane_state(screen, "gemini"), "waiting")


class ActiveSubagentsTests(unittest.TestCase):
    def _notice(self, frm, subject):
        return {"type": "dispatch.sent", "kind": "notice", "from": frm, "subject": subject}

    def test_start_then_end_nets_to_empty(self):
        d = [
            self._notice("backend-lead", "subagent:start code-reviewer"),
            self._notice("backend-lead", "subagent:end code-reviewer"),
        ]
        self.assertEqual(jumpcode.active_subagents(d), {})

    def test_open_subagent_is_reported_per_role(self):
        d = [
            self._notice("backend-lead", "subagent:start code-reviewer"),
            self._notice("frontend-lead", "subagent:start a11y-auditor"),
            self._notice("backend-lead", "subagent:start migration-writer"),
        ]
        self.assertEqual(
            jumpcode.active_subagents(d),
            {"backend-lead": ["code-reviewer", "migration-writer"],
             "frontend-lead": ["a11y-auditor"]},
        )

    def test_non_subagent_notices_and_other_kinds_ignored(self):
        d = [
            self._notice("backend-lead", "just an fyi"),
            {"type": "dispatch.sent", "kind": "request", "from": "orchestrator",
             "subject": "subagent:start nope"},  # wrong kind, ignored
        ]
        self.assertEqual(jumpcode.active_subagents(d), {})


class LastSeenTests(unittest.TestCase):
    def _d(self, frm, to, ts):
        return {"type": "dispatch.sent", "from": frm, "to": to, "created_at": ts}

    def test_woken_but_silent_lead_has_addressed_not_spoke(self):
        # orchestrator dispatches backend-lead twice; backend never replies.
        # A single merged last_seen would make backend look freshly active; the
        # split must show it was *addressed* recently but never *spoke*.
        d = [
            self._d("orchestrator", "backend-lead", "2026-06-07T01:00:00Z"),
            self._d("orchestrator", "backend-lead", "2026-06-07T02:00:00Z"),
        ]
        seen = jumpcode.last_seen_by_role(d)
        self.assertEqual(seen["backend-lead"]["addressed"], "2026-06-07T02:00:00Z")
        self.assertIsNone(seen["backend-lead"]["spoke"])
        self.assertEqual(seen["orchestrator"]["spoke"], "2026-06-07T02:00:00Z")

    def test_reply_updates_spoke_independently(self):
        d = [
            self._d("orchestrator", "backend-lead", "2026-06-07T01:00:00Z"),
            self._d("backend-lead", "orchestrator", "2026-06-07T03:00:00Z"),
        ]
        seen = jumpcode.last_seen_by_role(d)
        self.assertEqual(seen["backend-lead"]["spoke"], "2026-06-07T03:00:00Z")
        self.assertEqual(seen["backend-lead"]["addressed"], "2026-06-07T01:00:00Z")

    def test_non_dispatch_events_ignored(self):
        d = [{"type": "other", "from": "x", "to": "y", "created_at": "2026-06-07T01:00:00Z"}]
        self.assertEqual(jumpcode.last_seen_by_role(d), {})


if __name__ == "__main__":
    unittest.main()
