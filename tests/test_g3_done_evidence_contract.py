"""G3 regression tests: DONE must require matching verification evidence."""

import tempfile
import unittest
from pathlib import Path

from autopoesis.core import EvolutionError
from autopoesis.task_queue import (
    record_outcome,
    record_outcome_file,
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
            path = self._queue_path(directory)
            from autopoesis.task_queue import load_queue

            queue = load_queue(path)
            with self.assertRaisesRegex(EvolutionError, "verification|evidence|DONE"):
                record_outcome(queue, "G3-TASK-1", "DONE", "no verification evidence")

    def test_file_transition_rejects_done_without_matching_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._queue_path(directory)
            with self.assertRaisesRegex(EvolutionError, "verification|evidence|DONE"):
                record_outcome_file(path, "G3-TASK-1", "DONE", "no verification evidence")


if __name__ == "__main__":
    unittest.main()
