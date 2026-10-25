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
