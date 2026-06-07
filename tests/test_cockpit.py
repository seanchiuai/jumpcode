import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COCKPIT = ROOT / ".agent-cockpit" / "bin" / "cockpit"


def run_cmd(tmp_path, *args, check=True):
    env = os.environ.copy()
    env["COCKPIT_HOME"] = str(tmp_path / ".agent-cockpit")
    # Never let tests touch a real tmux session: clear both the explicit override
    # and $TMUX so resolve_session() returns "" and wake_pane() is a no-op.
    env.pop("COCKPIT_TMUX_SESSION", None)
    env.pop("TMUX", None)
    result = subprocess.run(
        [sys.executable, str(COCKPIT), *args],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        env=env,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed: {args}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return result


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class DispatchCliTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_dispatch_send_logs_and_is_in_inbox(self):
        sent = json.loads(run_cmd(
            self.tmp_path, "dispatch", "send",
            "--from", "orchestrator", "--to", "backend-lead",
            "--task", "ENG-12", "--subject", "Build auth", "--no-wake",
            "Implement the auth endpoints.",
        ).stdout)
        self.assertEqual(sent["type"], "dispatch.sent")
        self.assertTrue(sent["dispatch_id"].startswith("dsp-"))
        self.assertEqual(sent["task"], "ENG-12")
        self.assertEqual(sent["from"], "orchestrator")
        self.assertEqual(sent["to"], "backend-lead")
        self.assertEqual(sent["body"], "Implement the auth endpoints.")

        # It is durably logged to the dispatch jsonl...
        logged = read_jsonl(self.tmp_path / ".agent-cockpit" / "state" / "dispatches.jsonl")
        self.assertEqual([m["dispatch_id"] for m in logged], [sent["dispatch_id"]])

        # ...and recoverable via inbox (addressed-to filter).
        inbox = json.loads(run_cmd(
            self.tmp_path, "dispatch", "inbox", "backend-lead", "--json"
        ).stdout)
        self.assertEqual([m["dispatch_id"] for m in inbox], [sent["dispatch_id"]])

    def test_woke_flag_is_persisted_to_durable_log(self):
        # Trigger the real WAKE path (note: no --no-wake). With no tmux session
        # resolvable, wake_pane() returns False, so woke == False. The delivery
        # VERDICT is the point: it must be recorded in the durable log, not only
        # echoed to stdout — otherwise the recovery/feedback layer can never tell
        # a delivered dispatch from an undelivered one.
        sent = json.loads(run_cmd(
            self.tmp_path, "dispatch", "send",
            "--from", "orchestrator", "--to", "backend-lead",
            "--task", "ENG-12", "--subject", "Build auth",
            "Implement the auth endpoints.",
        ).stdout)
        # stdout carries the delivery verdict...
        self.assertIn("woke", sent)
        self.assertFalse(sent["woke"])  # no tmux session -> not delivered

        # ...and so MUST the durable log line (this is the bug: today `woke` is
        # set on the event dict AFTER append_event, so the JSONL omits it).
        logged = read_jsonl(self.tmp_path / ".agent-cockpit" / "state" / "dispatches.jsonl")
        self.assertEqual(len(logged), 1)
        self.assertIn("woke", logged[0])
        self.assertEqual(logged[0]["woke"], sent["woke"])

    def test_inbox_only_returns_messages_addressed_to_recipient(self):
        run_cmd(self.tmp_path, "dispatch", "send", "--from", "orchestrator",
                "--to", "backend-lead", "--no-wake", "for backend")
        run_cmd(self.tmp_path, "dispatch", "send", "--from", "orchestrator",
                "--to", "frontend-lead", "--no-wake", "for frontend")
        inbox = json.loads(run_cmd(
            self.tmp_path, "dispatch", "inbox", "backend-lead", "--json"
        ).stdout)
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]["body"], "for backend")

    def test_report_kind_is_just_a_dispatch(self):
        sent = json.loads(run_cmd(
            self.tmp_path, "dispatch", "send",
            "--from", "backend-lead", "--to", "orchestrator",
            "--kind", "report-done", "--task", "ENG-12", "--no-wake",
            "Done; updated ENG-12 in Linear.",
        ).stdout)
        self.assertEqual(sent["kind"], "report-done")
        self.assertEqual(sent["from"], "backend-lead")

    def test_dispatch_show_round_trips(self):
        sent = json.loads(run_cmd(
            self.tmp_path, "dispatch", "send", "--from", "hermes",
            "--to", "orchestrator", "--subject", "kickoff", "--no-wake",
            "Start the smoke task.",
        ).stdout)
        shown = json.loads(run_cmd(
            self.tmp_path, "dispatch", "show", sent["dispatch_id"], "--json"
        ).stdout)
        self.assertEqual(shown["body"], "Start the smoke task.")
        self.assertEqual(shown["subject"], "kickoff")

    def test_dispatch_log_is_human_readable_feed(self):
        run_cmd(self.tmp_path, "dispatch", "send", "--from", "hermes",
                "--to", "orchestrator", "--subject", "kickoff", "--no-wake", "go")
        out = run_cmd(self.tmp_path, "dispatch", "log").stdout
        self.assertIn("hermes", out)
        self.assertIn("orchestrator", out)
        self.assertIn("kickoff", out)

    def test_unique_ids_across_sends(self):
        ids = set()
        for i in range(5):
            sent = json.loads(run_cmd(
                self.tmp_path, "dispatch", "send", "--from", "orchestrator",
                "--to", "qa-lead", "--no-wake", f"msg {i}",
            ).stdout)
            ids.add(sent["dispatch_id"])
        self.assertEqual(len(ids), 5)


if __name__ == "__main__":
    unittest.main()
