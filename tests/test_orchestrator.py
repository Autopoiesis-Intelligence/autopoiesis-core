"""A10: the bounded unattended cycle, through the real queue file and runner entry point."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from autopoesis.executor import source_tree_digest
from autopoesis.orchestrator import HANDLERS, LOCK_RETRIES, LOCK_RETRY_SECONDS, run_cycle
from autopoesis.task_queue import (
    LEASE_TTL,
    advance_task_file,
    load_queue,
    queue_write_lock,
    recover_expired_leases_file,
    select_next_task_file,
    update_queue_file,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "autopoesis/core.py"


def task(task_id="TASK-1", task_type="verify_test_scaffold", source=SOURCE):
    return {"id": task_id, "type": task_type, "source": source, "evidence": "orchestrator test"}


def passing(item, root):
    return {"verification_status": "PASS", "verification_level": "unit",
            "revision": source_tree_digest(root / "autopoesis")}


def failing(item, root):
    raise RuntimeError("handler crashed")


class OrchestratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # A checkout without tests/, so the real scaffold handler has a module it may write a test for.
        cls.checkout = tempfile.TemporaryDirectory()
        cls.repo = Path(cls.checkout.name)
        shutil.copytree(ROOT / "autopoesis", cls.repo / "autopoesis", ignore=shutil.ignore_patterns("__pycache__"))

    @classmethod
    def tearDownClass(cls):
        cls.checkout.cleanup()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.dir = Path(temporary.name)
        self.path = self.dir / "TASK_QUEUE.json"

    def item(self, task_id="TASK-1"):
        return next(entry for entry in load_queue(self.path)["items"] if entry["id"] == task_id)

    def events(self, kind):
        return [e for e in load_queue(self.path)["history"] if e["event"] == kind]

    def test_full_cycle_runs_the_real_handler_to_done(self):
        update_queue_file(self.path, [task()])
        result = run_cycle(self.path, "runner", self.repo)
        self.assertEqual((result["status"], result["final"], result["verification"]), ("COMPLETED", "DONE", "PASS"))
        self.assertEqual(self.item()["status"], "DONE")
        self.assertNotIn("lease", self.item())
        steps = [e["to"] for e in self.events("STATUS_CHANGED")]
        self.assertEqual(steps, ["SELECTED", "IN_PROGRESS", "DONE"])
        self.assertEqual(self.events("VERIFICATION_RECORDED")[0]["verification_level"],
                         "GENERATED_TEST_EXECUTION")

    def test_budget_that_could_outlive_the_lease_is_refused_before_any_write(self):
        update_queue_file(self.path, [task()])
        before = self.path.read_bytes()
        for budget in (LEASE_TTL.total_seconds(), LEASE_TTL.total_seconds() - 1, 0):
            with self.subTest(budget=budget), self.assertRaisesRegex(ValueError, "lease TTL"):
                run_cycle(self.path, "runner", ROOT, handlers={"verify_test_scaffold": passing}, budget_seconds=budget)
        self.assertEqual(self.path.read_bytes(), before)

    def test_empty_queue_and_disable_switch_write_nothing(self):
        update_queue_file(self.path, [task(task_type="proposal")])
        before = self.path.read_bytes()
        result = run_cycle(self.path, "runner", ROOT, handlers={"verify_test_scaffold": passing})
        self.assertEqual(result["status"], "NO_WORK")
        self.assertEqual(self.path.read_bytes(), before)

        update_queue_file(self.path, [task("TASK-2")])
        before = self.path.read_bytes()
        switch = self.dir / "DISABLED"
        switch.write_text("paused", encoding="utf-8")
        result = run_cycle(self.path, "runner", ROOT, handlers={"verify_test_scaffold": passing}, disable_path=switch)
        self.assertEqual(result["status"], "DISABLED")
        self.assertEqual(self.path.read_bytes(), before)

    def test_only_allowlisted_types_are_selected(self):
        update_queue_file(self.path, [task("A-PROPOSAL", task_type="proposal"), task("B-RUNNABLE")])
        result = run_cycle(self.path, "runner", ROOT, handlers={"verify_test_scaffold": passing})
        self.assertEqual(result["task_id"], "B-RUNNABLE")
        self.assertEqual(self.item("A-PROPOSAL")["status"], "OPEN")
        self.assertEqual(set(HANDLERS), {"verify_test_scaffold"})

    def test_handler_failure_retries_then_rejects_at_the_attempt_limit(self):
        update_queue_file(self.path, [task()])
        finals = [run_cycle(self.path, "runner", ROOT, handlers={"verify_test_scaffold": failing})["final"]
                  for _ in range(3)]
        self.assertEqual(finals, ["OPEN", "OPEN", "REJECTED"])
        self.assertEqual(self.item()["attempts"], 3)
        self.assertEqual([e["verification_status"] for e in self.events("VERIFICATION_RECORDED")], ["FAIL"] * 3)
        self.assertEqual(run_cycle(self.path, "runner", ROOT, handlers={"verify_test_scaffold": failing})["status"],
                         "NO_WORK")

    def test_completed_task_is_not_run_twice(self):
        update_queue_file(self.path, [task()])
        run_cycle(self.path, "runner", ROOT, handlers={"verify_test_scaffold": passing})
        before = self.path.read_bytes()
        self.assertEqual(run_cycle(self.path, "runner", ROOT, handlers={"verify_test_scaffold": passing})["status"],
                         "NO_WORK")
        self.assertEqual(self.path.read_bytes(), before)

    def test_timeout_releases_the_task_without_evidence(self):
        update_queue_file(self.path, [task()])
        ticks = iter([0.0, 1000.0])
        result = run_cycle(self.path, "runner", ROOT, handlers={"verify_test_scaffold": passing},
                           budget_seconds=10, clock=lambda: next(ticks))
        self.assertEqual((result["status"], result["final"]), ("TIMED_OUT", "OPEN"))
        self.assertEqual(self.item()["status"], "OPEN")
        self.assertFalse(self.events("VERIFICATION_RECORDED"))

    def test_hung_handler_is_killed_at_the_budget(self):
        update_queue_file(self.path, [task()])

        def hung(item, root):
            time.sleep(60)
            return passing(item, root)

        started = time.monotonic()
        result = run_cycle(self.path, "runner", ROOT, handlers={"verify_test_scaffold": hung}, budget_seconds=1)
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual((result["status"], result["final"]), ("TIMED_OUT", "OPEN"))
        self.assertFalse(self.events("VERIFICATION_RECORDED"))
        self.assertEqual(run_cycle(self.path, "runner", ROOT, handlers={"verify_test_scaffold": passing})["final"],
                         "DONE")

    def test_held_queue_lock_refuses_in_bounded_time_without_writes(self):
        update_queue_file(self.path, [task()])
        before = self.path.read_bytes()
        started = time.monotonic()
        with queue_write_lock(self.path):
            result = run_cycle(self.path, "runner", ROOT, handlers={"verify_test_scaffold": passing})
        self.assertLess(time.monotonic() - started, LOCK_RETRIES * LOCK_RETRY_SECONDS + 5)
        self.assertEqual(result["status"], "REFUSED")
        self.assertIn("locked by another writer", result["reason"])
        self.assertEqual(self.path.read_bytes(), before)

    def test_slow_result_delivery_is_still_bounded(self):
        update_queue_file(self.path, [task()])

        class Slow:
            def __str__(self):
                time.sleep(60)
                return "never"

        def slow_result(item, root):
            # The handler itself returns at once; only turning the result into bytes stalls.
            return {**passing(item, root), "detail": Slow()}

        started = time.monotonic()
        result = run_cycle(self.path, "runner", ROOT, handlers={"verify_test_scaffold": slow_result}, budget_seconds=1)
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual((result["status"], result["final"]), ("TIMED_OUT", "OPEN"))
        self.assertFalse(self.events("VERIFICATION_RECORDED"))

    def test_large_result_and_silent_exit_are_classified_correctly(self):
        update_queue_file(self.path, [task("A-LARGE"), task("B-SILENT")])

        def large(item, root):
            # Bigger than a pipe buffer: the parent must read it before waiting for the child.
            return {**passing(item, root), "detail": "x" * 1_000_000}

        def silent(item, root):
            os._exit(3)

        handlers = {"verify_test_scaffold": lambda item, root: (large if item["id"] == "A-LARGE" else silent)(item, root)}
        first = run_cycle(self.path, "runner", ROOT, handlers=handlers, budget_seconds=30)
        self.assertEqual((first["task_id"], first["final"]), ("A-LARGE", "DONE"))
        second = run_cycle(self.path, "runner", ROOT, handlers=handlers, budget_seconds=30)
        self.assertEqual((second["task_id"], second["final"], second["verification"]), ("B-SILENT", "OPEN", "FAIL"))
        self.assertIn("code 3", second["detail"])

    def test_expired_lease_is_recovered_before_selection(self):
        update_queue_file(self.path, [task()])
        stale = select_next_task_file(self.path, "crashed-runner",
                                      now=datetime.now(timezone.utc) - LEASE_TTL - timedelta(minutes=1))
        self.assertIsNotNone(stale["lease"])
        result = run_cycle(self.path, "runner", ROOT, handlers={"verify_test_scaffold": passing})
        self.assertEqual(result["recovered"], ["TASK-1"])
        self.assertEqual((result["status"], result["final"]), ("COMPLETED", "DONE"))

    def test_stale_worker_cannot_record_or_complete_after_reassignment(self):
        update_queue_file(self.path, [task()])
        later = datetime.now(timezone.utc) + LEASE_TTL + timedelta(hours=1)

        def overtaken(item, root):
            # While this worker runs, its lease expires and another executor takes the task.
            recover_expired_leases_file(self.path, now=later)
            token = advance_task_file(self.path, "TASK-1", "SELECTED", owner="other", now=later)["lease"]["token"]
            advance_task_file(self.path, "TASK-1", "IN_PROGRESS", token=token, now=later)
            return passing(item, root)

        result = run_cycle(self.path, "runner", ROOT, handlers={"verify_test_scaffold": overtaken})
        self.assertEqual(result["status"], "REFUSED")
        self.assertIn("STALE_LEASE", result["reason"])
        self.assertEqual(self.item()["status"], "IN_PROGRESS")
        self.assertEqual(self.item()["lease"]["owner"], "other")
        self.assertFalse(self.events("VERIFICATION_RECORDED"))

    def test_two_runner_processes_never_both_execute(self):
        update_queue_file(self.path, [task()])
        marker = self.dir / "executions"
        script = textwrap.dedent("""
            import sys, time
            from pathlib import Path
            from autopoesis.executor import source_tree_digest
            from autopoesis.orchestrator import run_cycle
            queue, marker, owner = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
            def slow(item, root):
                with marker.open("a") as handle:
                    handle.write(owner + "\\n")
                time.sleep(1)
                return {"verification_status": "PASS", "verification_level": "unit",
                        "revision": source_tree_digest(root / "autopoesis")}
            print(run_cycle(queue, owner, Path("."), handlers={"verify_test_scaffold": slow})["status"])
        """)
        runners = [subprocess.Popen([sys.executable, "-c", script, str(self.path), str(marker), owner],
                                    cwd=ROOT, stdout=subprocess.PIPE, text=True) for owner in ("one", "two")]
        statuses = sorted(runner.communicate(timeout=60)[0].strip() for runner in runners)
        self.assertEqual(statuses, ["COMPLETED", "NO_WORK"])
        self.assertEqual(len(marker.read_text(encoding="utf-8").splitlines()), 1)
        self.assertEqual(self.item()["status"], "DONE")

    def test_command_line_entry_point_runs_one_cycle(self):
        update_queue_file(self.path, [task()])
        completed = subprocess.run(
            [sys.executable, "-m", "autopoesis.orchestrator", "--queue", str(self.path), "--owner", "ci",
             "--root", str(self.repo)],
            cwd=ROOT, capture_output=True, text=True, timeout=120, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["final"], "DONE")

    
    def test_command_line_timeout_exits_nonzero_and_preserves_open_task(self):
        update_queue_file(self.path, [task()])
        completed = subprocess.run(
            [sys.executable, "-m", "autopoesis.orchestrator", "--queue", str(self.path), "--owner", "ci",
             "--root", str(self.repo), "--budget-seconds", "0.000001"],
            cwd=ROOT, capture_output=True, text=True, timeout=120, check=False,
        )
        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        result = json.loads(completed.stdout)
        self.assertEqual((result["status"], result["final"]), ("TIMED_OUT", "OPEN"))
        queue = load_queue(self.path)
        self.assertEqual(queue["items"][0]["status"], "OPEN")
        self.assertFalse(any(event["event"] == "VERIFICATION_RECORDED" for event in queue["history"]))


    def test_command_line_no_work_exits_zero(self):
        update_queue_file(self.path, [])
        completed = subprocess.run(
            [sys.executable, "-m", "autopoesis.orchestrator", "--queue", str(self.path), "--owner", "ci",
             "--root", str(self.repo)],
            cwd=ROOT, capture_output=True, text=True, timeout=120, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "NO_WORK")
        self.assertNotIn("final", result)


if __name__ == "__main__":
    unittest.main()
