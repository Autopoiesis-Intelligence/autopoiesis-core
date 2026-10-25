"""Tests for the bounded queue-cycle coordinator.

The PASS/FAIL handler in these tests is a controlled fixture that records
lease-bound evidence; it does not claim the sandbox executor ran here.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from autopoesis.queue_cycle import run_one_queue_cycle
from autopoesis.task_queue import (
    current_attempt,
    load_queue,
    record_verification_file,
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
        self.assertTrue(any(
            item.get("id") == "CYCLE-001" and item.get("reason") == "attempt limit reached"
            for item in result["deferred"]
        ))
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


if __name__ == "__main__":
    unittest.main()
