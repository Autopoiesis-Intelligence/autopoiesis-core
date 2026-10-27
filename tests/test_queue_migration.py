"""Version 1 -> 2 queue migration: no evidence upgraded, idempotent, restartable, fail-closed."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from autopoesis.core import EvolutionError
from autopoesis.task_queue import (
    QUEUE_VERSION,
    load_queue,
    main,
    migrate_queue,
    migrate_queue_file,
    update_queue_file,
)

# Written by the version 1 code of PR #45 (ba65d04): one task taken through orchestrator.run_cycle to DONE.
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "queue_v1_done_from_ba65d04.json"


class QueueMigrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "TASK_QUEUE.json"
        self.original = FIXTURE.read_text(encoding="utf-8")
        self.path.write_text(self.original, encoding="utf-8")
        self.backup = self.path.with_name("TASK_QUEUE.json.v1.bak")

    def v1(self):
        return json.loads(self.original)

    def test_version_1_is_refused_until_migrated(self):
        with self.assertRaisesRegex(EvolutionError, "must be migrated"):
            load_queue(self.path)

    def test_done_gets_the_bound_pass_revision_and_a_migrated_label(self):
        source = self.v1()
        migrated = migrate_queue(source)
        self.assertEqual(migrated["version"], QUEUE_VERSION)
        self.assertEqual(migrated["items"], source["items"])
        self.assertEqual(len(migrated["history"]), len(source["history"]))
        pass_event = next(e for e in source["history"] if e.get("verification_status") == "PASS")
        done = migrated["history"][-1]
        self.assertEqual(done["to"], "DONE")
        self.assertEqual(done["revision"], pass_event["revision"])
        self.assertEqual(done["revision_semantics"], "migrated_v1_bound_pass_revision")
        # Nothing else changes: every other event is byte-for-byte the same.
        stripped = {k: v for k, v in done.items() if k not in {"revision", "revision_semantics"}}
        self.assertEqual(migrated["history"][:-1] + [stripped], source["history"])

    def test_migration_is_idempotent(self):
        once = migrate_queue(self.v1())
        self.assertEqual(migrate_queue(once), once)
        first = migrate_queue_file(self.path)
        after_first = self.path.read_bytes()
        second = migrate_queue_file(self.path)
        self.assertEqual((first["migrated"], second["migrated"]), (True, False))
        self.assertEqual(self.path.read_bytes(), after_first)
        self.assertEqual(load_queue(self.path)["items"][0]["status"], "DONE")

    def test_backup_keeps_the_original_bytes(self):
        migrate_queue_file(self.path)
        self.assertEqual(self.backup.read_text(encoding="utf-8"), self.original)

    def test_interrupted_run_after_backup_resumes(self):
        # A crash between writing the backup and replacing the queue leaves both as version 1.
        self.backup.write_text(self.original, encoding="utf-8")
        self.assertTrue(migrate_queue_file(self.path)["migrated"])
        self.assertEqual(json.loads(self.path.read_text())["version"], QUEUE_VERSION)

    def test_conflicting_backup_is_refused_without_writes(self):
        self.backup.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(EvolutionError, "differs"):
            migrate_queue_file(self.path)
        self.assertEqual(self.path.read_text(encoding="utf-8"), self.original)
        self.assertEqual(self.backup.read_text(encoding="utf-8"), "{}")

    def test_done_without_a_bound_pass_is_refused(self):
        cases = {
            "pass removed": lambda q: q["history"].remove(next(e for e in q["history"] if e["event"] == "VERIFICATION_RECORDED")),
            "pass turned into fail": lambda q: next(e for e in q["history"] if e["event"] == "VERIFICATION_RECORDED").update(verification_status="FAIL"),
            "pass without revision": lambda q: next(e for e in q["history"] if e["event"] == "VERIFICATION_RECORDED").pop("revision"),
            "pass for another attempt": lambda q: next(e for e in q["history"] if e["event"] == "VERIFICATION_RECORDED").update(attempt=2),
        }
        for label, mutate in cases.items():
            with self.subTest(label):
                queue = self.v1()
                mutate(queue)
                self.path.write_text(json.dumps(queue), encoding="utf-8")
                before = self.path.read_bytes()
                with self.assertRaises(EvolutionError):
                    migrate_queue_file(self.path)
                self.assertEqual(self.path.read_bytes(), before)
                self.assertFalse(self.backup.exists())

    def test_corrupt_and_unknown_versions_are_refused(self):
        for label, text in {"torn": self.original[:40], "version 3": json.dumps({**self.v1(), "version": 3})}.items():
            with self.subTest(label):
                self.path.write_text(text, encoding="utf-8")
                with self.assertRaises(EvolutionError):
                    migrate_queue_file(self.path)
                self.assertEqual(self.path.read_text(encoding="utf-8"), text)
                self.assertFalse(self.backup.exists())

    def test_migrated_label_cannot_carry_a_different_revision(self):
        queue = migrate_queue(self.v1())
        forged = copy.deepcopy(queue)
        forged["history"][-1]["revision"] = "f" * 64
        self.path.write_text(json.dumps(forged), encoding="utf-8")
        with self.assertRaisesRegex(EvolutionError, "DONE revision"):
            load_queue(self.path)

    def test_migrated_queue_accepts_new_work(self):
        migrate_queue_file(self.path)
        update_queue_file(self.path, [{"id": "T2", "type": "verify_test_scaffold", "source": "autopoesis/core.py",
                                       "evidence": "after migration"}])
        self.assertEqual([i["status"] for i in load_queue(self.path)["items"]], ["DONE", "OPEN"])

    def test_cli_exit_codes(self):
        self.assertEqual(main(["migrate", "--queue", str(self.path)]), 0)
        self.path.write_text("{", encoding="utf-8")
        self.assertEqual(main(["migrate", "--queue", str(self.path)]), 3)


if __name__ == "__main__":
    unittest.main()
