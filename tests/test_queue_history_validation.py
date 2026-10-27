"""Validation tests for persisted task queue history."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from autopoesis.core import EvolutionError
from autopoesis.task_queue import (
    load_queue,
    record_outcome,
    record_outcome_file,
    record_verification_file,
    update_queue_file,
)


class QueueHistoryValidationTests(unittest.TestCase):
    def _write_queue(self, history):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "TASK_QUEUE.json"
        path.write_text(json.dumps({
            "version": 1,
            "items": [{"id": "TASK-1", "status": "DONE"}],
            "history": history,
        }), encoding="utf-8")
        return path

    def test_rejects_non_object_history_entry(self):
        with self.assertRaisesRegex(EvolutionError, "expected an object"):
            load_queue(self._write_queue(["not-an-event"]))

    def test_rejects_non_string_history_event_type(self):
        with self.assertRaisesRegex(EvolutionError, "unsupported event type"):
            load_queue(self._write_queue([{
                "event": ["UNKNOWN"],
                "task_id": "TASK-1",
                "at": "2026-01-01T00:00:00+00:00",
            }]))

    def test_rejects_unknown_history_event_type(self):
        with self.assertRaisesRegex(EvolutionError, "unsupported event type"):
            load_queue(self._write_queue([{
                "event": "UNKNOWN",
                "task_id": "TASK-1",
                "at": "2026-01-01T00:00:00+00:00",
            }]))

    def test_rejects_missing_task_id_or_timestamp(self):
        with self.assertRaisesRegex(EvolutionError, "task_id"):
            load_queue(self._write_queue([{
                "event": "CANDIDATE_ADDED",
                "at": "2026-01-01T00:00:00+00:00",
            }]))
        with self.assertRaisesRegex(EvolutionError, "at"):
            load_queue(self._write_queue([{
                "event": "CANDIDATE_ADDED",
                "task_id": "TASK-1",
                "at": "",
            }]))
        for invalid_timestamp in ("yesterday", "2026-01-01T00:00:00", "2026-99-99T00:00:00+00:00"):
            with self.subTest(at=invalid_timestamp):
                with self.assertRaisesRegex(EvolutionError, "ISO 8601|timezone offset"):
                    load_queue(self._write_queue([{
                        "event": "CANDIDATE_ADDED",
                        "task_id": "TASK-1",
                        "at": invalid_timestamp,
                    }]))

    def test_rejects_non_string_queue_status(self):
        # The task status is independently validated before history records.
        path = self._write_queue([])
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["items"][0]["status"] = ["DONE"]
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(EvolutionError, "Invalid status"):
            load_queue(path)

    def test_rejects_empty_task_ids_and_invalid_attempt_counts(self):
        for task_id in ("", "   "):
            with self.subTest(task_id=task_id):
                path = self._write_queue([])
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["items"][0]["id"] = task_id
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaisesRegex(EvolutionError, "non-empty string id"):
                    load_queue(path)

        for attempts in (-1, True, "1", None):
            with self.subTest(attempts=attempts):
                path = self._write_queue([])
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["items"][0]["attempts"] = attempts
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaisesRegex(EvolutionError, "attempts count"):
                    load_queue(path)

    def test_record_outcome_rejects_invalid_note_and_attempt_count(self):
        queue = {
            "version": 1,
            "items": [{"id": "TASK-1", "status": "OPEN", "attempts": 0}],
            "history": [],
        }
        with self.assertRaisesRegex(EvolutionError, "note must be a string"):
            record_outcome(queue, "TASK-1", "DONE", ["not a note"])
        queue["items"][0]["attempts"] = -1
        with self.assertRaisesRegex(EvolutionError, "attempts count"):
            record_outcome(queue, "TASK-1", "IN_PROGRESS")

    def test_rejects_invalid_status_transition_history(self):
        with self.assertRaisesRegex(EvolutionError, "destination status"):
            load_queue(self._write_queue([{
                "event": "STATUS_CHANGED",
                "task_id": "TASK-1",
                "from": "OPEN",
                "to": "UNKNOWN",
                "note": "bad status",
                "at": "2026-01-01T00:00:00+00:00",
            }]))

    def test_rejects_broken_transition_chain_even_when_final_status_matches(self):
        with self.assertRaisesRegex(EvolutionError, "transition chain mismatch"):
            load_queue(self._write_queue([
                {
                    "event": "STATUS_CHANGED",
                    "task_id": "TASK-1",
                    "from": "OPEN",
                    "to": "DONE",
                    "note": "first transition",
                    "at": "2026-01-01T00:00:00+00:00",
                },
                {
                    "event": "STATUS_CHANGED",
                    "task_id": "TASK-1",
                    "from": "OPEN",
                    "to": "DONE",
                    "note": "invalid second transition starts from old state",
                    "at": "2026-01-01T00:00:01+00:00",
                },
            ]))

    def test_rejects_queue_status_that_contradicts_latest_history(self):
        with self.assertRaisesRegex(EvolutionError, "Queue status/history mismatch"):
            load_queue(self._write_queue([{
                "event": "STATUS_CHANGED",
                "task_id": "TASK-1",
                "from": "OPEN",
                "to": "OPEN",
                "note": "history claims OPEN",
                "at": "2026-01-01T00:00:00+00:00",
            }]))

    def test_rejects_non_string_transition_note(self):
        with self.assertRaisesRegex(EvolutionError, "note must be a string"):
            load_queue(self._write_queue([{
                "event": "STATUS_CHANGED",
                "task_id": "TASK-1",
                "from": "OPEN",
                "to": "DONE",
                "note": ["not-a-string"],
                "at": "2026-01-01T00:00:00+00:00",
            }]))

    def test_accepts_persisted_verification_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "TASK_QUEUE.json"
            update_queue_file(path, [{
                "id": "TASK-1",
                "type": "proposal",
                "description": "test",
            }])
            record_verification_file(
                path,
                "TASK-1",
                "PASS",
                "GENERATED_TEST_EXECUTION",
                "a" * 64,
            )
            queue = load_queue(path)
            event = queue["history"][-1]
            self.assertEqual(event["event"], "VERIFICATION_RECORDED")
            self.assertEqual(event["verification_status"], "PASS")
            self.assertEqual(event["verification_level"], "GENERATED_TEST_EXECUTION")
            self.assertEqual(event["artifact_sha256"], "a" * 64)
            self.assertEqual(queue["items"][0]["status"], "OPEN")

    def test_rejects_invalid_persisted_verification_digest(self):
        with self.assertRaisesRegex(EvolutionError, "artifact_sha256"):
            load_queue(self._write_queue([{
                "event": "VERIFICATION_RECORDED",
                "task_id": "CORE-007",
                "verification_status": "PASS",
                "verification_level": "GENERATED_TEST_EXECUTION",
                "artifact_sha256": "not-a-digest",
                "at": "2026-01-01T00:00:00+00:00",
            }]))

    def test_rejects_non_string_persisted_verification_status(self):
        with self.assertRaisesRegex(EvolutionError, "invalid verification status"):
            load_queue(self._write_queue([{
                "event": "VERIFICATION_RECORDED",
                "task_id": "CORE-007",
                "verification_status": ["PASS"],
                "verification_level": "GENERATED_TEST_EXECUTION",
                "artifact_sha256": None,
                "at": "2026-01-01T00:00:00+00:00",
            }]))

    def test_verification_and_outcome_helpers_reject_non_string_status(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "TASK_QUEUE.json"
            update_queue_file(path, [{
                "id": "TASK-1",
                "type": "proposal",
                "description": "test",
            }])
            with self.assertRaisesRegex(EvolutionError, "Unsupported verification status"):
                record_verification_file(path, "TASK-1", ["PASS"], "GENERATED_TEST_EXECUTION")
            with self.assertRaisesRegex(EvolutionError, "Unsupported queue status"):
                record_outcome_file(path, "TASK-1", ["DONE"], "invalid status type")

    def test_accepts_history_written_by_queue_helpers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "TASK_QUEUE.json"
            update_queue_file(path, [{
                "id": "TASK-1",
                "type": "proposal",
                "description": "test",
            }])
            with self.assertRaisesRegex(EvolutionError, "without a matching latest PASS verification"):
                record_outcome_file(path, "TASK-1", "DONE", "must fail closed")

            record_verification_file(
                path,
                "TASK-1",
                "PASS",
                "GENERATED_TEST_EXECUTION",
                "b" * 64,
            )
            record_outcome_file(path, "TASK-1", "DONE", "test transition")
            queue = load_queue(path)
            self.assertEqual([event["event"] for event in queue["history"]], [
                "CANDIDATE_ADDED",
                "VERIFICATION_RECORDED",
                "STATUS_CHANGED",
            ])

    def test_verification_for_unknown_task_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "TASK_QUEUE.json"
            update_queue_file(path, [{"id": "TASK-1", "type": "proposal"}])
            with self.assertRaisesRegex(EvolutionError, "exactly one queued task"):
                record_verification_file(path, "UNKNOWN", "PASS", "unit")

    def test_stale_pass_from_previous_attempt_cannot_mark_task_done(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "TASK_QUEUE.json"
            update_queue_file(path, [{"id": "TASK-1", "type": "proposal"}])
            record_verification_file(path, "TASK-1", "PASS", "unit", "a" * 64)
            record_outcome_file(path, "TASK-1", "IN_PROGRESS", "begin a new attempt")
            with self.assertRaisesRegex(EvolutionError, "current attempt"):
                record_outcome_file(path, "TASK-1", "DONE", "stale PASS must not authorize DONE")
            record_verification_file(path, "TASK-1", "PASS", "unit", "b" * 64)
            record_outcome_file(path, "TASK-1", "DONE", "current attempt verified")
            queue = load_queue(path)
            evidence = [
                event for event in queue["history"]
                if event.get("event") == "VERIFICATION_RECORDED"
            ]
            self.assertEqual([event["attempt"] for event in evidence], [0, 1])
            self.assertEqual(queue["items"][0]["status"], "DONE")

    def test_latest_failed_verification_blocks_done_even_after_an_earlier_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "TASK_QUEUE.json"
            update_queue_file(path, [{"id": "TASK-1", "type": "proposal"}])
            record_verification_file(
                path, "TASK-1", "PASS", "GENERATED_TEST_EXECUTION", "d" * 64
            )
            record_verification_file(
                path, "TASK-1", "FAIL", "GENERATED_TEST_EXECUTION", "e" * 64
            )

            with self.assertRaisesRegex(EvolutionError, "without a matching latest PASS verification"):
                record_outcome_file(path, "TASK-1", "DONE", "stale PASS must not authorize DONE")

            queue = load_queue(path)
            self.assertEqual(queue["items"][0]["status"], "OPEN")
            self.assertEqual(queue["history"][-1]["verification_status"], "FAIL")

    def test_failed_atomic_replace_preserves_previous_queue_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "TASK_QUEUE.json"
            update_queue_file(path, [{"id": "TASK-1", "type": "proposal"}])
            record_verification_file(
                path,
                "TASK-1",
                "PASS",
                "GENERATED_TEST_EXECUTION",
                "c" * 64,
            )
            original_bytes = path.read_bytes()

            with patch("autopoesis.task_queue.os.replace", side_effect=OSError("disk error")):
                with self.assertRaisesRegex(OSError, "disk error"):
                    record_outcome_file(path, "TASK-1", "DONE", "must not partially persist")

            self.assertEqual(path.read_bytes(), original_bytes)
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])


    def test_missing_queue_file_returns_empty_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_path = Path(directory) / "missing" / "TASK_QUEUE.json"
            self.assertEqual(load_queue(missing_path), {
                "version": 1,
                "items": [],
                "history": [],
            })

    def test_queue_read_permission_error_fails_closed(self):
        path = Path("unreadable-TASK_QUEUE.json")
        with patch.object(Path, "read_text", side_effect=PermissionError("permission denied")):
            with self.assertRaisesRegex(EvolutionError, "Cannot read task queue"):
                load_queue(path)

    def test_queue_read_unicode_error_fails_closed(self):
        path = Path("invalid-encoding-TASK_QUEUE.json")
        with patch.object(Path, "read_text", side_effect=UnicodeError("invalid text")):
            with self.assertRaisesRegex(EvolutionError, "Cannot read task queue"):
                load_queue(path)


if __name__ == "__main__":
    unittest.main()
