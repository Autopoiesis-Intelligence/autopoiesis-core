"""merge_candidates appends without reordering history and never returns or persists an invalid queue."""

import json
import tempfile
import unittest
from pathlib import Path

from autopoesis.core import EvolutionError
from autopoesis.task_queue import empty_queue, load_queue, merge_candidates, update_queue_file
from lease_helpers import step

COMMIT = "a" * 40
TREE = "e" * 40


def candidate(task_id, source="autopoesis/core.py"):
    return {"id": task_id, "type": "proposal", "source": source, "evidence": "merge test"}


def without_times(queue):
    queue = json.loads(json.dumps(queue))
    for item in queue["items"]:
        item.pop("first_seen", None)
    for event in queue["history"]:
        event.pop("at", None)
    return queue


class QueueMergeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "TASK_QUEUE.json"

    def test_existing_history_is_never_reordered(self):
        queue = merge_candidates(empty_queue(), [candidate("B")])["queue"]
        # Recorded events far in the future: a merge with a normal clock must still append after them.
        for event in queue["history"]:
            event["at"] = "2999-01-01T00:00:00+00:00"
        merged = merge_candidates(queue, [candidate("A")])["queue"]
        self.assertEqual(merged["history"][:1], queue["history"])
        self.assertEqual([e["task_id"] for e in merged["history"]], ["B", "A"])
        self.assertEqual([i["id"] for i in merged["items"]], ["A", "B"])

    def test_valid_merges_are_deterministic(self):
        base = merge_candidates(empty_queue(), [candidate("M")])["queue"]
        one = merge_candidates(base, [candidate("C"), candidate("A"), candidate("B"), candidate("A")])
        two = merge_candidates(base, [candidate("B"), candidate("C"), candidate("A")])
        self.assertEqual(without_times(one["queue"]), without_times(two["queue"]))
        self.assertEqual((one["added"], one["total"]), (3, 4))
        self.assertEqual([e["task_id"] for e in one["queue"]["history"]], ["M", "A", "B", "C"])

    def test_merge_keeps_lifecycle_state_of_known_items(self):
        queue = merge_candidates(empty_queue(), [candidate("T1")])["queue"]
        queue = step(queue, "T1", "SELECTED", "IN_PROGRESS", "OPEN")
        merged = merge_candidates(queue, [{**candidate("T1"), "status": "DONE"}, candidate("T2")])["queue"]
        item = next(i for i in merged["items"] if i["id"] == "T1")
        self.assertEqual((item["status"], item["attempts"]), ("OPEN", 1))
        self.assertEqual(merged["history"][:len(queue["history"])], queue["history"])

    def test_invalid_merged_queue_is_refused(self):
        # A candidate that carries a lease would make an OPEN item look owned; the merged queue is invalid.
        with self.assertRaisesRegex(EvolutionError, "has a lease but is not active"):
            merge_candidates(empty_queue(), [{**candidate("X"), "lease": {"owner": "x"}}])
        # An input whose history contradicts itself is refused too, not passed through.
        forged = merge_candidates(empty_queue(), [candidate("T1")])["queue"]
        forged["items"][0]["status"] = "DONE"
        forged["history"].append({"event": "STATUS_CHANGED", "task_id": "T1", "from": "OPEN", "to": "DONE",
                                  "note": "forged", "at": "2026-01-01T00:00:00+00:00"})
        with self.assertRaisesRegex(EvolutionError, "illegal transition"):
            merge_candidates(forged, [candidate("T2")])

    def test_failed_merge_leaves_the_stored_queue_unchanged(self):
        update_queue_file(self.path, [candidate("T1")])
        before = self.path.read_bytes()
        for bad in ([candidate("T2"), {**candidate("X"), "lease": {"owner": "x"}}],
                    [candidate("T2"), "not an object"],
                    [candidate("T2"), {"id": "  "}]):
            with self.subTest(bad=bad), self.assertRaises(EvolutionError):
                update_queue_file(self.path, bad)
            self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual([i["id"] for i in load_queue(self.path)["items"]], ["T1"])
        # No temporary file from an atomic write is left behind.
        self.assertFalse([p.name for p in self.path.parent.iterdir() if p.name.endswith((".tmp", ".partial"))])


if __name__ == "__main__":
    unittest.main()
