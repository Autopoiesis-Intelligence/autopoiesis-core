"""Invariants of the NIGHT QUEUE table in docs/PLAN.md.

The hourly tick keeps its state only in this table, so CI checks that the state stays well formed:
every task in progress names who took it and when, no task started before its dependencies are done, and no DONE
without an exact SHA and a run ID.
"""

import re
import unittest
from pathlib import Path

PLAN = Path(__file__).resolve().parent.parent / "docs" / "PLAN.md"
STATUSES = ("TODO", "IN_PROGRESS", "DONE", "BLOCKED")


def parse_queue(text):
    section = text.split("## NIGHT QUEUE", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in section.splitlines() if re.match(r"\| N\d+ \|", line)]
    tasks = {}
    for line in rows:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 6:
            raise ValueError(f"row has {len(cells)} cells, expected 6: {line[:60]}")
        task_id, _, _, depends, _, status = cells
        if task_id in tasks:
            raise ValueError(f"duplicate task {task_id}")
        state = status.split(" ", 1)[0]
        if state not in STATUSES:
            raise ValueError(f"{task_id}: unknown status {status[:40]!r}")
        tasks[task_id] = {"depends": re.findall(r"N\d+", depends), "state": state, "status": status}
    return tasks


def check_queue(tasks):
    for task_id, task in tasks.items():
        # The marker is what stops a second tick from taking the same task, so it must say whose it is.
        if task["state"] == "IN_PROGRESS" and not re.match(
            r"IN_PROGRESS \((Claude|GPT)[^)]*\d{4}-\d{2}-\d{2}[^)]*\)", task["status"]
        ):
            raise ValueError(f"{task_id} is IN_PROGRESS without an owner and a date")
        for dep in task["depends"]:
            if dep not in tasks:
                raise ValueError(f"{task_id} depends on unknown task {dep}")
            if task["state"] in ("IN_PROGRESS", "DONE") and tasks[dep]["state"] != "DONE":
                raise ValueError(f"{task_id} is {task['state']} but its dependency {dep} is not DONE")
        if task["state"] == "DONE":
            if not re.search(r"`[0-9a-f]{7,40}`", task["status"]):
                raise ValueError(f"{task_id} is DONE without an exact SHA")
            if "as design" not in task["status"] and not re.search(r"\b\d{8,}\b", task["status"]):
                raise ValueError(f"{task_id} is DONE without a CI or runtime run ID")
        if task["state"] == "BLOCKED" and len(task["status"]) < len("BLOCKED") + 10:
            raise ValueError(f"{task_id} is BLOCKED without a reason")


def row(task_id, depends="—", status="TODO"):
    return f"| {task_id} | task | branch | {depends} | criterion | {status} |"


def table(*rows):
    return "## NIGHT QUEUE\n\n| ID | Task | Branch / PR | Depends on | Done criterion | Status |\n|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n\n## Tasks\n"


class NightQueueTests(unittest.TestCase):
    def test_current_plan_queue_is_well_formed(self):
        tasks = parse_queue(PLAN.read_text(encoding="utf-8"))
        self.assertTrue(tasks)
        check_queue(tasks)

    def test_in_progress_without_owner_and_date_is_refused(self):
        with self.assertRaisesRegex(ValueError, "without an owner and a date"):
            check_queue(parse_queue(table(row("N1", status="IN_PROGRESS"))))
        check_queue(parse_queue(table(row("N1", status="IN_PROGRESS (Claude, 2026-10-24 13:50 UTC)"))))

    def test_starting_a_task_before_its_dependency_is_done_is_refused(self):
        with self.assertRaisesRegex(ValueError, "dependency N1 is not DONE"):
            check_queue(parse_queue(table(row("N1", status="BLOCKED (owner decision)"), row("N2", "N1", "IN_PROGRESS (Claude, 2026-10-24)"))))

    def test_done_without_sha_or_run_id_is_refused(self):
        with self.assertRaisesRegex(ValueError, "without an exact SHA"):
            check_queue(parse_queue(table(row("N1", status="DONE (Claude): tests pass, run 40095732798"))))
        with self.assertRaisesRegex(ValueError, "without a CI or runtime run ID"):
            check_queue(parse_queue(table(row("N1", status="DONE (Claude): `ab2c149`"))))

    def test_blocked_needs_a_reason_and_unknown_status_is_refused(self):
        with self.assertRaisesRegex(ValueError, "BLOCKED without a reason"):
            check_queue(parse_queue(table(row("N1", status="BLOCKED"))))
        with self.assertRaisesRegex(ValueError, "unknown status"):
            parse_queue(table(row("N1", status="MAYBE")))

    def test_duplicate_task_ids_are_refused(self):
        with self.assertRaisesRegex(ValueError, "duplicate task N1"):
            parse_queue(table(row("N1"), row("N1")))


if __name__ == "__main__":
    unittest.main()
