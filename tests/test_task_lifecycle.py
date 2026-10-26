import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from autopoesis.core import EvolutionError
from autopoesis.task_queue import (
    ALLOWED_TRANSITIONS,
    MAX_ATTEMPTS,
    QUEUE_STATUSES,
    advance_task,
    advance_task_file,
    current_attempt,
    load_queue,
    merge_candidates,
    empty_queue,
    record_verification_file,
    update_queue_file,
)
from autopoesis.executor import source_tree_digest
from run_tasks import run
from lease_helpers import OWNER, step, step_file, token_of


SOURCE = "autopoesis/task_queue.py"
REVISION = "a" * 64


def fresh_queue():
    return merge_candidates(empty_queue(), [{"id": "TASK-1", "type": "proposal", "source": SOURCE}])["queue"]


def advance(queue, *statuses):
    return step(queue, "TASK-1", *statuses, revision=REVISION)


def attempt(queue, status):
    return advance_task(queue, "TASK-1", status, owner=OWNER, token=token_of(queue, "TASK-1"), revision=REVISION)


def with_verification(queue, status, source=SOURCE, revision=REVISION):
    queue = json.loads(json.dumps(queue))
    queue["history"].append({
        "event": "VERIFICATION_RECORDED",
        "task_id": "TASK-1",
        "verification_status": status,
        "verification_level": "UNIT_TEST_FIXTURE",
        "artifact_sha256": None,
        "source": source,
        "lease_sha256": hashlib.sha256(token_of(queue, "TASK-1").encode()).hexdigest(),
        "attempt": next(i for i in queue["items"] if i["id"] == "TASK-1")["attempts"],
        "revision": revision,
        "at": "2999-01-01T00:00:00+00:00",
    })
    return queue


class TaskLifecycleTests(unittest.TestCase):
    def test_table_covers_every_status_and_terminal_states_have_no_exit(self):
        self.assertEqual(set(ALLOWED_TRANSITIONS), QUEUE_STATUSES)
        for targets in ALLOWED_TRANSITIONS.values():
            self.assertLessEqual(targets, QUEUE_STATUSES)
        self.assertEqual(ALLOWED_TRANSITIONS["DONE"], frozenset())
        self.assertEqual(ALLOWED_TRANSITIONS["REJECTED"], frozenset())

    def test_every_transition_outside_the_table_is_rejected(self):
        paths = {
            "OPEN": (),
            "SELECTED": ("SELECTED",),
            "IN_PROGRESS": ("SELECTED", "IN_PROGRESS"),
            "REJECTED": ("REJECTED",),
        }
        for source, path in paths.items():
            queue = advance(fresh_queue(), *path)
            for target in QUEUE_STATUSES - ALLOWED_TRANSITIONS[source] - {source}:
                with self.subTest(source=source, target=target):
                    with self.assertRaisesRegex(EvolutionError, "Illegal transition"):
                        attempt(queue, target)

    def test_done_cannot_be_reopened(self):
        queue = with_verification(advance(fresh_queue(), "SELECTED", "IN_PROGRESS"), "PASS")
        queue = advance(queue, "DONE")
        for target in QUEUE_STATUSES - {"DONE"}:
            with self.assertRaisesRegex(EvolutionError, "Illegal transition"):
                attempt(queue, target)

    def test_repeated_transition_is_an_idempotent_no_op(self):
        queue = advance(fresh_queue(), "SELECTED")
        result = attempt(queue, "SELECTED")
        self.assertFalse(result["changed"])
        self.assertEqual(result["queue"], queue)

    def test_done_requires_pass_verification_after_latest_attempt(self):
        in_progress = advance(fresh_queue(), "SELECTED", "IN_PROGRESS")
        with self.assertRaisesRegex(EvolutionError, "no PASS verification"):
            attempt(in_progress, "DONE")
        with self.assertRaisesRegex(EvolutionError, "no PASS verification"):
            attempt(with_verification(in_progress, "FAIL"), "DONE")
        with self.assertRaisesRegex(EvolutionError, "no PASS verification"):
            attempt(with_verification(with_verification(in_progress, "PASS"), "FAIL"), "DONE")
        done = advance(with_verification(in_progress, "PASS"), "DONE")
        self.assertEqual(done["items"][0]["status"], "DONE")

    def test_pass_for_a_different_source_does_not_count(self):
        in_progress = advance(fresh_queue(), "SELECTED", "IN_PROGRESS")
        for forged in ("autopoesis/core.py", None):
            queue = with_verification(in_progress, "PASS", source=forged)
            if forged is None:
                del queue["history"][-1]["source"]
            with self.assertRaisesRegex(EvolutionError, "own source"):
                attempt(queue, "DONE")

    def test_item_without_source_cannot_reach_done(self):
        queue = merge_candidates(empty_queue(), [{"id": "TASK-1", "type": "proposal"}])["queue"]
        queue = with_verification(advance(queue, "SELECTED", "IN_PROGRESS"), "PASS")
        with self.assertRaisesRegex(EvolutionError, "own source"):
            attempt(queue, "DONE")

    def test_verification_file_binds_evidence_to_the_item_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "TASK_QUEUE.json"
            update_queue_file(path, [
                {"id": "TASK-1", "type": "proposal", "source": SOURCE},
                {"id": "NO-SOURCE", "type": "proposal"},
            ])
            step_file(path, "TASK-1", "SELECTED", "IN_PROGRESS")
            token = token_of(load_queue(path), "TASK-1")
            before = path.read_bytes()
            for task_id, source, message in (
                ("TASK-1", "autopoesis/core.py", "does not match"),
                ("TASK-1", None, "does not match"),
                ("NO-SOURCE", SOURCE, "no source to bind"),
            ):
                with self.subTest(task_id=task_id, source=source):
                    with self.assertRaisesRegex(EvolutionError, message):
                        record_verification_file(path, task_id, "PASS", "unit", source=source, attempt=1, token=token)
            self.assertEqual(path.read_bytes(), before)
            record_verification_file(path, "TASK-1", "PASS", "unit", source=SOURCE, attempt=1, token=token)
            self.assertEqual(load_queue(path)["history"][-1]["source"], SOURCE)

    def test_verification_attempt_must_be_a_real_integer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "TASK_QUEUE.json"
            update_queue_file(path, [{"id": "TASK-1", "type": "proposal", "source": SOURCE}])
            step_file(path, "TASK-1", "SELECTED", "IN_PROGRESS")
            token = token_of(load_queue(path), "TASK-1")
            before = path.read_bytes()
            for attempt in (True, 1.0, "1", 0):
                with self.subTest(attempt=attempt):
                    with self.assertRaisesRegex(EvolutionError, "attempt must be a positive integer"):
                        record_verification_file(path, "TASK-1", "PASS", "unit", source=SOURCE, attempt=attempt,
                                                 token=token)
            self.assertEqual(path.read_bytes(), before)
            load_queue(path)

    def test_queue_module_exposes_no_unchecked_status_writer(self):
        import autopoesis.task_queue as task_queue
        self.assertFalse(hasattr(task_queue, "record_outcome"))
        self.assertFalse(hasattr(task_queue, "record_outcome_file"))

    def test_pass_from_an_earlier_attempt_does_not_count_after_retry(self):
        queue = with_verification(advance(fresh_queue(), "SELECTED", "IN_PROGRESS"), "PASS")
        queue = advance(queue, "OPEN", "SELECTED", "IN_PROGRESS")
        with self.assertRaisesRegex(EvolutionError, "no PASS verification"):
            attempt(queue, "DONE")

    def test_delayed_verifier_cannot_record_into_a_later_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "TASK_QUEUE.json"
            update_queue_file(path, [{"id": "TASK-1", "type": "proposal", "source": SOURCE}])
            step_file(path, "TASK-1", "SELECTED", "IN_PROGRESS")
            captured, old_token = current_attempt(path, "TASK-1"), token_of(load_queue(path), "TASK-1")
            step_file(path, "TASK-1", "OPEN", "SELECTED", "IN_PROGRESS")
            token = token_of(load_queue(path), "TASK-1")
            before = path.read_bytes()
            for label, held in (("old lease", old_token), ("current lease", token)):
                with self.subTest(label):
                    with self.assertRaisesRegex(EvolutionError, "(?i)stale"):
                        record_verification_file(path, "TASK-1", "PASS", "unit", source=SOURCE,
                                                 attempt=captured, token=held)
            self.assertEqual(path.read_bytes(), before)
            with self.assertRaisesRegex(EvolutionError, "no PASS verification"):
                advance_task_file(path, "TASK-1", "DONE", token=token)

    def test_runner_refuses_a_pass_that_returns_after_a_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue_path, tasks_path, results_path = (
                root / "TASK_QUEUE.json", root / "TASKS.json", root / "RESULTS.json"
            )
            update_queue_file(queue_path, [{"id": "TASK-1", "type": "proposal", "source": SOURCE}])
            step_file(queue_path, "TASK-1", "SELECTED", "IN_PROGRESS")
            started_token = token_of(load_queue(queue_path), "TASK-1")

            def slow_verifier(task, root):
                # Another executor retries the item while this verification is still running.
                step_file(queue_path, "TASK-1", "OPEN", "SELECTED", "IN_PROGRESS")
                return {"verification_status": "PASS", "artifact_sha256": None}

            tasks_path.write_text(json.dumps({"tasks": [{
                "id": "verify", "type": "verify_test_patch_sandbox", "source": SOURCE, "queue_task_id": "TASK-1",
                "lease_token": started_token,
            }]}), encoding="utf-8")
            with mock.patch("run_tasks.verify_test_patch_in_sandbox", side_effect=slow_verifier):
                code = run(tasks_path, results_path, queue_path)
            self.assertEqual(code, 1)
            self.assertRegex(json.loads(results_path.read_text(encoding="utf-8"))["tasks"][0]["error"], "(?i)stale")
            queue = load_queue(queue_path)
            self.assertEqual(queue["items"][0]["attempts"], 2)
            self.assertFalse([e for e in queue["history"] if e["event"] == "VERIFICATION_RECORDED"])
            with self.assertRaisesRegex(EvolutionError, "no PASS verification"):
                advance_task_file(queue_path, "TASK-1", "DONE", token=token_of(queue, "TASK-1"))

    def test_pass_for_other_code_does_not_complete_the_task(self):
        in_progress = advance(fresh_queue(), "SELECTED", "IN_PROGRESS")
        verified = with_verification(in_progress, "PASS", revision="b" * 64)
        for revision in (REVISION, None, "not-a-digest"):
            with self.subTest(revision=revision):
                with self.assertRaisesRegex(EvolutionError, "no PASS verification"):
                    advance_task(verified, "TASK-1", "DONE", owner=OWNER, token=token_of(verified, "TASK-1"),
                                 revision=revision)
        done = advance_task(verified, "TASK-1", "DONE", owner=OWNER, token=token_of(verified, "TASK-1"),
                            revision="b" * 64)["queue"]
        self.assertEqual(done["items"][0]["status"], "DONE")

    def test_runner_refuses_done_after_the_code_changed_since_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue_path, tasks_path, results_path = (
                root / "TASK_QUEUE.json", root / "TASKS.json", root / "RESULTS.json"
            )
            update_queue_file(queue_path, [{"id": "TASK-1", "type": "proposal", "source": SOURCE}])
            step_file(queue_path, "TASK-1", "SELECTED", "IN_PROGRESS")
            token = token_of(load_queue(queue_path), "TASK-1")

            def run_tasks(*tasks):
                tasks_path.write_text(json.dumps({"tasks": list(tasks)}), encoding="utf-8")
                return run(tasks_path, results_path, queue_path), json.loads(results_path.read_text(encoding="utf-8"))

            code, _ = run_tasks({"id": "verify", "type": "verify_test_patch_sandbox", "source": SOURCE,
                                 "queue_task_id": "TASK-1", "lease_token": token})
            self.assertEqual(code, 0)
            evidence = [e for e in load_queue(queue_path)["history"] if e["event"] == "VERIFICATION_RECORDED"]
            self.assertEqual(evidence[-1]["revision"], source_tree_digest(ROOT / "autopoesis"))

            done = {"id": "done", "type": "update_task_status", "task_id": "TASK-1", "status": "DONE",
                    "lease_token": token}
            # The checkout was restored to other code between verification and completion.
            with mock.patch("run_tasks.source_tree_digest", return_value="c" * 64):
                code, results = run_tasks(done)
            self.assertEqual(code, 1)
            self.assertIn("no PASS verification", results["tasks"][0]["error"])
            self.assertEqual(load_queue(queue_path)["items"][0]["status"], "IN_PROGRESS")

            code, _ = run_tasks(done)
            self.assertEqual(code, 0)
            self.assertEqual(load_queue(queue_path)["items"][0]["status"], "DONE")

    def test_source_tree_digest_follows_content_and_ignores_bytecode(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "autopoesis"
            (package / "__pycache__").mkdir(parents=True)
            (package / "core.py").write_text("x = 1\n", encoding="utf-8")
            original = source_tree_digest(package)
            (package / "__pycache__" / "core.cpython-312.pyc").write_bytes(b"cache")
            self.assertEqual(source_tree_digest(package), original)
            (package / "core.py").write_text("x = 2\n", encoding="utf-8")
            self.assertNotEqual(source_tree_digest(package), original)
            (package / "core.py").write_text("x = 1\n", encoding="utf-8")
            (package / "extra.py").write_text("", encoding="utf-8")
            self.assertNotEqual(source_tree_digest(package), original)

    def test_attempt_limit_stops_retries_but_allows_rejection(self):
        queue = fresh_queue()
        for _ in range(MAX_ATTEMPTS):
            queue = advance(queue, "SELECTED", "IN_PROGRESS", "OPEN")
        self.assertEqual(queue["items"][0]["attempts"], MAX_ATTEMPTS)
        queue = advance(queue, "SELECTED")
        with self.assertRaisesRegex(EvolutionError, "attempt limit"):
            attempt(queue, "IN_PROGRESS")
        self.assertEqual(advance(queue, "REJECTED")["items"][0]["status"], "REJECTED")

    def test_unknown_task_and_status_are_rejected(self):
        with self.assertRaises(EvolutionError):
            advance_task(fresh_queue(), "MISSING", "SELECTED")
        with self.assertRaises(EvolutionError):
            attempt(fresh_queue(), "FINISHED")

    def test_file_no_op_and_rejection_leave_the_file_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "TASK_QUEUE.json"
            update_queue_file(path, [{"id": "TASK-1", "type": "proposal"}])
            step_file(path, "TASK-1", "SELECTED")
            before = path.read_bytes()
            self.assertFalse(step_file(path, "TASK-1", "SELECTED")["changed"])
            with self.assertRaises(EvolutionError):
                step_file(path, "TASK-1", "DONE")
            self.assertEqual(path.read_bytes(), before)

    def test_runner_completes_item_only_through_linked_sandbox_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue_path, tasks_path, results_path = (
                root / "TASK_QUEUE.json", root / "TASKS.json", root / "RESULTS.json"
            )
            update_queue_file(queue_path, [
                {"id": "QUEUE-ITEM", "type": "proposal", "source": SOURCE},
                {"id": "OTHER-ITEM", "type": "proposal", "source": "autopoesis/core.py"},
            ])

            def run_tasks(*tasks):
                tasks_path.write_text(json.dumps({"tasks": list(tasks)}), encoding="utf-8")
                code = run(tasks_path, results_path, queue_path)
                return code, json.loads(results_path.read_text(encoding="utf-8"))

            def token():
                return token_of(load_queue(queue_path), "QUEUE-ITEM")

            def status(target, task_id="set"):
                return {"id": task_id, "type": "update_task_status", "task_id": "QUEUE-ITEM", "status": target,
                        "lease_token": token()}

            run_tasks(status("SELECTED", "s"))
            code, results = run_tasks(status("IN_PROGRESS", "p"), status("DONE", "d"))
            self.assertEqual(code, 1)
            self.assertIn("no PASS verification", results["tasks"][1]["error"])

            # A real PASS for task_queue.py must not be credited to an item about core.py.
            code, results = run_tasks({
                "id": "verify-other",
                "type": "verify_test_patch_sandbox",
                "source": SOURCE,
                "queue_task_id": "OTHER-ITEM",
            })
            self.assertEqual(code, 1)
            self.assertIn("does not match", results["tasks"][0]["error"])
            self.assertFalse([e for e in load_queue(queue_path)["history"] if e["event"] == "VERIFICATION_RECORDED"])

            code, _ = run_tasks({
                "id": "verify",
                "type": "verify_test_patch_sandbox",
                "source": "autopoesis/task_queue.py",
                "queue_task_id": "QUEUE-ITEM",
                "lease_token": token(),
            }, status("DONE"))
            self.assertEqual(code, 0)
            queue = load_queue(queue_path)
            item = next(i for i in queue["items"] if i["id"] == "QUEUE-ITEM")
            self.assertEqual(item["status"], "DONE")
            self.assertEqual(item["attempts"], 1)
            evidence = [e for e in queue["history"] if e["event"] == "VERIFICATION_RECORDED"]
            self.assertEqual([e["task_id"] for e in evidence], ["QUEUE-ITEM"])

            code, results = run_tasks(status("OPEN"))
            self.assertEqual(code, 1)
            self.assertIn("Illegal transition", results["tasks"][0]["error"])
            item = next(i for i in load_queue(queue_path)["items"] if i["id"] == "QUEUE-ITEM")
            self.assertEqual(item["status"], "DONE")


ROOT = Path(__file__).resolve().parents[1]


def workflow_seed_script():
    """Return the Python body of the CI seed probe step, exactly as the workflow runs it."""
    lines = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8").splitlines()
    start = lines.index("      - name: Seed synthetic DONE probe for cross-run verification")
    begin = next(i for i in range(start, len(lines)) if lines[i].strip() == "python - <<'PY'")
    end = next(i for i in range(begin + 1, len(lines)) if lines[i].strip() == "PY")
    return "\n".join(line[10:] for line in lines[begin + 1:end]) + "\n"


class WorkflowSeedProbeTests(unittest.TestCase):
    def test_seed_probe_uses_only_the_governed_lifecycle(self):
        script = workflow_seed_script()
        self.assertNotIn("record_outcome", script)
        self.assertIn("advance_task_file", script)

    def test_seed_probe_reaches_done_through_verified_transitions(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {**os.environ, "PYTHONPATH": str(ROOT)}
            completed = subprocess.run(
                [sys.executable, "-c", workflow_seed_script()],
                cwd=directory, env=env, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            queue = load_queue(Path(directory) / "TASK_QUEUE.json")
        probe = next(item for item in queue["items"] if item["id"] == "CI-RESTORE-DONE-PROBE")
        self.assertEqual(probe["status"], "DONE")
        self.assertEqual(probe["attempts"], 1)
        steps = [
            (event["event"], event.get("to") or event.get("verification_status"))
            for event in queue["history"] if event["task_id"] == "CI-RESTORE-DONE-PROBE"
        ]
        self.assertEqual(steps, [
            ("CANDIDATE_ADDED", None),
            ("STATUS_CHANGED", "SELECTED"),
            ("STATUS_CHANGED", "IN_PROGRESS"),
            ("VERIFICATION_RECORDED", "PASS"),
            ("STATUS_CHANGED", "DONE"),
        ])
        self.assertTrue(any(
            event.get("task_id") == "CI-RESTORE-VERIFICATION-PROBE" for event in queue["history"]
        ))


if __name__ == "__main__":
    unittest.main()
