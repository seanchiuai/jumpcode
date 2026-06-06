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
    result = subprocess.run(
        [sys.executable, str(COCKPIT), *args],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        env=env,
    )
    if check and result.returncode != 0:
        raise AssertionError(f"command failed: {args}\nstdout={result.stdout}\nstderr={result.stderr}")
    return result


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class CockpitCliTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_run_start_records_current_run_and_ledger(self):
        result = run_cmd(self.tmp_path, "run", "start", "--goal", "Build orchestration primitives", "--participant", "orchestrator", "--participant", "backend-lead")
        payload = json.loads(result.stdout)

        self.assertEqual(payload["type"], "run.started")
        self.assertTrue(payload["run_id"].startswith("run-"))
        self.assertEqual(payload["goal"], "Build orchestration primitives")
        self.assertEqual(payload["participants"], ["orchestrator", "backend-lead"])

        state = self.tmp_path / ".agent-cockpit" / "state"
        self.assertEqual(json.loads((state / "current_run.json").read_text())["run_id"], payload["run_id"])
        self.assertEqual(read_jsonl(state / "runs.jsonl")[-1]["run_id"], payload["run_id"])

    def test_task_create_and_list_reconstruct_current_state(self):
        run = json.loads(run_cmd(self.tmp_path, "run", "start", "--goal", "Goal").stdout)
        created = json.loads(run_cmd(
            self.tmp_path,
            "task", "create",
            "--title", "Implement mailbox",
            "--owner", "backend-lead",
            "--description", "JSONL backed messages",
            "--criteria", "Inbox lists unread messages",
            "--criteria", "Replies preserve task id",
        ).stdout)

        self.assertEqual(created["type"], "task.created")
        self.assertEqual(created["run_id"], run["run_id"])
        self.assertEqual(created["status"], "assigned")
        self.assertEqual(created["acceptance_criteria"], ["Inbox lists unread messages", "Replies preserve task id"])

        run_cmd(self.tmp_path, "task", "start", created["task_id"], "--by", "backend-lead")
        tasks = json.loads(run_cmd(self.tmp_path, "task", "list", "--json").stdout)
        self.assertEqual(tasks[0]["task_id"], created["task_id"])
        self.assertEqual(tasks[0]["status"], "in_progress")
        self.assertEqual(tasks[0]["owner"], "backend-lead")

    def test_mail_send_inbox_reply_and_show(self):
        run_cmd(self.tmp_path, "run", "start", "--goal", "Goal")
        task = json.loads(run_cmd(self.tmp_path, "task", "create", "--title", "Wire mailbox", "--owner", "backend-lead").stdout)

        sent = json.loads(run_cmd(
            self.tmp_path,
            "mail", "send",
            "--from", "orchestrator",
            "--to", "backend-lead",
            "--task", task["task_id"],
            "--subject", "Please implement",
            "Please implement the mailbox.",
        ).stdout)
        self.assertTrue(sent["message_id"].startswith("msg-"))
        self.assertEqual(sent["thread_id"], task["task_id"])

        inbox = json.loads(run_cmd(self.tmp_path, "mail", "inbox", "backend-lead", "--json").stdout)
        self.assertEqual([m["message_id"] for m in inbox], [sent["message_id"]])

        reply = json.loads(run_cmd(
            self.tmp_path,
            "mail", "reply",
            "--from", "backend-lead",
            "--to", "orchestrator",
            "--task", task["task_id"],
            "--reply-to", sent["message_id"],
            "Working on it.",
        ).stdout)
        self.assertEqual(reply["kind"], "reply")
        self.assertEqual(reply["reply_to"], sent["message_id"])

        shown = json.loads(run_cmd(self.tmp_path, "mail", "show", sent["message_id"], "--json").stdout)
        self.assertEqual(shown["body"], "Please implement the mailbox.")

    def test_report_done_updates_task_and_records_machine_readable_report(self):
        run_cmd(self.tmp_path, "run", "start", "--goal", "Goal")
        task = json.loads(run_cmd(self.tmp_path, "task", "create", "--title", "Build reports", "--owner", "backend-lead").stdout)

        report = json.loads(run_cmd(
            self.tmp_path,
            "report", "done", task["task_id"],
            "--from", "backend-lead",
            "--summary", "Implemented report command",
            "--work", "Added report done",
            "--file", ".agent-cockpit/bin/cockpit",
            "--check", "python -m py_compile .agent-cockpit/bin/cockpit:pass:compiled",
            "--concern", "No eval scoring yet",
            "--next", "Have QA run smoke test",
        ).stdout)

        self.assertEqual(report["type"], "report.done")
        self.assertEqual(report["checks_run"], [{"command": "python -m py_compile .agent-cockpit/bin/cockpit", "result": "pass", "summary": "compiled"}])

        tasks = json.loads(run_cmd(self.tmp_path, "task", "list", "--json").stdout)
        self.assertEqual(tasks[0]["status"], "done")

    def test_run_summary_includes_tasks_messages_and_reports(self):
        run_cmd(self.tmp_path, "run", "start", "--goal", "Goal", "--participant", "orchestrator")
        task = json.loads(run_cmd(self.tmp_path, "task", "create", "--title", "T", "--owner", "backend-lead").stdout)
        run_cmd(self.tmp_path, "mail", "send", "--from", "orchestrator", "--to", "backend-lead", "--task", task["task_id"], "Do T")
        run_cmd(self.tmp_path, "report", "blocked", task["task_id"], "--from", "backend-lead", "--blocker", "Need decision", "--why", "Ambiguous scope", "--tried", "Read task", "--need-from", "orchestrator")

        summary = json.loads(run_cmd(self.tmp_path, "run", "summary", "--json").stdout)
        self.assertEqual(summary["goal"], "Goal")
        self.assertEqual(summary["task_counts"], {"blocked": 1})
        self.assertEqual(summary["message_count"], 1)
        self.assertEqual(summary["report_count"], 1)


if __name__ == "__main__":
    unittest.main()
