"""A1 adversarial tests: queue state must fail closed and never lose updates."""

import json
import multiprocessing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from autopoesis.core import EvolutionError
from autopoesis.task_queue import (
    advance_task_file,
    load_queue,
    record_verification_file,
    update_queue_file,
)


WRITERS = 8


def _add_candidate(path_text, candidate_id, start, results):
    start.wait()
    try:
        update_queue_file(Path(path_text), [{"id": candidate_id, "type": "proposal"}])
    except EvolutionError as exc:
        results.put((candidate_id, "rejected", str(exc)))
    else:
        results.put((candidate_id, "written", ""))


class QueueDurabilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "TASK_QUEUE.json"

    def _seed(self):
        update_queue_file(self.path, [{"id": "TASK-1", "type": "proposal"}])
        return self.path.read_bytes()

    def test_malformed_json_fails_closed_and_is_not_overwritten(self):
        self.path.write_text('{"version": 2, "items": [', encoding="utf-8")
        original = self.path.read_bytes()
        with self.assertRaisesRegex(EvolutionError, "Cannot read task queue"):
            load_queue(self.path)
        with self.assertRaisesRegex(EvolutionError, "Cannot read task queue"):
            update_queue_file(self.path, [{"id": "TASK-2", "type": "proposal"}])
        self.assertEqual(self.path.read_bytes(), original)

    def test_directory_in_place_of_queue_fails_closed(self):
        self.path.mkdir()
        with self.assertRaisesRegex(EvolutionError, "Cannot read task queue"):
            load_queue(self.path)

    def test_failed_write_or_flush_preserves_previous_queue_bytes(self):
        original = self._seed()
        for target in ("autopoesis.task_queue.os.fsync", "autopoesis.task_queue.os.fdopen"):
            with self.subTest(target=target):
                with patch(target, side_effect=OSError("disk full")):
                    with self.assertRaisesRegex(OSError, "disk full"):
                        advance_task_file(self.path, "TASK-1", "SELECTED", "must not persist", owner="unit-test")
                self.assertEqual(self.path.read_bytes(), original)
                self.assertEqual(list(self.path.parent.glob(f".{self.path.name}.*.tmp")), [])

    def test_failed_verification_write_preserves_previous_queue_bytes(self):
        original = self._seed()
        with patch("autopoesis.task_queue.os.replace", side_effect=OSError("disk error")):
            with self.assertRaisesRegex(OSError, "disk error"):
                record_verification_file(self.path, "CORE-007", "PASS", "unit")
        self.assertEqual(self.path.read_bytes(), original)

    def test_concurrent_writers_never_lose_an_acknowledged_update(self):
        # Every writer that returns successfully must find its update in the
        # final queue. A writer may be rejected, but it must never "succeed"
        # and then be silently overwritten by another writer.
        update_queue_file(self.path, [])
        context = multiprocessing.get_context("fork")
        start = context.Event()
        results = context.Queue()
        processes = [
            context.Process(
                target=_add_candidate,
                args=(str(self.path), f"TASK-{index}", start, results),
            )
            for index in range(WRITERS)
        ]
        for process in processes:
            process.start()
        start.set()
        outcomes = [results.get(timeout=30) for _ in processes]
        for process in processes:
            process.join(timeout=30)
            self.assertEqual(process.exitcode, 0)

        written = {candidate for candidate, outcome, _ in outcomes if outcome == "written"}
        stored = {item["id"] for item in load_queue(self.path)["items"]}
        self.assertTrue(written, "at least one writer must succeed")
        self.assertEqual(stored, written)
        for _, outcome, message in outcomes:
            if outcome == "rejected":
                self.assertIn("locked", message)

    def test_writer_is_rejected_while_another_writer_holds_the_queue(self):
        from autopoesis.task_queue import queue_write_lock

        original = self._seed()
        with queue_write_lock(self.path):
            with self.assertRaisesRegex(EvolutionError, "locked by another writer"):
                advance_task_file(self.path, "TASK-1", "SELECTED", "concurrent", owner="unit-test")
        self.assertEqual(self.path.read_bytes(), original)
        advance_task_file(self.path, "TASK-1", "SELECTED", "after release", owner="unit-test")
        self.assertEqual(load_queue(self.path)["items"][0]["status"], "SELECTED")


if __name__ == "__main__":
    unittest.main()
