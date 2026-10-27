"""G3: DONE names the exact commit and tree that a PASS verified, and nothing else can complete a task."""

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import run_tasks
from autopoesis import orchestrator
from autopoesis.core import EvolutionError
from autopoesis.executor import source_tree_digest
from git_helpers import make_repository
from autopoesis.task_queue import (
    advance_task_file,
    current_attempt,
    load_queue,
    migrate_queue_file,
    record_verification_file,
    recover_expired_leases_file,
    select_next_task_file,
    update_queue_file,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "autopoesis/core.py"
# Written by the version 2 code of bbf6a44: T1 DONE, T2 IN_PROGRESS with a PASS and no DONE.
V2_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "queue_v2_done_from_bbf6a44.json"
V1_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "queue_v1_done_from_ba65d04.json"
COMMIT_A = "a" * 40
COMMIT_B = "b" * 40
TREE_A = "c" * 40
TREE_B = "d" * 40


def candidate(task_id="T1"):
    return {"id": task_id, "type": "verify_test_scaffold", "source": SOURCE, "evidence": "commit binding test"}


class QueueCommitBindingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "TASK_QUEUE.json"

    def start(self, task_id="T1", now=None):
        lease = select_next_task_file(self.path, "worker", now=now)["lease"]
        advance_task_file(self.path, task_id, "IN_PROGRESS", "started", token=lease["token"], now=now)
        return lease["token"]

    def record_pass(self, token, commit, tree, task_id="T1"):
        record_verification_file(
            self.path, task_id, "PASS", "unit", None, SOURCE, current_attempt(self.path, task_id), None, token,
            commit_sha=commit, tree_sha=tree,
        )

    def forge_done(self, commit, tree):
        """Write a DONE straight into the file, as a restored or tampered snapshot would carry it."""
        queue = json.loads(self.path.read_text(encoding="utf-8"))
        item = queue["items"][0]
        item["status"] = "DONE"
        item.pop("lease", None)
        queue["history"].append({
            "event": "STATUS_CHANGED", "task_id": item["id"], "from": "IN_PROGRESS", "to": "DONE",
            "note": "forged", "at": datetime.now(timezone.utc).isoformat(),
            "commit_sha": commit, "tree_sha": tree, "revision_semantics": "tested_commit_tree",
        })
        self.path.write_text(json.dumps(queue), encoding="utf-8")

    # 1
    def test_pass_for_one_commit_cannot_complete_another(self):
        update_queue_file(self.path, [candidate()])
        token = self.start()
        self.record_pass(token, COMMIT_A, TREE_A)
        with self.assertRaisesRegex(EvolutionError, "no PASS verification"):
            advance_task_file(self.path, "T1", "DONE", "done", token=token, commit_sha=COMMIT_B, tree_sha=TREE_A)
        self.forge_done(COMMIT_B, TREE_A)
        with self.assertRaisesRegex(EvolutionError, "does not match its bound PASS"):
            load_queue(self.path)

    # 2
    def test_same_commit_with_another_tree_cannot_complete(self):
        update_queue_file(self.path, [candidate()])
        token = self.start()
        self.record_pass(token, COMMIT_A, TREE_A)
        with self.assertRaisesRegex(EvolutionError, "no PASS verification"):
            advance_task_file(self.path, "T1", "DONE", "done", token=token, commit_sha=COMMIT_A, tree_sha=TREE_B)
        self.forge_done(COMMIT_A, TREE_B)
        with self.assertRaisesRegex(EvolutionError, "does not match its bound PASS"):
            load_queue(self.path)

    # 9
    def test_pass_from_an_earlier_attempt_cannot_complete_a_retry(self):
        update_queue_file(self.path, [candidate()])
        token = self.start()
        self.record_pass(token, COMMIT_A, TREE_A)
        later = datetime.now(timezone.utc) + timedelta(hours=1)
        self.assertEqual(recover_expired_leases_file(self.path, now=later)["recovered"], ["T1"])
        retry = self.start(now=later)
        self.assertEqual(load_queue(self.path)["items"][0]["attempts"], 2)
        with self.assertRaisesRegex(EvolutionError, "no PASS verification"):
            advance_task_file(self.path, "T1", "DONE", "done", token=retry, now=later,
                              commit_sha=COMMIT_A, tree_sha=TREE_A)
        self.forge_done(COMMIT_A, TREE_A)
        with self.assertRaisesRegex(EvolutionError, "without a PASS"):
            load_queue(self.path)

    # 10
    def test_run_tasks_cannot_set_done(self):
        update_queue_file(self.path, [candidate()])
        token = self.start()
        # A PASS that the version 2 path would have accepted: the digest of the live source tree.
        record_verification_file(
            self.path, "T1", "PASS", "unit", None, SOURCE, current_attempt(self.path, "T1"),
            source_tree_digest(ROOT / "autopoesis"), token,
        )
        with self.assertRaisesRegex(ValueError, "only by the coordinator"):
            run_tasks.execute_task(
                {"id": "status", "type": "update_task_status", "task_id": "T1", "status": "DONE",
                 "lease_token": token},
                self.path,
            )
        self.assertEqual(load_queue(self.path)["items"][0]["status"], "IN_PROGRESS")


class MigrationCommitBindingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "TASK_QUEUE.json"
        self.original = V2_FIXTURE.read_text(encoding="utf-8")
        self.path.write_text(self.original, encoding="utf-8")

    # 8
    def test_version_2_migration_keeps_the_old_semantics(self):
        result = migrate_queue_file(self.path)
        self.assertTrue(result["migrated"])
        self.assertEqual(Path(result["backup"]).read_text(encoding="utf-8"), self.original)
        source = json.loads(self.original)
        migrated = load_queue(self.path)
        self.assertEqual(migrated["version"], 3)
        self.assertEqual(migrated["legacy_history_length"], len(source["history"]))
        self.assertEqual((migrated["items"], migrated["history"]), (source["items"], source["history"]))
        done = [e for e in migrated["history"] if e.get("to") == "DONE"]
        self.assertEqual([e["revision_semantics"] for e in done], ["tested_source_snapshot_sha256"])
        self.assertFalse(any("commit_sha" in e or "tree_sha" in e for e in migrated["history"]))
        # T2 has a version 2 PASS; it names no commit, so it cannot complete T2 under any commit.
        token = next(i for i in migrated["items"] if i["id"] == "T2")["lease"]["token"]
        with self.assertRaisesRegex(EvolutionError, "no PASS verification"):
            advance_task_file(self.path, "T2", "DONE", "done", token=token, commit_sha=COMMIT_A, tree_sha=TREE_A)

    # 7
    def test_old_semantics_after_the_legacy_boundary_is_refused(self):
        migrate_queue_file(self.path)
        queue = json.loads(self.path.read_text(encoding="utf-8"))
        # Moving the boundary before T1's DONE turns it into a new event with the old semantics.
        done_index = next(i for i, e in enumerate(queue["history"]) if e.get("to") == "DONE")
        queue["legacy_history_length"] = done_index
        self.path.write_text(json.dumps(queue), encoding="utf-8")
        with self.assertRaisesRegex(EvolutionError, "does not match its bound PASS"):
            load_queue(self.path)

    def test_a_commit_bound_done_inside_the_legacy_boundary_is_refused(self):
        migrate_queue_file(self.path)
        token = next(i for i in load_queue(self.path)["items"] if i["id"] == "T2")["lease"]["token"]
        record_verification_file(self.path, "T2", "PASS", "unit", None, SOURCE, current_attempt(self.path, "T2"),
                                 None, token, commit_sha=COMMIT_A, tree_sha=TREE_A)
        advance_task_file(self.path, "T2", "DONE", "done", token=token, commit_sha=COMMIT_A, tree_sha=TREE_A)
        self.assertEqual(load_queue(self.path)["items"][1]["status"], "DONE")
        queue = json.loads(self.path.read_text(encoding="utf-8"))
        # Moving the boundary past the new DONE would make it legacy, and it carries no legacy revision.
        queue["legacy_history_length"] = len(queue["history"])
        self.path.write_text(json.dumps(queue), encoding="utf-8")
        with self.assertRaisesRegex(EvolutionError, "does not match its bound PASS"):
            load_queue(self.path)

    def test_malformed_legacy_boundary_is_refused(self):
        migrate_queue_file(self.path)
        queue = json.loads(self.path.read_text(encoding="utf-8"))
        for value in (-1, len(queue["history"]) + 1, True, "3", 1.0, None):
            with self.subTest(value=value):
                self.path.write_text(json.dumps({**queue, "legacy_history_length": value}), encoding="utf-8")
                with self.assertRaisesRegex(EvolutionError, "legacy_history_length"):
                    load_queue(self.path)
        source = json.loads(self.original)
        self.path.write_text(json.dumps({**source, "legacy_history_length": 0}), encoding="utf-8")
        with self.assertRaisesRegex(EvolutionError, "legacy_history_length"):
            migrate_queue_file(self.path)

    def test_clock_skew_cannot_move_events_across_the_boundary(self):
        # A clock behind the recorded events used to sort a new candidate into the legacy
        # prefix and push the last legacy event, here a DONE, out of it. Merging now appends.
        v1 = json.loads(V1_FIXTURE.read_text(encoding="utf-8"))
        for event in v1["history"]:
            event["at"] = "2999" + event["at"][4:]
        self.assertEqual(v1["history"][-1]["to"], "DONE")
        self.path.write_text(json.dumps(v1), encoding="utf-8")
        migrate_queue_file(self.path)
        before = load_queue(self.path)
        update_queue_file(self.path, [candidate("T9")])
        after = load_queue(self.path)
        boundary = before["legacy_history_length"]
        self.assertEqual(after["history"][:boundary], before["history"][:boundary])
        self.assertEqual((after["history"][-1]["event"], after["history"][-1]["task_id"]), ("CANDIDATE_ADDED", "T9"))

    def test_merging_candidates_after_migration_keeps_the_boundary(self):
        migrate_queue_file(self.path)
        before = load_queue(self.path)
        update_queue_file(self.path, [candidate("T9")])
        after = load_queue(self.path)
        boundary = before["legacy_history_length"]
        self.assertEqual(after["legacy_history_length"], boundary)
        self.assertEqual(after["history"][:boundary], before["history"][:boundary])

    # 12
    def test_migrating_a_version_3_queue_changes_nothing(self):
        first = migrate_queue_file(self.path)
        migrated = self.path.read_bytes()
        self.assertEqual(json.loads(migrated)["version"], 3)
        second = migrate_queue_file(self.path)
        self.assertEqual((first["migrated"], second["migrated"]), (True, False))
        self.assertEqual(self.path.read_bytes(), migrated)


class CycleCommitBindingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.dir = Path(temporary.name)
        self.repo = self.dir / "repo"
        self.repo.mkdir()
        self.commit, self.tree = make_repository(self.repo)
        self.path = self.dir / "TASK_QUEUE.json"
        update_queue_file(self.path, [candidate()])

    def run_with(self, handler, root=None):
        return orchestrator.run_cycle(self.path, "runner", root or self.repo, handlers={"verify_test_scaffold": handler})

    def done_events(self):
        return [e for e in load_queue(self.path)["history"] if e.get("to") == "DONE"]

    # 3
    def test_tree_that_is_not_the_commit_tree_is_recovery_required(self):
        real = orchestrator._snapshot

        def wrong_tree(root, destination):
            commit, _, path = real(root, destination)
            return commit, TREE_B, path

        with mock.patch.object(orchestrator, "_snapshot", wrong_tree):
            result = self.run_with(lambda item, root: {"verification_status": "PASS"})
        self.assertEqual(result["status"], "RECOVERY_REQUIRED")
        self.assertIn("is not the tree of commit", result["reason"])
        self.assertEqual(self.done_events(), [])

    # 4
    def test_working_tree_changed_after_testing_does_not_change_what_done_names(self):
        def mutate_checkout(item, root):
            tested = source_tree_digest(root / "autopoesis")
            # The checkout changes after the test; what DONE names must not depend on it.
            with (self.repo / "autopoesis" / "core.py").open("a", encoding="utf-8") as handle:
                handle.write("\n# changed after the test\n")
            return {"verification_status": "PASS", "revision": tested}

        result = self.run_with(mutate_checkout)
        self.assertEqual(result["status"], "COMPLETED")
        done = self.done_events()[0]
        self.assertEqual((done["commit_sha"], done["tree_sha"]), (self.commit, self.tree))
        self.assertEqual(done["revision_semantics"], "tested_commit_tree")

    # 5
    def test_dirty_working_tree_is_not_visible_to_the_handler(self):
        (self.repo / "autopoesis" / "untracked_marker.py").write_text("X = 1\n", encoding="utf-8")
        committed = (self.repo / "autopoesis" / "core.py").read_text(encoding="utf-8")
        (self.repo / "autopoesis" / "core.py").write_text(committed + "\n# uncommitted\n", encoding="utf-8")

        def sees_commit_only(item, root):
            clean = (
                not (root / "autopoesis" / "untracked_marker.py").exists()
                and (root / "autopoesis" / "core.py").read_text(encoding="utf-8") == committed
            )
            return {"verification_status": "PASS" if clean else "FAIL",
                    "revision": source_tree_digest(root / "autopoesis"), "detail": f"handler saw {root}"}

        result = self.run_with(sees_commit_only)
        self.assertEqual((result["status"], result["verification"]), ("COMPLETED", "PASS"))
        self.assertEqual(self.done_events()[0]["commit_sha"], self.commit)

    # 6
    def test_handler_writing_to_its_snapshot_does_not_change_the_recorded_tree(self):
        def writes_snapshot(item, root):
            (root / "autopoesis" / "core.py").write_text("# rewritten by the handler\n", encoding="utf-8")
            return {"verification_status": "PASS", "revision": source_tree_digest(root / "autopoesis")}

        before = (self.repo / "autopoesis" / "core.py").read_bytes()
        result = self.run_with(writes_snapshot)
        self.assertEqual((self.repo / "autopoesis" / "core.py").read_bytes(), before)
        self.assertEqual(result["status"], "COMPLETED")
        verification = [e for e in load_queue(self.path)["history"] if e["event"] == "VERIFICATION_RECORDED"][0]
        done = self.done_events()[0]
        self.assertEqual((verification["tree_sha"], done["tree_sha"]), (self.tree, self.tree))

    # 11
    def test_root_that_is_not_a_git_repository_is_recovery_required_without_writes(self):
        plain = self.dir / "plain"
        shutil.copytree(ROOT / "autopoesis", plain / "autopoesis", ignore=shutil.ignore_patterns("__pycache__"))
        before = self.path.read_bytes()
        result = self.run_with(
            lambda item, root: {"verification_status": "PASS", "revision": source_tree_digest(root / "autopoesis")},
            root=plain,
        )
        self.assertEqual(result["status"], "RECOVERY_REQUIRED")
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
