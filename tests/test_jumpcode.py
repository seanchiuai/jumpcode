import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JUMPCODE = ROOT / ".jumpcode" / "bin" / "jumpcode"


def run_cmd(tmp_path, *args, check=True):
    env = os.environ.copy()
    env["JUMPCODE_HOME"] = str(tmp_path / ".jumpcode")
    # Never let tests touch a real tmux session: clear both the explicit override
    # and $TMUX so resolve_session() returns "" and wake_pane() is a no-op.
    env.pop("JUMPCODE_TMUX_SESSION", None)
    env.pop("TMUX", None)
    result = subprocess.run(
        [sys.executable, str(JUMPCODE), *args],
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
        logged = read_jsonl(self.tmp_path / ".jumpcode" / "state" / "dispatches.jsonl")
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
        logged = read_jsonl(self.tmp_path / ".jumpcode" / "state" / "dispatches.jsonl")
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

    def test_send_tags_event_with_session(self):
        # The collision fix: a dispatch's identity is (session, role). --session is the
        # explicit form (env JUMPCODE_TMUX_SESSION is the implicit one, cleared in tests).
        sent = json.loads(run_cmd(
            self.tmp_path, "dispatch", "send",
            "--from", "orchestrator", "--to", "backend-lead",
            "--session", "macbook-seo", "--no-wake", "seo work",
        ).stdout)
        self.assertEqual(sent["session"], "macbook-seo")
        logged = read_jsonl(self.tmp_path / ".jumpcode" / "state" / "dispatches.jsonl")
        self.assertEqual(logged[0]["session"], "macbook-seo")

    def test_send_without_session_logs_untagged_with_warning(self):
        r = run_cmd(
            self.tmp_path, "dispatch", "send",
            "--from", "orchestrator", "--to", "backend-lead", "--no-wake", "x",
        )
        self.assertIsNone(json.loads(r.stdout)["session"])
        self.assertIn("UNTAGGED", r.stderr)

    def test_inbox_is_session_scoped(self):
        # Same role name in three concurrent workspaces: each session's backend-lead
        # must see ONLY its own session's traffic — this is the hijack regression test.
        run_cmd(self.tmp_path, "dispatch", "send", "--from", "orchestrator",
                "--to", "backend-lead", "--session", "macbook-ambassador",
                "--no-wake", "BB-63 START NOW")
        run_cmd(self.tmp_path, "dispatch", "send", "--from", "orchestrator",
                "--to", "backend-lead", "--session", "macbook-seo",
                "--no-wake", "MIN-119 seo work")
        run_cmd(self.tmp_path, "dispatch", "send", "--from", "orchestrator",
                "--to", "backend-lead", "--no-wake", "legacy untagged")

        seo = json.loads(run_cmd(
            self.tmp_path, "dispatch", "inbox", "backend-lead",
            "--session", "macbook-seo", "--json",
        ).stdout)
        self.assertEqual([m["body"] for m in seo], ["MIN-119 seo work"])

        # Unscoped (no session resolvable) and --all-sessions both give the global view.
        everything = json.loads(run_cmd(
            self.tmp_path, "dispatch", "inbox", "backend-lead",
            "--all-sessions", "--json",
        ).stdout)
        self.assertEqual(len(everything), 3)

    def test_status_open_loop_pairing_is_session_scoped(self):
        # A report from another session's same-named lead must NOT close this
        # session's request.
        req = json.loads(run_cmd(
            self.tmp_path, "dispatch", "send", "--from", "orchestrator",
            "--to", "backend-lead", "--task", "MIN-119",
            "--session", "macbook-seo", "--no-wake", "do seo thing",
        ).stdout)
        run_cmd(self.tmp_path, "dispatch", "send", "--from", "backend-lead",
                "--to", "orchestrator", "--kind", "report-done", "--task", "MIN-119",
                "--session", "macbook-heatmap", "--no-wake", "done elsewhere")

        seo_status = json.loads(run_cmd(
            self.tmp_path, "dispatch", "status", "--session", "macbook-seo", "--json",
        ).stdout)
        self.assertEqual([r["dispatch_id"] for r in seo_status["open"]],
                         [req["dispatch_id"]])

        # Same-session report DOES close it.
        run_cmd(self.tmp_path, "dispatch", "send", "--from", "backend-lead",
                "--to", "orchestrator", "--kind", "report-done",
                "--reply-to", req["dispatch_id"],
                "--session", "macbook-seo", "--no-wake", "done here")
        seo_status = json.loads(run_cmd(
            self.tmp_path, "dispatch", "status", "--session", "macbook-seo", "--json",
        ).stdout)
        self.assertEqual(seo_status["open"], [])

    def test_log_is_session_scoped(self):
        run_cmd(self.tmp_path, "dispatch", "send", "--from", "orchestrator",
                "--to", "qa-lead", "--session", "macbook-seo", "--no-wake", "seo-only-msg")
        run_cmd(self.tmp_path, "dispatch", "send", "--from", "orchestrator",
                "--to", "qa-lead", "--session", "macbook-heatmap", "--no-wake", "heatmap-msg")
        out = run_cmd(self.tmp_path, "dispatch", "log", "--session", "macbook-seo").stdout
        self.assertIn("seo-only-msg", out)
        self.assertNotIn("heatmap-msg", out)
        out_all = run_cmd(self.tmp_path, "dispatch", "log", "--all-sessions").stdout
        self.assertIn("seo-only-msg", out_all)
        self.assertIn("heatmap-msg", out_all)

    def test_unique_ids_across_sends(self):
        ids = set()
        for i in range(5):
            sent = json.loads(run_cmd(
                self.tmp_path, "dispatch", "send", "--from", "orchestrator",
                "--to", "qa-lead", "--no-wake", f"msg {i}",
            ).stdout)
            ids.add(sent["dispatch_id"])
        self.assertEqual(len(ids), 5)


class PeekTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_peek_without_session_fails_gracefully(self):
        # No JUMPCODE_TMUX_SESSION and no $TMUX (run_cmd clears both) -> no session.
        # peek must exit non-zero with a clear message, never a traceback.
        r = run_cmd(self.tmp_path, "peek", "backend-lead", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("session", (r.stdout + r.stderr).lower())

    def test_peek_accepts_optional_line_count(self):
        # The lines arg parses as an int and does not crash the CLI (still no
        # session here, so it exits gracefully rather than capturing anything).
        r = run_cmd(self.tmp_path, "peek", "backend-lead", "120", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
