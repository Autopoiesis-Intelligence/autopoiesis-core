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
            with self.assertRaisesRegex(EvolutionError, "verification|evidence|DONE"):
                record_outcome(queue, "G3-TASK-1", "DONE", "no verification evidence")

    def test_file_transition_rejects_done_without_matching_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._queue_path(directory)
            with self.assertRaisesRegex(EvolutionError, "verification|evidence|DONE"):
                record_outcome_file(path, "G3-TASK-1", "DONE", "no verification evidence")

    def test_pass_for_different_task_does_not_authorize_done(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._queue_path(directory)
            record_verification_file(
                path, "UNRELATED-TASK", "PASS", "GENERATED_TEST_EXECUTION", "a" * 64
            )
            with self.assertRaisesRegex(EvolutionError, "verification|evidence|DONE"):
                record_outcome_file(path, "G3-TASK-1", "DONE", "unrelated PASS must not authorize")

    def test_unbound_pass_for_same_task_does_not_authorize_done(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._queue_path(directory)
            record_verification_file(
                path, "G3-TASK-1", "PASS", "GENERATED_TEST_EXECUTION", "a" * 64
            )
            with self.assertRaisesRegex(EvolutionError, "verification|evidence|DONE"):
                record_outcome_file(path, "G3-TASK-1", "DONE", "PASS lacks attempt/lease/commit/tree binding")


if __name__ == "__main__":
    unittest.main()
