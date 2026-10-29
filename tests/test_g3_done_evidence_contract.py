"""G3 regression tests: DONE must require matching verification evidence."""

import tempfile
import unittest
from pathlib import Path

from autopoesis.core import EvolutionError
from autopoesis.task_queue import (
    load_queue,
    record_outcome,
    record_outcome_file,
    record_verification_file,
    update_queue_file,
)


class DoneEvidenceContractTests(unittest.TestCase):
    COMMIT = "1" * 40
    TREE = "2" * 40
    LEASE = "c" * 64

    def _start_attempt(self, path: Path) -> None:
        record_outcome_file(
            path, "G3-TASK-1", "IN_PROGRESS", "start test attempt",
            lease_fingerprint=self.LEASE, commit_sha=self.COMMIT, tree_sha=self.TREE,
        )

    def _queue_path(self, directory: str) -> Path:
        path = Path(directory) / "TASK_QUEUE.json"
        update_queue_file(path, [{
            "id": "G3-TASK-1",
            "type": "proposal",
            "source": "autopoesis/example.py",
            "evidence": "G3 regression fixture",
            "description": "A task that must not be marked DONE without proof.",
        }])
        return path

    def test_in_memory_transition_rejects_done_without_matching_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            queue = load_queue(self._queue_path(directory))
            queue = record_outcome(
                queue, "G3-TASK-1", "IN_PROGRESS", "start test attempt",
                lease_fingerprint=self.LEASE, commit_sha=self.COMMIT, tree_sha=self.TREE,
            )
            with self.assertRaisesRegex(EvolutionError, "verification|evidence|DONE"):
                record_outcome(queue, "G3-TASK-1", "DONE", "no verification evidence")

    def test_file_transition_rejects_done_without_matching_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._queue_path(directory)
            self._start_attempt(path)
            with self.assertRaisesRegex(EvolutionError, "verification|evidence|DONE"):
                record_outcome_file(path, "G3-TASK-1", "DONE", "no verification evidence")

    def test_pass_for_different_task_does_not_authorize_done(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._queue_path(directory)
            self._start_attempt(path)
            record_verification_file(
                path, "UNRELATED-TASK", "PASS", "GENERATED_TEST_EXECUTION", "a" * 64,
                attempt=1, lease_fingerprint=self.LEASE, commit_sha=self.COMMIT, tree_sha=self.TREE,
            )
            with self.assertRaisesRegex(EvolutionError, "verification|evidence|DONE"):
                record_outcome_file(path, "G3-TASK-1", "DONE", "unrelated PASS must not authorize")

    def test_matching_bound_pass_authorizes_done(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._queue_path(directory)
            self._start_attempt(path)
            record_verification_file(
                path, "G3-TASK-1", "PASS", "GENERATED_TEST_EXECUTION", "a" * 64,
                attempt=1, lease_fingerprint=self.LEASE, commit_sha=self.COMMIT, tree_sha=self.TREE,
            )
            result = record_outcome_file(path, "G3-TASK-1", "DONE", "verified")
            self.assertEqual(result["status"], "DONE")
            self.assertEqual(load_queue(path)["items"][0]["status"], "DONE")


    def test_mismatched_attempt_lease_commit_or_tree_does_not_authorize_done(self):
        mismatches = [
            {"attempt": 2, "lease_fingerprint": LEASE, "commit_sha": COMMIT, "tree_sha": TREE},
            {"attempt": 1, "lease_fingerprint": "d" * 64, "commit_sha": COMMIT, "tree_sha": TREE},
            {"attempt": 1, "lease_fingerprint": LEASE, "commit_sha": "3" * 40, "tree_sha": TREE},
            {"attempt": 1, "lease_fingerprint": LEASE, "commit_sha": COMMIT, "tree_sha": "4" * 40},
        ]
        for binding in mismatches:
            with self.subTest(binding=binding), tempfile.TemporaryDirectory() as directory:
                path = self._queue_path(directory)
                self._start_attempt(path)
                record_verification_file(
                    path, "G3-TASK-1", "PASS", "GENERATED_TEST_EXECUTION", "a" * 64,
                    **binding,
                )
                with self.assertRaisesRegex(EvolutionError, "verification|evidence|DONE"):
                    record_outcome_file(path, "G3-TASK-1", "DONE", "mismatched evidence")

    def test_later_fail_for_same_binding_revokes_prior_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._queue_path(directory)
            self._start_attempt(path)
            binding = {
                "attempt": 1, "lease_fingerprint": self.LEASE,
                "commit_sha": self.COMMIT, "tree_sha": self.TREE,
            }
            record_verification_file(
                path, "G3-TASK-1", "PASS", "GENERATED_TEST_EXECUTION", "a" * 64,
                **binding,
            )
            record_verification_file(
                path, "G3-TASK-1", "FAIL", "GENERATED_TEST_EXECUTION", "b" * 64,
                **binding,
            )
            with self.assertRaisesRegex(EvolutionError, "verification|evidence|DONE"):
                record_outcome_file(path, "G3-TASK-1", "DONE", "later FAIL supersedes PASS")

    def test_unbound_pass_for_same_task_does_not_authorize_done(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._queue_path(directory)
            self._start_attempt(path)
            record_verification_file(
                path, "G3-TASK-1", "PASS", "GENERATED_TEST_EXECUTION", "a" * 64
            )
            with self.assertRaisesRegex(EvolutionError, "verification|evidence|DONE"):
                record_outcome_file(path, "G3-TASK-1", "DONE", "PASS lacks attempt/lease/commit/tree binding")


if __name__ == "__main__":
    unittest.main()
