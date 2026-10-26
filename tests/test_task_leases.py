"""A9: leases keep one executor per task and let a crashed executor's task be recovered."""

import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from autopoesis.core import EvolutionError
from run_tasks import run
from autopoesis.task_queue import (
    LEASE_TTL,
    advance_task_file,
    load_queue,
    record_verification_file,
    recover_expired_leases_file,
    renew_lease_file,
    select_next_task_file,
    update_queue_file,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "autopoesis/task_queue.py"
REVISION = "a" * 64
LATER = datetime.now(timezone.utc) + LEASE_TTL + timedelta(hours=1)

CRASHING_EXECUTOR = textwrap.dedent("""
    import os, signal, sys
    from pathlib import Path
    from autopoesis.task_queue import advance_task_file, select_next_task_file
    path = Path(sys.argv[1])
    lease = select_next_task_file(path, "executor-A")["lease"]
    advance_task_file(path, "TASK-1", "IN_PROGRESS", "start", token=lease["token"])
    print(lease["token"], flush=True)
    os.kill(os.getpid(), signal.SIGKILL)
""")


def candidate(task_id="TASK-1"):
    return {"id": task_id, "type": "proposal", "source": SOURCE, "evidence": "lease test"}


def item(path, task_id="TASK-1"):
    return next(entry for entry in load_queue(path)["items"] if entry["id"] == task_id)


class TaskLeaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "TASK_QUEUE.json"
        update_queue_file(self.path, [candidate("TASK-1"), candidate("TASK-2")])

    def acquire(self, owner):
        return select_next_task_file(self.path, owner)["lease"]["token"]

    def test_lease_is_persisted_and_second_executor_is_refused(self):
        token = self.acquire("executor-A")
        lease = item(self.path)["lease"]
        self.assertEqual((lease["owner"], lease["token"]), ("executor-A", token))
        before = self.path.read_bytes()
        result = select_next_task_file(self.path, "executor-B")
        self.assertIsNone(result["selected"])
        self.assertIn("work already active: TASK-1", result["reason"])
        with self.assertRaisesRegex(EvolutionError, "work already active"):
            advance_task_file(self.path, "TASK-2", "SELECTED", owner="executor-B")
        self.assertEqual(self.path.read_bytes(), before)

    def test_holder_can_renew_but_a_wrong_token_cannot(self):
        token = self.acquire("executor-A")
        old_expiry = item(self.path)["lease"]["expires_at"]
        renewed = renew_lease_file(self.path, "TASK-1", token, ttl=LEASE_TTL * 2)["lease"]
        self.assertEqual(renewed["token"], token)
        self.assertGreater(renewed["expires_at"], old_expiry)
        with self.assertRaisesRegex(EvolutionError, "STALE_LEASE"):
            renew_lease_file(self.path, "TASK-1", "0" * 32)

    def test_every_change_of_an_active_item_needs_the_token(self):
        token = self.acquire("executor-A")
        for status in ("SELECTED", "IN_PROGRESS", "OPEN", "REJECTED"):
            with self.subTest(status=status):
                with self.assertRaisesRegex(EvolutionError, "STALE_LEASE"):
                    advance_task_file(self.path, "TASK-1", status, token=None)
        advance_task_file(self.path, "TASK-1", "IN_PROGRESS", token=token)
        self.assertEqual(item(self.path)["status"], "IN_PROGRESS")

    def test_crashed_executor_is_recovered_and_cannot_continue_after_resurrection(self):
        # T3: a real executor process takes the task and dies mid-work.
        env = {**os.environ, "PYTHONPATH": str(ROOT)}
        crashed = subprocess.run(
            [sys.executable, "-c", CRASHING_EXECUTOR, str(self.path)],
            env=env, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(crashed.returncode, -signal.SIGKILL, crashed.stderr)
        old_token = crashed.stdout.strip()
        stuck = item(self.path)
        self.assertEqual((stuck["status"], stuck["lease"]["token"]), ("IN_PROGRESS", old_token))

        # Before expiry nothing is recovered and nothing is written.
        before = self.path.read_bytes()
        self.assertEqual(recover_expired_leases_file(self.path)["recovered"], [])
        self.assertEqual(self.path.read_bytes(), before)

        # T7: once expired, even the right token is refused before recovery runs.
        with self.assertRaisesRegex(EvolutionError, "STALE_LEASE: lease expired"):
            advance_task_file(self.path, "TASK-1", "OPEN", token=old_token, now=LATER)

        # T4: recovery returns it to OPEN and records why.
        self.assertEqual(recover_expired_leases_file(self.path, now=LATER)["recovered"], ["TASK-1"])
        queue = load_queue(self.path)
        recovered = item(self.path)
        self.assertEqual(recovered["status"], "OPEN")
        self.assertNotIn("lease", recovered)
        expired = [e for e in queue["history"] if e["event"] == "LEASE_EXPIRED"]
        self.assertEqual([(e["task_id"], e["owner"], e["lease_sha256"]) for e in expired],
                         [("TASK-1", "executor-A", hashlib.sha256(old_token.encode()).hexdigest())])
        self.assertTrue(queue["history"][-2]["note"].startswith("recovered: lease expired"))
        self.assertNotIn(old_token, json.dumps(queue["history"]))

        # T5: a new executor takes the task with a new token.
        new_token = advance_task_file(self.path, "TASK-1", "SELECTED", owner="executor-B", now=LATER)["lease"]["token"]
        self.assertNotEqual(new_token, old_token)
        advance_task_file(self.path, "TASK-1", "IN_PROGRESS", token=new_token, now=LATER)
        self.assertEqual(item(self.path)["attempts"], 2)

        # T6: the resurrected old executor cannot renew, record evidence or finish.
        before = self.path.read_bytes()
        attempts = [
            lambda: renew_lease_file(self.path, "TASK-1", old_token, now=LATER),
            lambda: record_verification_file(self.path, "TASK-1", "PASS", "unit", source=SOURCE,
                                             attempt=1, token=old_token, now=LATER),
            lambda: advance_task_file(self.path, "TASK-1", "DONE", token=old_token, now=LATER, revision=REVISION),
            lambda: advance_task_file(self.path, "TASK-1", "IN_PROGRESS", token=old_token, now=LATER),
        ]
        for index, call in enumerate(attempts):
            with self.subTest(old_executor_call=index):
                with self.assertRaisesRegex(EvolutionError, "STALE_LEASE"):
                    call()
        self.assertEqual(self.path.read_bytes(), before)

        # T8: the current holder finishes only with its own PASS.
        with self.assertRaisesRegex(EvolutionError, "no PASS verification"):
            advance_task_file(self.path, "TASK-1", "DONE", token=new_token, now=LATER, revision=REVISION)
        record_verification_file(self.path, "TASK-1", "PASS", "unit", source=SOURCE, attempt=2, revision=REVISION,
                                 token=new_token, now=LATER)
        advance_task_file(self.path, "TASK-1", "DONE", token=new_token, now=LATER, revision=REVISION)
        done = item(self.path)
        self.assertEqual(done["status"], "DONE")
        self.assertNotIn("lease", done)

    def test_restored_pass_must_carry_the_token_leased_for_that_attempt(self):
        token = self.acquire("executor-A")
        advance_task_file(self.path, "TASK-1", "IN_PROGRESS", token=token)
        record_verification_file(self.path, "TASK-1", "PASS", "unit", source=SOURCE, attempt=1, revision=REVISION,
                                 token=token)
        advance_task_file(self.path, "TASK-1", "DONE", token=token, revision=REVISION)
        self.assertEqual(item(self.path)["status"], "DONE")
        queue = json.loads(self.path.read_text(encoding="utf-8"))
        selected = next(e for e in queue["history"] if e["event"] == "STATUS_CHANGED" and e["to"] == "SELECTED")
        # The bearer token never reaches durable history, only its fingerprint.
        self.assertNotIn(token, json.dumps(queue["history"]))
        passed = next(e for e in queue["history"] if e["event"] == "VERIFICATION_RECORDED")
        passed["lease_sha256"] = hashlib.sha256(("f" * 32 if token != "f" * 32 else "e" * 32).encode()).hexdigest()
        self.path.write_text(json.dumps(queue), encoding="utf-8")
        with self.assertRaisesRegex(EvolutionError, "without a PASS"):
            load_queue(self.path)

    def test_pass_under_an_expired_lease_does_not_complete_the_next_attempt(self):
        token = self.acquire("executor-A")
        advance_task_file(self.path, "TASK-1", "IN_PROGRESS", token=token)
        record_verification_file(self.path, "TASK-1", "PASS", "unit", source=SOURCE, attempt=1, token=token)
        recover_expired_leases_file(self.path, now=LATER)
        new_token = advance_task_file(self.path, "TASK-1", "SELECTED", owner="executor-B", now=LATER)["lease"]["token"]
        advance_task_file(self.path, "TASK-1", "IN_PROGRESS", token=new_token, now=LATER)
        with self.assertRaisesRegex(EvolutionError, "no PASS verification"):
            advance_task_file(self.path, "TASK-1", "DONE", token=new_token, now=LATER)

    def test_expired_but_unrecovered_lease_still_blocks_new_selection(self):
        self.acquire("executor-A")
        result = select_next_task_file(self.path, "executor-B", now=LATER)
        self.assertIsNone(result["selected"])

    def test_active_item_without_lease_is_frozen_until_recovered(self):
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        payload["items"][0]["status"] = "IN_PROGRESS"
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(EvolutionError, "has no lease"):
            advance_task_file(self.path, "TASK-1", "OPEN", token="0" * 32)
        self.assertEqual(recover_expired_leases_file(self.path)["recovered"], ["TASK-1"])
        self.assertEqual(item(self.path)["status"], "OPEN")

    def test_naive_clock_is_rejected(self):
        with self.assertRaisesRegex(EvolutionError, "timezone-aware"):
            recover_expired_leases_file(self.path, now=datetime(2030, 1, 1))

    def test_leased_snapshot_survives_a_byte_copy_restore(self):
        token = self.acquire("executor-A")
        restored = self.path.with_name("RESTORED.json")
        restored.write_bytes(self.path.read_bytes())
        self.assertEqual(item(restored)["lease"]["token"], token)
        advance_task_file(restored, "TASK-1", "IN_PROGRESS", token=token)

    def test_malformed_leases_are_rejected_on_load(self):
        self.acquire("executor-A")
        good = json.loads(self.path.read_text(encoding="utf-8"))
        broken = {
            "lease on OPEN item": lambda q: q["items"][1].__setitem__("lease", q["items"][0]["lease"]),
            "missing token": lambda q: q["items"][0]["lease"].pop("token"),
            "short token": lambda q: q["items"][0]["lease"].__setitem__("token", "abc"),
            "empty owner": lambda q: q["items"][0]["lease"].__setitem__("owner", " "),
            "naive expiry": lambda q: q["items"][0]["lease"].__setitem__("expires_at", "2030-01-01T00:00:00"),
            "extra field": lambda q: q["items"][0]["lease"].__setitem__("pid", 1),
        }
        for label, corrupt in broken.items():
            with self.subTest(label):
                payload = json.loads(json.dumps(good))
                corrupt(payload)
                self.path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(EvolutionError):
                    load_queue(self.path)

    def test_snapshot_with_two_live_leases_is_rejected_on_load(self):
        self.acquire("executor-A")
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        second = payload["items"][1]
        second["status"] = "SELECTED"
        second["lease"] = {**payload["items"][0]["lease"], "owner": "executor-B", "token": "b" * 32}
        payload["history"] = [e for e in payload["history"] if e.get("task_id") != second["id"]]
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(EvolutionError, "more than one active task"):
            load_queue(self.path)
        with self.assertRaisesRegex(EvolutionError, "more than one active task"):
            advance_task_file(self.path, second["id"], "IN_PROGRESS", token="b" * 32)


    def test_runner_hands_out_the_lease_and_recovers_nothing_while_it_is_live(self):
        tasks = self.path.with_name("TASKS.json")
        results = self.path.with_name("RESULTS.json")
        tasks.write_text(json.dumps({"tasks": [
            {"id": "pick", "type": "select_next_task", "owner": "runner"},
            {"id": "recover", "type": "recover_expired_leases"},
        ]}), encoding="utf-8")
        self.assertEqual(run(tasks, results, self.path), 0)
        output = json.loads(results.read_text(encoding="utf-8"))["tasks"]
        self.assertEqual(output[0]["result"]["lease"]["token"], item(self.path)["lease"]["token"])
        self.assertEqual(output[0]["result"]["lease"]["owner"], "runner")
        self.assertEqual(output[1]["result"]["recovered"], [])

    def test_runner_exposes_lease_renewal_for_an_external_supervisor(self):
        tasks = self.path.with_name("TASKS.json")
        results = self.path.with_name("RESULTS.json")
        tasks.write_text(json.dumps({"tasks": [
            {"id": "pick", "type": "select_next_task", "owner": "runner"},
        ]}), encoding="utf-8")
        self.assertEqual(run(tasks, results, self.path), 0)
        token = item(self.path)["lease"]["token"]
        original_expiry = item(self.path)["lease"]["expires_at"]

        tasks.write_text(json.dumps({"tasks": [
            {"id": "renew", "type": "renew_lease", "queue_task_id": "TASK-1", "lease_token": token},
        ]}), encoding="utf-8")
        self.assertEqual(run(tasks, results, self.path), 0)
        output = json.loads(results.read_text(encoding="utf-8"))["tasks"][0]
        self.assertEqual(output["result"]["lease"]["token"], token)
        self.assertGreater(output["result"]["lease"]["expires_at"], original_expiry)



if __name__ == "__main__":
    unittest.main()
