"""Tests for the bounded queue-cycle coordinator.

The PASS/FAIL handler in these tests is a controlled fixture that records
lease-bound evidence; it does not claim the sandbox executor ran here.
"""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from autopoesis.queue_cycle import run_one_queue_cycle
from autopoesis.task_queue import (
    current_attempt,
    load_queue,
    advance_task_file,
    record_verification_file,
    select_next_task_file,
    update_queue_file,
)
import autopoesis.queue_cycle as queue_cycle


class BoundedQueueCycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.queue_path = Path(self.temp.name) / "TASK_QUEUE.json"
        update_queue_file(
            self.queue_path,
            [{
                "id": "CYCLE-001",
                "type": "verify_test_patch_sandbox",
                "source": "autopoesis/task_queue.py",
                "evidence": "unit-test fixture for bounded coordinator",
                "description": "Exercise one governed queue cycle.",
            }],
        )

    def _fixture_handler(self, task, queue_path, verification_status="PASS", reported_revision=None):
        task_id = task["queue_task_id"]
        revision = queue_cycle.source_tree_digest(queue_cycle.ROOT / "autopoesis")
        record_verification_file(
            queue_path,
            task_id,
            verification_status,
            "UNIT_TEST_FIXTURE",
            source=task["source"],
            attempt=current_attempt(queue_path, task_id),
            revision=revision,
            token=task["lease_token"],
        )
        return {
            "id": task["id"],
            "type": task["type"],
            "status": "PASS" if verification_status == "PASS" else "FAIL",
            "result": {
                "verification_status": verification_status,
                "source_tree_sha256": reported_revision or revision,
            },
        }

    def test_pass_evidence_completes_only_the_selected_task(self):
        with mock.patch.object(
            queue_cycle, "execute_task",
            side_effect=lambda task, path: self._fixture_handler(task, path, "PASS"),
        ):
            result = run_one_queue_cycle(self.queue_path)

        self.assertEqual(result["status"], "COMPLETED")
        queue = load_queue(self.queue_path)
        item = next(item for item in queue["items"] if item["id"] == "CYCLE-001")
        self.assertEqual(item["status"], "DONE")
        self.assertEqual(item["attempts"], 1)
        self.assertTrue(any(
            event.get("event") == "VERIFICATION_RECORDED"
            and event.get("task_id") == "CYCLE-001"
            and event.get("verification_status") == "PASS"
            for event in queue["history"]
        ))

    def test_fail_evidence_reopens_task_without_done(self):
        with mock.patch.object(
            queue_cycle, "execute_task",
            side_effect=lambda task, path: self._fixture_handler(task, path, "FAIL"),
        ):
            result = run_one_queue_cycle(self.queue_path)

        self.assertEqual(result["status"], "RETRYABLE_FAILURE")
        queue = load_queue(self.queue_path)
        item = next(item for item in queue["items"] if item["id"] == "CYCLE-001")
        self.assertEqual(item["status"], "OPEN")
        self.assertEqual(item["attempts"], 1)
        self.assertFalse(any(
            event.get("event") == "STATUS_CHANGED"
            and event.get("task_id") == "CYCLE-001"
            and event.get("to") == "DONE"
            for event in queue["history"]
        ))

    def test_selection_exception_returns_recovery_required(self):
        with mock.patch.object(
            queue_cycle,
            "select_next_task_file",
            side_effect=OSError("simulated queue lock failure"),
        ):
            result = run_one_queue_cycle(self.queue_path)

        self.assertEqual(result["status"], "RECOVERY_REQUIRED")
        self.assertIsNone(result["task_id"])
        self.assertFalse(result["reopened"])
        self.assertIn("simulated queue lock failure", result["reason"])
        self.assertEqual(load_queue(self.queue_path)["items"][0]["status"], "OPEN")

    def test_selected_state_reload_exception_returns_recovery_required(self):
        with mock.patch.object(
            queue_cycle,
            "load_queue",
            side_effect=OSError("simulated read failure"),
        ):
            result = run_one_queue_cycle(self.queue_path)

        self.assertEqual(result["status"], "RECOVERY_REQUIRED")
        self.assertEqual(result["task_id"], "CYCLE-001")
        self.assertFalse(result["reopened"])
        self.assertIn("simulated read failure", result["reason"])
        # The independent test import remains usable to inspect persisted state.
        self.assertEqual(load_queue(self.queue_path)["items"][0]["status"], "SELECTED")

    def test_missing_selected_lease_reports_recovery_required_without_rejection(self):
        # First create a real persisted selection/lease. Then simulate the
        # selector losing its lease metadata; the coordinator must not claim
        # REJECTED or mutate the still-SELECTED queue item.
        queue_cycle.select_next_task_file(
            self.queue_path,
            queue_cycle.OWNER,
            types=queue_cycle.SUPPORTED_CYCLE_TYPES,
        )
        before = self.queue_path.read_bytes()
        with mock.patch.object(
            queue_cycle,
            "select_next_task_file",
            return_value={"selected": "CYCLE-001", "lease": None, "deferred": []},
        ):
            result = run_one_queue_cycle(self.queue_path)

        self.assertEqual(result["status"], "RECOVERY_REQUIRED")
        self.assertFalse(result["reopened"])
        self.assertNotEqual(result["status"], "REJECTED")
        queue = load_queue(self.queue_path)
        item = next(item for item in queue["items"] if item["id"] == "CYCLE-001")
        self.assertEqual(item["status"], "SELECTED")
        self.assertEqual(self.queue_path.read_bytes(), before)

    def test_failed_recovery_transition_reports_recovery_required(self):
        original_advance = queue_cycle.advance_task_file

        def fail_reopen(path, task_id, status, *args, **kwargs):
            if status == "OPEN":
                raise RuntimeError("simulated lease rejection")
            return original_advance(path, task_id, status, *args, **kwargs)

        with (
            mock.patch.object(queue_cycle, "execute_task", side_effect=RuntimeError("executor failed")),
            mock.patch.object(queue_cycle, "advance_task_file", side_effect=fail_reopen),
        ):
            result = run_one_queue_cycle(self.queue_path)

        self.assertEqual(result["status"], "RECOVERY_REQUIRED")
        self.assertFalse(result["reopened"])
        queue = load_queue(self.queue_path)
        item = next(item for item in queue["items"] if item["id"] == "CYCLE-001")
        self.assertEqual(item["status"], "IN_PROGRESS")
        self.assertNotEqual(result["status"], "REJECTED")

    def test_repeated_failures_reject_after_max_attempts(self):
        expected = ["RETRYABLE_FAILURE", "RETRYABLE_FAILURE", "REJECTED"]
        for expected_status in expected:
            with mock.patch.object(
                queue_cycle, "execute_task",
                side_effect=lambda task, path: self._fixture_handler(task, path, "FAIL"),
            ):
                result = run_one_queue_cycle(self.queue_path)
            self.assertEqual(result["status"], expected_status)

        queue = load_queue(self.queue_path)
        item = next(item for item in queue["items"] if item["id"] == "CYCLE-001")
        self.assertEqual(item["status"], "REJECTED")
        self.assertEqual(item["attempts"], 3)
        rejected_events = [
            event for event in queue["history"]
            if event.get("event") == "STATUS_CHANGED"
            and event.get("task_id") == "CYCLE-001"
            and event.get("to") == "REJECTED"
        ]
        self.assertEqual(len(rejected_events), 1)

        # A fourth call must not misreport the terminal task as executable work.
        before = self.queue_path.read_bytes()
        result = run_one_queue_cycle(self.queue_path)
        self.assertEqual(result["status"], "NO_WORK")
        # REJECTED is terminal: selection skips it instead of deferring it as waiting work.
        self.assertNotIn("CYCLE-001", [item.get("id") for item in result["deferred"]])
        self.assertEqual(self.queue_path.read_bytes(), before)

    def test_mismatched_executor_digest_reopens_task_without_done(self):
        with mock.patch.object(
            queue_cycle, "execute_task",
            side_effect=lambda task, path: self._fixture_handler(
                task, path, "PASS", reported_revision="f" * 64
            ),
        ):
            result = run_one_queue_cycle(self.queue_path)

        self.assertEqual(result["status"], "RETRYABLE_FAILURE")
        self.assertIn("mismatched", result["reason"])
        queue = load_queue(self.queue_path)
        item = next(item for item in queue["items"] if item["id"] == "CYCLE-001")
        self.assertEqual(item["status"], "OPEN")
        self.assertFalse(any(
            event.get("event") == "STATUS_CHANGED"
            and event.get("task_id") == "CYCLE-001"
            and event.get("to") == "DONE"
            for event in queue["history"]
        ))

    def test_missing_executor_digest_reopens_task_without_done(self):
        def handler_without_digest(task, path):
            result = self._fixture_handler(task, path, "PASS")
            result["result"].pop("source_tree_sha256", None)
            return result

        with mock.patch.object(queue_cycle, "execute_task", side_effect=handler_without_digest):
            result = run_one_queue_cycle(self.queue_path)

        self.assertEqual(result["status"], "RETRYABLE_FAILURE")
        self.assertIn("missing or mismatched", result["reason"])
        queue = load_queue(self.queue_path)
        item = next(item for item in queue["items"] if item["id"] == "CYCLE-001")
        self.assertEqual(item["status"], "OPEN")
        self.assertFalse(any(
            event.get("event") == "STATUS_CHANGED"
            and event.get("task_id") == "CYCLE-001"
            and event.get("to") == "DONE"
            for event in queue["history"]
        ))

    def test_real_executor_sandbox_cycle_completes_with_bound_evidence(self):
        # Integration path: do not mock execute_task. The real executor creates
        # a temporary package copy, runs the generated import test, and records
        # lease-bound verification evidence into this queue.
        result = run_one_queue_cycle(self.queue_path)

        self.assertEqual(result["status"], "COMPLETED", result)
        self.assertEqual(result["verification_status"], "PASS")
        execution = result["execution"]
        self.assertEqual(execution["result"]["verification_status"], "PASS")
        self.assertTrue(execution["result"]["source_package_copied"])
        self.assertTrue(execution["result"]["generated_code_executed"])
        self.assertFalse(execution["result"]["repository_modified"])
        self.assertEqual(execution["result"]["source_tree_sha256"], result["revision"])

        queue = load_queue(self.queue_path)
        item = next(item for item in queue["items"] if item["id"] == "CYCLE-001")
        self.assertEqual(item["status"], "DONE")
        self.assertEqual(item["attempts"], 1)
        passing_events = [
            event for event in queue["history"]
            if event.get("event") == "VERIFICATION_RECORDED"
            and event.get("task_id") == "CYCLE-001"
            and event.get("verification_status") == "PASS"
        ]
        self.assertGreaterEqual(len(passing_events), 1)
        self.assertTrue(all(event.get("revision") == result["revision"] for event in passing_events))

    def test_no_supported_work_does_not_mutate_queue(self):
        unsupported_path = Path(self.temp.name) / "unsupported.json"
        update_queue_file(
            unsupported_path,
            [{
                "id": "UNSUPPORTED-001",
                "type": "proposal",
                "source": "autopoesis/task_queue.py",
                "evidence": "not handled by the bounded verifier",
                "description": "Should be deferred, not executed.",
            }],
        )
        before = unsupported_path.read_bytes()
        result = run_one_queue_cycle(unsupported_path)
        self.assertEqual(result["status"], "NO_WORK")
        self.assertEqual(unsupported_path.read_bytes(), before)
        self.assertEqual(result["deferred"][0]["id"], "UNSUPPORTED-001")


    def test_done_write_failure_before_persisting_does_not_report_completed(self):
        original_advance = queue_cycle.advance_task_file

        def fail_before_done(path, task_id, status, *args, **kwargs):
            if status == "DONE":
                raise OSError("simulated failure before DONE persistence")
            return original_advance(path, task_id, status, *args, **kwargs)

        with (
            mock.patch.object(
                queue_cycle, "execute_task",
                side_effect=lambda task, path: self._fixture_handler(task, path, "PASS"),
            ),
            mock.patch.object(queue_cycle, "advance_task_file", side_effect=fail_before_done),
        ):
            result = run_one_queue_cycle(self.queue_path)

        self.assertNotEqual(result["status"], "COMPLETED")
        self.assertEqual(result["status"], "RETRYABLE_FAILURE")
        queue = load_queue(self.queue_path)
        item = next(item for item in queue["items"] if item["id"] == "CYCLE-001")
        self.assertEqual(item["status"], "OPEN")
        self.assertFalse(any(
            event.get("event") == "STATUS_CHANGED"
            and event.get("task_id") == "CYCLE-001"
            and event.get("to") == "DONE"
            for event in queue["history"]
        ))

    def test_done_write_persists_then_raises_is_reported_conservatively(self):
        original_advance = queue_cycle.advance_task_file

        def persist_done_then_raise(path, task_id, status, *args, **kwargs):
            result = original_advance(path, task_id, status, *args, **kwargs)
            if status == "DONE":
                raise OSError("simulated lost acknowledgement after DONE persistence")
            return result

        with (
            mock.patch.object(
                queue_cycle, "execute_task",
                side_effect=lambda task, path: self._fixture_handler(task, path, "PASS"),
            ),
            mock.patch.object(queue_cycle, "advance_task_file", side_effect=persist_done_then_raise),
        ):
            result = run_one_queue_cycle(self.queue_path)

        # The coordinator must not invent success from the exception. The
        # terminal persisted state and lease-bound PASS evidence remain inspectable.
        self.assertEqual(result["status"], "RECOVERY_REQUIRED")
        queue = load_queue(self.queue_path)
        item = next(item for item in queue["items"] if item["id"] == "CYCLE-001")
        self.assertEqual(item["status"], "DONE")
        self.assertTrue(any(
            event.get("event") == "VERIFICATION_RECORDED"
            and event.get("task_id") == "CYCLE-001"
            and event.get("verification_status") == "PASS"
            for event in queue["history"]
        ))
        before = self.queue_path.read_bytes()
        follow_up = run_one_queue_cycle(self.queue_path)
        self.assertEqual(follow_up["status"], "NO_WORK")
        self.assertEqual(self.queue_path.read_bytes(), before)


    def test_cycle_recovers_an_expired_lease_left_by_a_crashed_cycle(self):
        # A cycle killed after IN_PROGRESS (runner timeout, OOM) leaves its lease behind.
        # Once that lease expires, the next cycle must recover it instead of reporting
        # "work already active" forever.
        crashed_at = datetime.now(timezone.utc) - timedelta(days=2)
        selection = select_next_task_file(self.queue_path, queue_cycle.OWNER, now=crashed_at)
        advance_task_file(
            self.queue_path, "CYCLE-001", "IN_PROGRESS", "cycle that later crashed",
            owner=queue_cycle.OWNER, token=selection["lease"]["token"], now=crashed_at,
        )
        with mock.patch.object(
            queue_cycle, "execute_task",
            side_effect=lambda task, path: self._fixture_handler(task, path, "PASS"),
        ):
            result = run_one_queue_cycle(self.queue_path)
        self.assertEqual(result["status"], "COMPLETED")
        item = next(item for item in load_queue(self.queue_path)["items"] if item["id"] == "CYCLE-001")
        self.assertEqual(item["status"], "DONE")
        self.assertEqual(item["attempts"], 2)

    def test_cycle_leaves_an_unexpired_lease_alone(self):
        selection = select_next_task_file(self.queue_path, "another-holder")
        before = self.queue_path.read_bytes()
        result = run_one_queue_cycle(self.queue_path)
        self.assertEqual(result["status"], "NO_WORK")
        self.assertIn("work already active", result["reason"])
        self.assertEqual(self.queue_path.read_bytes(), before)
        self.assertTrue(selection["lease"]["token"])


    def test_expired_lease_on_the_last_attempt_ends_rejected_not_deferred(self):
        # Two failed cycles, then a third that crashes after IN_PROGRESS: the task has used
        # every attempt, so recovery must end it REJECTED instead of parking it in OPEN.
        for _ in range(2):
            with mock.patch.object(
                queue_cycle, "execute_task",
                side_effect=lambda task, path: self._fixture_handler(task, path, "FAIL"),
            ):
                self.assertEqual(run_one_queue_cycle(self.queue_path)["status"], "RETRYABLE_FAILURE")
        crashed_at = datetime.now(timezone.utc) - timedelta(days=2)
        selection = select_next_task_file(self.queue_path, queue_cycle.OWNER, now=crashed_at)
        advance_task_file(
            self.queue_path, "CYCLE-001", "IN_PROGRESS", "third cycle that later crashed",
            owner=queue_cycle.OWNER, token=selection["lease"]["token"], now=crashed_at,
        )
        result = run_one_queue_cycle(self.queue_path)
        self.assertEqual(result["status"], "NO_WORK")
        self.assertEqual(result["rejected_after_recovery"], ["CYCLE-001"])
        item = next(item for item in load_queue(self.queue_path)["items"] if item["id"] == "CYCLE-001")
        self.assertEqual(item["status"], "REJECTED")
        self.assertEqual(item["attempts"], 3)
        self.assertNotIn("CYCLE-001", [entry.get("id") for entry in result["deferred"]])


    def test_command_line_runs_one_cycle_and_maps_the_outcome_to_an_exit_code(self):
        import io
        import json
        from contextlib import redirect_stdout

        out = io.StringIO()
        with mock.patch.object(
            queue_cycle, "execute_task",
            side_effect=lambda task, path: self._fixture_handler(task, path, "FAIL"),
        ), redirect_stdout(out):
            code = queue_cycle.main(["--queue", str(self.queue_path)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out.getvalue())["status"], "RETRYABLE_FAILURE")

        out = io.StringIO()
        with mock.patch.object(
            queue_cycle, "execute_task",
            side_effect=lambda task, path: self._fixture_handler(task, path, "PASS"),
        ), redirect_stdout(out):
            code = queue_cycle.main(["--queue", str(self.queue_path)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "COMPLETED")

        before = self.queue_path.read_bytes()
        out = io.StringIO()
        with redirect_stdout(out):
            code = queue_cycle.main(["--queue", str(self.queue_path)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "NO_WORK")
        self.assertEqual(self.queue_path.read_bytes(), before)

    def test_command_line_refuses_a_missing_queue_file_instead_of_reporting_no_work(self):
        import io
        import json
        from contextlib import redirect_stdout

        missing = self.queue_path.parent / "no-such-queue.json"
        out = io.StringIO()
        with redirect_stdout(out):
            code = queue_cycle.main(["--queue", str(missing)])
        self.assertEqual(code, 3)
        self.assertEqual(json.loads(out.getvalue())["status"], "RECOVERY_REQUIRED")
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
