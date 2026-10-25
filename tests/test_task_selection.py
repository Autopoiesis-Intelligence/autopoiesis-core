import json
import multiprocessing
import tempfile
import unittest
from pathlib import Path

from autopoesis.task_queue import (
    MAX_ATTEMPTS,
    advance_task,
    empty_queue,
    load_queue,
    merge_candidates,
    select_next_task,
    select_next_task_file,
    update_queue_file,
)
from autopoesis.core import EvolutionError
from run_tasks import run
from lease_helpers import step


def _select(path_text, start, results):
    start.wait()
    try:
        results.put(("selected", select_next_task_file(Path(path_text), "selector")["selected"]))
    except EvolutionError as exc:
        results.put(("rejected", str(exc)))


def candidate(task_id, **extra):
    return {"id": task_id, "type": "proposal", "source": "autopoesis/x.py", "evidence": "missing test", **extra}


def queue_of(*candidates):
    return merge_candidates(empty_queue(), list(candidates))["queue"]


class TaskSelectionTests(unittest.TestCase):
    def test_empty_queue_selects_nothing(self):
        self.assertEqual(
            select_next_task(empty_queue()),
            {"selected": None, "reason": "no eligible OPEN candidates", "deferred": []},
        )

    def test_selection_is_deterministic_and_independent_of_item_order(self):
        items = [candidate("B"), candidate("A"), candidate("C")]
        first = select_next_task(queue_of(*items))
        second = select_next_task(queue_of(*reversed(items)))
        self.assertEqual(first, second)
        self.assertEqual(first["selected"], "A")
        self.assertEqual([d["id"] for d in first["deferred"]], ["B", "C"])

    def test_priority_then_fewest_attempts_then_id(self):
        queue = queue_of(candidate("A"), candidate("B", priority=2), candidate("C", priority=2))
        self.assertEqual(select_next_task(queue)["selected"], "B")
        queue = step(queue, "B", "SELECTED", "IN_PROGRESS", "OPEN")
        self.assertEqual(select_next_task(queue)["selected"], "C")

    def test_malformed_priority_is_deferred_not_ranked(self):
        queue = queue_of(candidate("A", priority=1), candidate("B", priority="100"), candidate("C", priority=True),
                         candidate("D", priority=2.5))
        selection = select_next_task(queue)
        self.assertEqual(selection["selected"], "A")
        self.assertIn("highest priority 1", selection["reason"])
        reasons = {entry["id"]: entry["reason"] for entry in selection["deferred"]}
        for task_id in ("B", "C", "D"):
            self.assertIn("malformed priority", reasons[task_id])
        only_malformed = select_next_task(queue_of(candidate("B", priority="100")))
        self.assertIsNone(only_malformed["selected"])

    def test_insufficient_evidence_and_attempt_limit_are_deferred_with_reasons(self):
        queue = queue_of({"id": "NOEVIDENCE", "type": "proposal", "source": "x.py"}, candidate("TIRED"))
        for _ in range(MAX_ATTEMPTS):
            for status in ("SELECTED", "IN_PROGRESS", "OPEN"):
                queue = step(queue, "TIRED", status)
        result = select_next_task(queue)
        self.assertIsNone(result["selected"])
        self.assertEqual(result["deferred"], [
            {"id": "NOEVIDENCE", "reason": "insufficient evidence: needs source and evidence"},
            {"id": "TIRED", "reason": "attempt limit reached"},
        ])

    def test_active_work_blocks_a_second_selection(self):
        queue = step(queue_of(candidate("A"), candidate("B")), "B", "SELECTED")
        result = select_next_task(queue)
        self.assertIsNone(result["selected"])
        self.assertEqual(result["reason"], "work already active: B")

    def test_terminal_items_are_not_candidates(self):
        queue = step(queue_of(candidate("A")), "A", "REJECTED")
        self.assertIsNone(select_next_task(queue)["selected"])

    def test_file_selection_persists_once_and_no_work_leaves_file_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "TASK_QUEUE.json"
            update_queue_file(path, [candidate("A"), candidate("B")])
            self.assertEqual(select_next_task_file(path, "selector")["selected"], "A")
            queue = load_queue(path)
            self.assertEqual({i["id"]: i["status"] for i in queue["items"]}, {"A": "SELECTED", "B": "OPEN"})
            self.assertTrue(queue["history"][-1]["note"].startswith("selected by selector: "))
            before = path.read_bytes()
            self.assertIsNone(select_next_task_file(path, "selector")["selected"])
            self.assertEqual(path.read_bytes(), before)

    def test_runner_task_reports_selection_without_manufacturing_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue_path, tasks_path, results_path = root / "Q.json", root / "T.json", root / "R.json"
            tasks_path.write_text(json.dumps({"tasks": [{"id": "pick", "type": "select_next_task"}]}), encoding="utf-8")
            self.assertEqual(run(tasks_path, results_path, queue_path), 0)
            result = json.loads(results_path.read_text(encoding="utf-8"))["tasks"][0]["result"]
            self.assertIsNone(result["selected"])
            self.assertFalse(queue_path.exists())
            update_queue_file(queue_path, [candidate("A")])
            self.assertEqual(run(tasks_path, results_path, queue_path), 0)
            result = json.loads(results_path.read_text(encoding="utf-8"))["tasks"][0]["result"]
            self.assertEqual(result["selected"], "A")
            self.assertEqual(load_queue(queue_path)["items"][0]["status"], "SELECTED")


    def test_concurrent_selectors_never_select_two_items(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "TASK_QUEUE.json"
            update_queue_file(path, [candidate("A"), candidate("B"), candidate("C")])
            context = multiprocessing.get_context("fork")
            start, results = context.Event(), context.Queue()
            processes = [context.Process(target=_select, args=(str(path), start, results)) for _ in range(8)]
            for process in processes:
                process.start()
            start.set()
            outcomes = [results.get(timeout=30) for _ in processes]
            for process in processes:
                process.join(timeout=30)
                self.assertEqual(process.exitcode, 0)
            winners = [value for kind, value in outcomes if kind == "selected" and value is not None]
            self.assertEqual(winners, ["A"])
            for kind, value in outcomes:
                if kind == "rejected":
                    self.assertIn("locked", value)
            statuses = {item["id"]: item["status"] for item in load_queue(path)["items"]}
            self.assertEqual(statuses, {"A": "SELECTED", "B": "OPEN", "C": "OPEN"})


if __name__ == "__main__":
    unittest.main()
