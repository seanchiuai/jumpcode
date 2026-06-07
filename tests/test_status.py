import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_COCKPIT = ROOT / ".agent-cockpit" / "bin" / "cockpit"
spec = importlib.util.spec_from_file_location(
    "cockpit", _COCKPIT, loader=SourceFileLoader("cockpit", str(_COCKPIT))
)
cockpit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cockpit)


def _req(did, to, task, ts, reply_to=None):
    return {"type": "dispatch.sent", "kind": "request", "dispatch_id": did,
            "from": "orchestrator", "to": to, "task": task,
            "created_at": ts, "reply_to": reply_to}


def _report(did, frm, ts, task=None, reply_to=None, kind="report-done"):
    return {"type": "dispatch.sent", "kind": kind, "dispatch_id": did,
            "from": frm, "to": "orchestrator", "task": task,
            "created_at": ts, "reply_to": reply_to}


class OpenRequestsTests(unittest.TestCase):
    def test_request_with_no_report_is_open(self):
        d = [_req("dsp-1", "backend-lead", "SEA-7", "2026-06-07T01:00:00Z")]
        opens = cockpit.open_requests(d)
        self.assertEqual([r["dispatch_id"] for r in opens], ["dsp-1"])

    def test_precise_reply_to_closes_the_loop(self):
        d = [
            _req("dsp-1", "backend-lead", "SEA-7", "2026-06-07T01:00:00Z"),
            _report("dsp-2", "backend-lead", "2026-06-07T02:00:00Z", reply_to="dsp-1"),
        ]
        self.assertEqual(cockpit.open_requests(d), [])

    def test_fallback_same_task_from_recipient_closes_the_loop(self):
        # No reply_to set (the pre-linkage convention); still pairs by task+sender.
        d = [
            _req("dsp-1", "backend-lead", "SEA-7", "2026-06-07T01:00:00Z"),
            _report("dsp-2", "backend-lead", "2026-06-07T02:00:00Z", task="SEA-7"),
        ]
        self.assertEqual(cockpit.open_requests(d), [])

    def test_report_from_other_role_does_not_close(self):
        d = [
            _req("dsp-1", "backend-lead", "SEA-7", "2026-06-07T01:00:00Z"),
            _report("dsp-2", "frontend-lead", "2026-06-07T02:00:00Z", task="SEA-7"),
        ]
        self.assertEqual([r["dispatch_id"] for r in cockpit.open_requests(d)], ["dsp-1"])

    def test_two_open_requests_one_report_leaves_one_open(self):
        # Two requests to the same lead, same task, only one report -> exactly one open.
        d = [
            _req("dsp-1", "backend-lead", "SEA-7", "2026-06-07T01:00:00Z"),
            _req("dsp-2", "backend-lead", "SEA-7", "2026-06-07T02:00:00Z"),
            _report("dsp-3", "backend-lead", "2026-06-07T03:00:00Z", task="SEA-7"),
        ]
        opens = cockpit.open_requests(d)
        self.assertEqual(len(opens), 1)

    def test_precise_reply_to_wins_over_fallback_steal(self):
        # Two same-task requests to one lead; the single report explicitly replies to
        # the SECOND. Precise linkage must close B and leave A open — a request-by-
        # request fallback would wrongly let A consume R and report B open.
        d = [
            _req("dsp-A", "backend-lead", "SEA-7", "2026-06-07T01:00:00Z"),
            _req("dsp-B", "backend-lead", "SEA-7", "2026-06-07T02:00:00Z"),
            _report("dsp-R", "backend-lead", "2026-06-07T03:00:00Z",
                    task="SEA-7", reply_to="dsp-B"),
        ]
        self.assertEqual([r["dispatch_id"] for r in cockpit.open_requests(d)], ["dsp-A"])

    def test_blocked_report_also_closes(self):
        d = [
            _req("dsp-1", "backend-lead", "SEA-7", "2026-06-07T01:00:00Z"),
            _report("dsp-2", "backend-lead", "2026-06-07T02:00:00Z",
                    reply_to="dsp-1", kind="report-blocked"),
        ]
        self.assertEqual(cockpit.open_requests(d), [])


class StatusCliTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _run(self, *args, check=True):
        env = os.environ.copy()
        env["COCKPIT_HOME"] = str(self.tmp_path / ".agent-cockpit")
        env.pop("COCKPIT_TMUX_SESSION", None)
        env.pop("TMUX", None)
        r = subprocess.run([sys.executable, str(_COCKPIT), *args],
                           cwd=self.tmp_path, text=True, capture_output=True, env=env)
        if check and r.returncode != 0:
            raise AssertionError(f"{args} failed\n{r.stdout}\n{r.stderr}")
        return r

    def test_status_json_lists_open_loops(self):
        self._run("dispatch", "send", "--from", "orchestrator", "--to", "backend-lead",
                  "--task", "SEA-7", "--no-wake", "do the thing")
        out = json.loads(self._run("dispatch", "status", "--json").stdout)
        ids = [o["dispatch_id"] for o in out["open"]]
        self.assertEqual(len(ids), 1)
        self.assertEqual(out["open"][0]["to"], "backend-lead")

    def test_status_empty_when_request_is_reported(self):
        sent = json.loads(self._run(
            "dispatch", "send", "--from", "orchestrator", "--to", "backend-lead",
            "--task", "SEA-7", "--no-wake", "do the thing").stdout)
        self._run("dispatch", "send", "--from", "backend-lead", "--to", "orchestrator",
                  "--kind", "report-done", "--task", "SEA-7",
                  "--reply-to", sent["dispatch_id"], "--no-wake", "done")
        out = json.loads(self._run("dispatch", "status", "--json").stdout)
        self.assertEqual(out["open"], [])


if __name__ == "__main__":
    unittest.main()
