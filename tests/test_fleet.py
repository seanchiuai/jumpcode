import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

_JUMPCODE = Path(__file__).resolve().parents[1] / "bin" / "jumpcode"
spec = importlib.util.spec_from_file_location(
    "jumpcode", _JUMPCODE, loader=SourceFileLoader("jumpcode", str(_JUMPCODE))
)
jumpcode = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jumpcode)

IDLE_SECS = 600  # 10 min


def wp(alive, agents=None, attached=False, open_loops=0, config_ok=True):
    """Build the classifier input dict for one workspace."""
    return {
        "alive": alive,
        "attached": attached,
        "agents": agents or [],
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
                wp(alive=True, open_loops=1)), "error")

    def test_working_pane_is_active(self):
        self.assertEqual(
            jumpcode.classify_workspace(
                wp(alive=True, agents=[{"state": "working"}, {"state": "idle"}])),
            "active")

    def test_attached_is_active_even_if_all_panes_idle(self):
        # a window is open on it (you're driving it by hand) -> active, regardless
        # of dispatch traffic. This is the case the old recency rule got wrong.
        self.assertEqual(
            jumpcode.classify_workspace(
                wp(alive=True, agents=[{"state": "idle"}], attached=True)), "active")

    def test_detached_and_all_idle_is_idle(self):
        self.assertEqual(
            jumpcode.classify_workspace(
                wp(alive=True, agents=[{"state": "idle"}, {"state": "idle"}],
                   attached=False)), "idle")

    def test_detached_but_pane_working_is_active(self):
        # background work with no window open still counts as active
        self.assertEqual(
            jumpcode.classify_workspace(
                wp(alive=True, agents=[{"state": "working"}], attached=False)),
            "active")

    def test_alive_no_panes_detached_is_idle(self):
        # session exists but no panes scanned and no window open -> not "active"
        self.assertEqual(
            jumpcode.classify_workspace(
                wp(alive=True, agents=[], attached=False)), "idle")

    def test_error_wins_over_active(self):
        self.assertEqual(
            jumpcode.classify_workspace(
                wp(alive=True, agents=[{"state": "working"}],
                   open_loops=1, attached=True)), "error")


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


def _ago(secs):
    t = datetime.now(timezone.utc) - timedelta(seconds=secs)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _sent(frm, to, ts):
    return {"type": "dispatch.sent", "from": frm, "to": to, "created_at": ts}


class SilentLoopTests(unittest.TestCase):
    def test_woken_recently_no_reply_overdue_counts(self):
        # backend-lead woken 20 min ago, never spoke -> overdue & recent -> 1
        disp = [_sent("orchestrator", "backend-lead", _ago(1200))]
        self.assertEqual(jumpcode.fleet_silent_loops(disp), 1)

    def test_replied_after_being_woken_does_not_count(self):
        # backend-lead woken, then replied; orchestrator speaks last so it isn't
        # itself left looking silent by the reply addressing it.
        disp = [_sent("orchestrator", "backend-lead", _ago(1200)),
                _sent("backend-lead", "orchestrator", _ago(700)),
                _sent("orchestrator", "backend-lead", _ago(100))]
        # backend's latest wake (100s ago) is recent but not overdue; orchestrator
        # spoke most recently -> neither is a stale silent loop.
        self.assertEqual(jumpcode.fleet_silent_loops(disp), 0)

    def test_ancient_silent_loop_does_not_count(self):
        # woken 7 days ago, never replied -> too old to be a live error -> 0
        disp = [_sent("orchestrator", "backend-lead", _ago(7 * 86400))]
        self.assertEqual(jumpcode.fleet_silent_loops(disp), 0)

    def test_just_woken_not_yet_overdue_does_not_count(self):
        # woken 2 min ago -> not overdue yet -> 0
        disp = [_sent("orchestrator", "backend-lead", _ago(120))]
        self.assertEqual(jumpcode.fleet_silent_loops(disp), 0)


def row(workspace, status, agents=None, config_ok=True, open_loops=0,
        last_dispatch=None, attached=False):
    """Build a gathered-fleet row for the renderer (post-classification)."""
    return {"workspace": workspace, "status": status, "agents": agents or [],
            "config_ok": config_ok, "stale_open_loops": open_loops,
            "last_dispatch": last_dispatch, "attached": attached}


class RenderTests(unittest.TestCase):
    def test_all_four_headers_present_with_counts(self):
        rows = [row("seo", "active", agents=[{"alive": True}]),
                row("cleanup", "past")]
        out = "\n".join(jumpcode._fleet_render(rows))
        self.assertIn("ACTIVE (1)", out)
        self.assertIn("INACTIVE (0)", out)
        self.assertIn("BROKEN (0)", out)
        self.assertIn("CLOSED — reopenable (1)", out)

    def test_empty_section_still_prints_zero(self):
        out = "\n".join(jumpcode._fleet_render([]))
        for header in ("ACTIVE (0)", "INACTIVE (0)", "BROKEN (0)",
                       "CLOSED — reopenable (0)"):
            self.assertIn(header, out)

    def test_closed_row_shows_revive_command(self):
        out = "\n".join(jumpcode._fleet_render([row("cleanup", "past")]))
        self.assertIn("revive cleanup", out)

    def test_section_order_is_fixed(self):
        out = "\n".join(jumpcode._fleet_render([]))
        self.assertLess(out.index("ACTIVE"), out.index("INACTIVE"))
        self.assertLess(out.index("INACTIVE"), out.index("BROKEN"))
        self.assertLess(out.index("BROKEN"), out.index("CLOSED"))

    def test_live_row_has_panes_and_no_status_word(self):
        line = jumpcode._fleet_line(
            row("seo", "active", agents=[{"alive": True}, {"alive": True}]))
        self.assertIn("2/2 panes", line)
        self.assertNotIn("active", line)  # status conveyed by section header

    def test_error_row_shows_config_note(self):
        line = jumpcode._fleet_line(row("bugsmash", "error", config_ok=False))
        self.assertIn("config!", line)

    def test_attached_row_shows_attached_marker(self):
        attached = jumpcode._fleet_line(
            row("seo", "active", agents=[{"alive": True}], attached=True))
        detached = jumpcode._fleet_line(
            row("obs", "idle", agents=[{"alive": True}], attached=False))
        self.assertIn("attached", attached)
        self.assertIn("detached", detached)

    def test_broken_attached_is_flagged_do_not_reap(self):
        # BROKEN + attached = being repaired; must be flagged so a teardown skips it.
        line = jumpcode._fleet_line(
            row("ambassador", "error", config_ok=False, attached=True))
        self.assertIn("config!", line)
        self.assertIn("DO NOT REAP", line)

    def test_broken_detached_is_not_flagged_in_repair(self):
        line = jumpcode._fleet_line(
            row("ambassador", "error", config_ok=False, attached=False))
        self.assertIn("config!", line)
        self.assertNotIn("DO NOT REAP", line)

    def test_closed_row_omits_panes(self):
        line = jumpcode._fleet_line(row("cleanup", "past"))
        self.assertNotIn("panes", line)
        self.assertIn("revive cleanup", line)


def wrow(workspace, window, agents=None, activity="idle", config_ok=True,
         open_loops=0, last_dispatch=None, session_alive=True):
    """Build a gather_windows row for the list-view renderer."""
    return {"workspace": workspace, "window": window, "activity": activity,
            "agents": agents or [], "config_ok": config_ok,
            "stale_open_loops": open_loops, "last_dispatch": last_dispatch,
            "session_alive": session_alive}


class ClassifyWindowTests(unittest.TestCase):
    def test_parked_beats_open(self):
        self.assertEqual(
            jumpcode.classify_window({"parked": True, "window_open": True}), "parked")

    def test_window_open_is_open(self):
        self.assertEqual(
            jumpcode.classify_window({"parked": False, "window_open": True}), "open")

    def test_no_window_no_park_is_closed(self):
        self.assertEqual(
            jumpcode.classify_window({"parked": False, "window_open": False}), "closed")


class WindowRenderTests(unittest.TestCase):
    def test_three_headers_with_counts_shown_even_at_zero(self):
        out = "\n".join(jumpcode._window_render([wrow("a", "open")]))
        self.assertIn("OPEN (1)", out)
        self.assertIn("PARKED — reopenable (0)", out)
        self.assertIn("CLOSED — reopenable (0)", out)

    def test_parked_and_closed_show_revive(self):
        out = "\n".join(jumpcode._window_render(
            [wrow("obs", "parked"), wrow("seo", "closed")]))
        self.assertIn("revive obs", out)
        self.assertIn("revive seo", out)

    def test_open_row_shows_panes_not_revive(self):
        line = jumpcode._window_line(
            wrow("a", "open", agents=[{"alive": True}, {"alive": True}]))
        self.assertIn("2/2 panes", line)
        self.assertNotIn("revive", line)

    def test_closed_running_hint(self):
        running = jumpcode._window_line(wrow("seo", "closed", session_alive=True))
        stopped = jumpcode._window_line(wrow("seo", "closed", session_alive=False))
        self.assertIn("(still running)", running)
        self.assertNotIn("(still running)", stopped)

    def test_section_order_open_parked_closed(self):
        out = "\n".join(jumpcode._window_render([]))
        self.assertLess(out.index("OPEN"), out.index("PARKED"))
        self.assertLess(out.index("PARKED"), out.index("CLOSED"))


class ParkedStateTests(unittest.TestCase):
    def test_park_unpark_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            self.assertEqual(jumpcode.parked_set(home), set())
            self.assertTrue(jumpcode.set_parked(home, "obs", True))
            self.assertEqual(jumpcode.parked_set(home), {"obs"})
            # idempotent: parking again reports no change
            self.assertFalse(jumpcode.set_parked(home, "obs", True))
            self.assertTrue(jumpcode.set_parked(home, "obs", False))
            self.assertEqual(jumpcode.parked_set(home), set())

    def test_corrupt_parked_file_reads_as_empty(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            (home / "state").mkdir(parents=True)
            jumpcode.parked_path(home).write_text("{not json", encoding="utf-8")
            self.assertEqual(jumpcode.parked_set(home), set())


if __name__ == "__main__":
    unittest.main()
