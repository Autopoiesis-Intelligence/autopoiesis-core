"""Validation tests for persisted task queue history."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from autopoesis.core import EvolutionError
from autopoesis.task_queue import (
    advance_task,
    advance_task_file,
    load_queue,
    record_verification_file,
    update_queue_file,
)


class QueueHistoryValidationTests(unittest.TestCase):
    def _write_queue(self, history):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "TASK_QUEUE.json"
        path.write_text(json.dumps({
            "version": 3,
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
            "version": 3,
            "items": [{"id": "TASK-1", "status": "OPEN", "attempts": 0}],
            "history": [],
        }
        with self.assertRaisesRegex(EvolutionError, "note must be a string"):
            advance_task(queue, "TASK-1", "SELECTED", ["not a note"], owner="unit-test")
        queue["items"][0]["attempts"] = -1
        with self.assertRaisesRegex(EvolutionError, "attempts count"):
            advance_task(queue, "TASK-1", "SELECTED", owner="unit-test")

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
                    "to": "SELECTED",
                    "note": "first transition",
                    "at": "2026-01-01T00:00:00+00:00",
                },
                {
                    "event": "STATUS_CHANGED",
                    "task_id": "TASK-1",
                    "from": "OPEN",
                    "to": "SELECTED",
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
                "to": "SELECTED",
                "note": "history claims SELECTED",
                "at": "2026-01-01T00:00:00+00:00",
            }]))

    def test_rejects_history_edges_outside_the_transition_table(self):
        for start, end in (("OPEN", "DONE"), ("DONE", "OPEN"), ("REJECTED", "SELECTED"), ("OPEN", "OPEN")):
            with self.subTest(edge=f"{start}->{end}"):
                with self.assertRaisesRegex(EvolutionError, "illegal transition"):
                    load_queue(self._write_queue([{
                        "event": "STATUS_CHANGED", "task_id": "TASK-1", "from": start, "to": end,
                        "note": "forged", "at": "2026-01-01T00:00:00+00:00",
                    }]))

    def test_rejects_history_completion_without_a_bound_pass(self):
        def edge(start, end, second):
            event = {"event": "STATUS_CHANGED", "task_id": "TASK-1", "from": start, "to": end,
                     "note": "", "at": f"2026-01-01T00:00:0{second}+00:00"}
            if end == "SELECTED":
                event["lease_sha256"] = hashlib.sha256(b"b" * 32).hexdigest()
            if end == "DONE":
                event["commit_sha"] = "a" * 40
                event["tree_sha"] = "e" * 40
                event["revision_semantics"] = "tested_commit_tree"
            return event

        def verification(status, attempt, source="tests/example.py", commit="a" * 40, lease_token="b" * 32):
            event = {"event": "VERIFICATION_RECORDED", "task_id": "TASK-1", "verification_status": status,
                     "verification_level": "unit", "artifact_sha256": None, "source": source,
                     "attempt": attempt, "at": "2026-01-01T00:00:03+00:00"}
            if commit is not None:
                event["commit_sha"] = commit
                event["tree_sha"] = "e" * 40
            if lease_token is not None:
                event["lease_sha256"] = hashlib.sha256(lease_token.encode()).hexdigest()
            return event

        def write(events):
            path = self._write_queue(events)
            queue = json.loads(path.read_text(encoding="utf-8"))
            attempts = sum(1 for e in events if e["event"] == "STATUS_CHANGED" and e["to"] == "IN_PROGRESS")
            queue["items"][0].update({"source": "tests/example.py", "attempts": attempts})
            path.write_text(json.dumps(queue), encoding="utf-8")
            return path

        walk = [edge("OPEN", "SELECTED", 1), edge("SELECTED", "IN_PROGRESS", 2)]
        cases = {
            "no evidence": walk,
            "FAIL": walk + [verification("FAIL", 1)],
            "other source": walk + [verification("PASS", 1, source="other.py")],
            "no commit": walk + [verification("PASS", 1, commit=None)],
            "other lease": walk + [verification("PASS", 1, lease_token="c" * 32)],
            "no lease token": walk + [verification("PASS", 1, lease_token=None)],
            "earlier attempt": walk + [verification("PASS", 1), edge("IN_PROGRESS", "OPEN", 3),
                                       edge("OPEN", "SELECTED", 3), edge("SELECTED", "IN_PROGRESS", 3)],
        }
        for label, events in cases.items():
            with self.subTest(label):
                with self.assertRaisesRegex(EvolutionError, "without a PASS"):
                    load_queue(write(events + [edge("IN_PROGRESS", "DONE", 4)]))
        path = write(walk + [verification("PASS", 1), edge("IN_PROGRESS", "DONE", 4)])
        self.assertEqual(load_queue(path)["items"][0]["status"], "DONE")

        # A persisted DONE edge must identify exactly the commit and tree that passed.
        for label, mutate in (
            ("different commit", lambda event: event.update({"commit_sha": "b" * 40})),
            ("different tree", lambda event: event.update({"tree_sha": "f" * 40})),
            ("missing commit", lambda event: event.pop("commit_sha")),
            ("malformed tree", lambda event: event.update({"tree_sha": "not-a-sha"})),
            ("missing semantics", lambda event: event.pop("revision_semantics")),
            ("wrong semantics", lambda event: event.update({"revision_semantics": "live_tree_digest"})),
            ("legacy semantics after migration", lambda event: event.update(
                {"revision_semantics": "tested_source_snapshot_sha256", "revision": "a" * 64})),
        ):
            with self.subTest(done_evidence=label):
                events = walk + [verification("PASS", 1), edge("IN_PROGRESS", "DONE", 4)]
                mutate(events[-1])
                with self.assertRaisesRegex(EvolutionError, "DONE commit and tree"):
                    load_queue(write(events))

        # Persisted history must not change verification state after a terminal transition.
        post_done_failure = verification("FAIL", 1)
        post_done_failure["at"] = "2026-01-01T00:00:05+00:00"
        path = write(walk + [
            verification("PASS", 1),
            edge("IN_PROGRESS", "DONE", 4),
            post_done_failure,
        ])
        with self.assertRaisesRegex(EvolutionError, "outside IN_PROGRESS"):
            load_queue(path)
        # Evidence recorded before the attempt started cannot count either.
        path = write([edge("OPEN", "SELECTED", 1), verification("PASS", 1), edge("SELECTED", "IN_PROGRESS", 2)])
        with self.assertRaisesRegex(EvolutionError, "outside IN_PROGRESS"):
            load_queue(path)

    def test_rejects_attempt_counter_that_contradicts_history(self):
        events = []
        for cycle in range(3):
            for start, end in (("OPEN", "SELECTED"), ("SELECTED", "IN_PROGRESS"), ("IN_PROGRESS", "OPEN")):
                events.append({"event": "STATUS_CHANGED", "task_id": "TASK-1", "from": start, "to": end,
                               "note": "", "at": f"2026-01-01T00:00:0{cycle}+00:00"})
        path = self._write_queue(events)
        queue = json.loads(path.read_text(encoding="utf-8"))
        for attempts in (0, 1, 2):
            with self.subTest(attempts=attempts):
                queue["items"][0].update({"status": "OPEN", "attempts": attempts})
                path.write_text(json.dumps(queue), encoding="utf-8")
                with self.assertRaisesRegex(EvolutionError, "attempts/history mismatch"):
                    load_queue(path)
        queue["items"][0]["attempts"] = 3
        path.write_text(json.dumps(queue), encoding="utf-8")
        self.assertEqual(load_queue(path)["items"][0]["attempts"], 3)

    def test_rejects_attempts_beyond_the_limit(self):
        # advance_task never starts a fourth attempt, so a restored queue that claims one is forged.
        path = self._write_queue([])
        queue = json.loads(path.read_text(encoding="utf-8"))
        queue["items"][0].update({"status": "OPEN", "attempts": 4})
        path.write_text(json.dumps(queue), encoding="utf-8")
        with self.assertRaisesRegex(EvolutionError, "attempt limit"):
            load_queue(path)
        events = []
        for cycle in range(4):
            for start, end in (("OPEN", "SELECTED"), ("SELECTED", "IN_PROGRESS"), ("IN_PROGRESS", "OPEN")):
                events.append({"event": "STATUS_CHANGED", "task_id": "TASK-1", "from": start, "to": end,
                               "note": "", "at": f"2026-01-01T00:00:0{cycle}+00:00"})
        queue["history"] = events
        queue["items"][0]["attempts"] = 3
        path.write_text(json.dumps(queue), encoding="utf-8")
        with self.assertRaisesRegex(EvolutionError, "beyond the attempt limit"):
            load_queue(path)

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
                "CORE-007",
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
                record_verification_file(path, "CORE-007", ["PASS"], "GENERATED_TEST_EXECUTION")
            with self.assertRaisesRegex(EvolutionError, "Unsupported queue status"):
                advance_task_file(path, "TASK-1", ["DONE"], "invalid status type")

    def test_accepts_history_written_by_queue_helpers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "TASK_QUEUE.json"
            update_queue_file(path, [{
                "id": "TASK-1",
                "type": "proposal",
                "description": "test",
            }])
            advance_task_file(path, "TASK-1", "SELECTED", "test transition", owner="unit-test")
            queue = load_queue(path)
            self.assertEqual([event["event"] for event in queue["history"]], [
                "CANDIDATE_ADDED",
                "STATUS_CHANGED",
            ])

    def test_failed_atomic_replace_preserves_previous_queue_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "TASK_QUEUE.json"
            update_queue_file(path, [{"id": "TASK-1", "type": "proposal"}])
            original_bytes = path.read_bytes()

            with patch("autopoesis.task_queue.os.replace", side_effect=OSError("disk error")):
                with self.assertRaisesRegex(OSError, "disk error"):
                    advance_task_file(path, "TASK-1", "SELECTED", "must not partially persist", owner="unit-test")

            self.assertEqual(path.read_bytes(), original_bytes)
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])


    def test_missing_queue_file_returns_empty_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_path = Path(directory) / "missing" / "TASK_QUEUE.json"
            self.assertEqual(load_queue(missing_path), {
                "version": 3,
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
