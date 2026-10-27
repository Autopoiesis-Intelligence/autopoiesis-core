"""Negative-path and multi-run regression tests for persisted queue snapshots."""

import json
import tempfile
import unittest
from pathlib import Path

from autopoesis.core import EvolutionError
from autopoesis.queue_snapshot import (
    bind_source_artifact,
    create_queue_snapshot_manifest,
    latest_source_run_id,
    require_latest_source_run,
    validate_queue_snapshot,
    validate_restore_source_run,
)
from autopoesis.task_queue import load_queue, update_queue_file
from run_tasks import run


class QueueSnapshotValidationTests(unittest.TestCase):
    def test_corrupt_json_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "TASK_QUEUE.json"
            snapshot.write_text('{"version": 1, "items": [', encoding="utf-8")

            with self.assertRaises(EvolutionError):
                load_queue(snapshot)

    def test_unsupported_snapshot_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "TASK_QUEUE.json"
            snapshot.write_text(json.dumps({
                "version": 999,
                "items": [],
                "history": [],
            }), encoding="utf-8")

            with self.assertRaises(EvolutionError):
                load_queue(snapshot)

    def test_boolean_and_float_snapshot_versions_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "TASK_QUEUE.json"
            for version in (True, 1.0):
                with self.subTest(version=version):
                    snapshot.write_text(json.dumps({
                        "version": version,
                        "items": [],
                        "history": [],
                    }), encoding="utf-8")
                    with self.assertRaises(EvolutionError):
                        load_queue(snapshot)

    def test_invalid_task_status_in_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "TASK_QUEUE.json"
            snapshot.write_text(json.dumps({
                "version": 1,
                "items": [{"id": "TASK-1", "status": "UNKNOWN"}],
                "history": [],
            }), encoding="utf-8")

            with self.assertRaises(EvolutionError):
                load_queue(snapshot)

    def test_missing_snapshot_loads_as_empty_queue_at_loader_boundary(self):
        # The CI workflow separately checks is_file() before calling load_queue().
        # This documents why that workflow guard is required: the general-purpose
        # loader intentionally treats a missing local queue as an empty queue.
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "missing-TASK_QUEUE.json"

            self.assertEqual(
                load_queue(snapshot),
                {"version": 1, "items": [], "history": []},
            )

    def test_generated_test_verification_is_persisted_without_marking_task_done(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue_path = root / "TASK_QUEUE.json"
            tasks_path = root / "TASKS.json"
            results_path = root / "RESULTS.json"
            tasks_path.write_text(json.dumps({"tasks": [{
                "id": "CORE-007-PERSIST",
                "type": "verify_test_patch_sandbox",
                "source": "autopoesis/task_queue.py",
            }]}), encoding="utf-8")

            self.assertEqual(run(tasks_path, results_path, queue_path), 0)
            results = json.loads(results_path.read_text(encoding="utf-8"))
            queue = load_queue(queue_path)

            self.assertEqual(results["tasks"][0]["status"], "PASS")
            self.assertTrue(results["tasks"][0]["result"]["generated_code_executed"])
            self.assertEqual(len(queue["history"]), 1)
            evidence = queue["history"][0]
            self.assertEqual(evidence["event"], "VERIFICATION_RECORDED")
            self.assertEqual(evidence["task_id"], "CORE-007-PERSIST")
            self.assertEqual(evidence["verification_status"], "PASS")
            self.assertEqual(evidence["verification_level"], "GENERATED_TEST_EXECUTION")
            self.assertEqual(len(evidence["artifact_sha256"]), 64)
            self.assertEqual(queue["items"], [])

    def test_status_and_history_survive_two_runner_invocations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            queue_path = root / "TASK_QUEUE.json"
            tasks_path = root / "TASKS.json"
            results_path = root / "RESULTS.json"
            candidate = {
                "id": "PERSIST-STATUS-001",
                "type": "proposal",
                "source": "tests/example.py",
                "evidence": "multi-run persistence regression",
                "description": "Keep this task status and history across runs.",
            }
            update_queue_file(queue_path, [candidate])
            from autopoesis.task_queue import record_verification_file
            record_verification_file(
                queue_path,
                candidate["id"],
                "PASS",
                "GENERATED_TEST_EXECUTION",
                "f" * 64,
            )

            tasks_path.write_text(json.dumps({"tasks": [{
                "id": "set-status",
                "type": "update_task_status",
                "task_id": candidate["id"],
                "status": "DONE",
                "note": "first invocation",
            }]}), encoding="utf-8")
            self.assertEqual(run(tasks_path, results_path, queue_path), 0)
            after_first_run = load_queue(queue_path)
            prior_history = list(after_first_run["history"])
            self.assertEqual(after_first_run["items"][0]["status"], "DONE")

            tasks_path.write_text(json.dumps({"tasks": [{
                "id": "merge-discovery",
                "type": "queue_discovered_tasks",
            }]}), encoding="utf-8")
            self.assertEqual(run(tasks_path, results_path, queue_path), 0)
            after_second_run = load_queue(queue_path)

            persisted_item = next(
                item for item in after_second_run["items"]
                if item["id"] == candidate["id"]
            )
            self.assertEqual(persisted_item["status"], "DONE")
            self.assertEqual(
                [event for event in after_second_run["history"] if event in prior_history],
                prior_history,
            )
            self.assertGreaterEqual(len(after_second_run["history"]), len(prior_history))


    def _write_bound_snapshot(self, root):
        snapshot = root / "TASK_QUEUE.json"
        manifest_path = root / "QUEUE_SNAPSHOT_MANIFEST.json"
        update_queue_file(snapshot, [{"id": "RESTORE-1", "type": "probe"}])
        expected = {
            "source_run_id": 12345,
            "source_head_sha": "a" * 40,
            "source_repository": "Autopoiesis-Intelligence/autopoesis-core",
        }
        manifest = create_queue_snapshot_manifest(snapshot, **expected)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return snapshot, manifest_path, expected, manifest

    def test_snapshot_manifest_round_trip_binds_queue_to_source(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot, manifest_path, expected, manifest = self._write_bound_snapshot(
                Path(directory)
            )

            result = validate_queue_snapshot(
                snapshot, manifest_path, **expected
            )

            self.assertEqual(result["queue"], load_queue(snapshot))
            self.assertEqual(result["task_queue_sha256"], manifest["task_queue_sha256"])
            self.assertEqual(result["task_queue_size_bytes"], manifest["task_queue_size_bytes"])
            self.assertEqual(len(result["source_manifest_sha256"]), 64)

    def test_snapshot_validation_rejects_wrong_source_run_sha_or_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot, manifest_path, expected, _manifest = self._write_bound_snapshot(
                Path(directory)
            )
            wrong_sources = (
                ({**expected, "source_run_id": 54321}, "run ID"),
                ({**expected, "source_head_sha": "b" * 40}, "SHA"),
                ({**expected, "source_repository": "someone/else"}, "repository"),
            )

            for source, message in wrong_sources:
                with self.subTest(source=source), self.assertRaisesRegex(ValueError, message):
                    validate_queue_snapshot(snapshot, manifest_path, **source)

    def test_snapshot_validation_rejects_tampered_queue_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot, manifest_path, expected, _manifest = self._write_bound_snapshot(
                Path(directory)
            )
            snapshot.write_bytes(snapshot.read_bytes() + b" ")

            with self.assertRaisesRegex(ValueError, "SHA-256"):
                validate_queue_snapshot(snapshot, manifest_path, **expected)

    def test_snapshot_validation_rejects_wrong_queue_size(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot, manifest_path, expected, manifest = self._write_bound_snapshot(
                Path(directory)
            )
            manifest["task_queue_size_bytes"] += 1
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "size"):
                validate_queue_snapshot(snapshot, manifest_path, **expected)

    def test_snapshot_validation_fails_closed_when_snapshot_or_manifest_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot, manifest_path, expected, _manifest = self._write_bound_snapshot(root)
            snapshot.unlink()
            with self.assertRaisesRegex(ValueError, "snapshot file is missing"):
                validate_queue_snapshot(snapshot, manifest_path, **expected)

            snapshot, manifest_path, expected, _manifest = self._write_bound_snapshot(root)
            manifest_path.unlink()
            with self.assertRaisesRegex(ValueError, "manifest file is missing"):
                validate_queue_snapshot(snapshot, manifest_path, **expected)


    def _valid_source_run(self):
        return {
            "id": 12345,
            "conclusion": "success",
            "event": "workflow_dispatch",
            "path": ".github/workflows/ci.yml@refs/heads/main",
            "repository": {
                "full_name": "Autopoiesis-Intelligence/autopoesis-core",
            },
            "head_sha": "a" * 40,
            "html_url": "https://github.com/Autopoiesis-Intelligence/autopoesis-core/actions/runs/12345",
        }

    def test_source_run_validation_accepts_expected_seed_run(self):
        provenance = validate_restore_source_run(
            self._valid_source_run(),
            requested_run_id=12345,
            expected_repository="Autopoiesis-Intelligence/autopoesis-core",
        )

        self.assertEqual(provenance["source_run_id"], 12345)
        self.assertEqual(provenance["source_head_sha"], "a" * 40)
        self.assertEqual(provenance["source_workflow_path"], ".github/workflows/ci.yml")
        self.assertEqual(provenance["source_conclusion"], "success")

    def test_source_run_validation_normalizes_leading_zero_run_id(self):
        provenance = validate_restore_source_run(
            self._valid_source_run(),
            requested_run_id="00012345",
            expected_repository="Autopoiesis-Intelligence/autopoesis-core",
        )
        self.assertEqual(provenance["source_run_id"], 12345)

    def test_source_run_validation_rejects_wrong_identity_status_event_workflow_or_repo(self):
        valid = self._valid_source_run()
        cases = (
            ("wrong run ID", {**valid, "id": 54321}, "ID"),
            ("failed source", {**valid, "conclusion": "failure"}, "conclusion=success"),
            ("wrong event", {**valid, "event": "pull_request"}, "workflow_dispatch"),
            ("wrong workflow", {**valid, "path": ".github/workflows/other.yml@refs/heads/main"}, "must use"),
            (
                "wrong repository",
                {**valid, "repository": {"full_name": "someone/else"}},
                "different repository",
            ),
            ("invalid commit SHA", {**valid, "head_sha": "not-a-sha"}, "valid 40-character"),
        )

        for label, run, message in cases:
            with self.subTest(case=label), self.assertRaisesRegex(ValueError, message):
                validate_restore_source_run(
                    run,
                    requested_run_id=12345,
                    expected_repository="Autopoiesis-Intelligence/autopoesis-core",
                )

    def test_source_artifact_validation_accepts_exact_run_binding(self):
        source = validate_restore_source_run(
            self._valid_source_run(),
            requested_run_id=12345,
            expected_repository="Autopoiesis-Intelligence/autopoesis-core",
        )
        artifact = {
            "id": 67890,
            "name": "autopoesis-core-results",
            "expired": False,
            "workflow_run": {"id": 12345, "head_sha": "a" * 40},
            "digest": "sha256:" + "b" * 64,
            "size_in_bytes": 4096,
            "created_at": "2026-10-19T08:00:00Z",
        }

        bound = bind_source_artifact(
            source,
            {"artifacts": [artifact]},
            requested_run_id=12345,
        )

        self.assertEqual(bound["source_artifact_id"], 67890)
        self.assertEqual(bound["source_artifact_digest"], artifact["digest"])
        self.assertEqual(bound["source_artifact_size_bytes"], 4096)

    def test_source_artifact_validation_rejects_missing_duplicate_or_unbound_artifacts(self):
        source = validate_restore_source_run(
            self._valid_source_run(),
            requested_run_id=12345,
            expected_repository="Autopoiesis-Intelligence/autopoesis-core",
        )
        artifact = {
            "id": 67890,
            "name": "autopoesis-core-results",
            "expired": False,
            "workflow_run": {"id": 12345, "head_sha": "a" * 40},
            "digest": "sha256:" + "b" * 64,
            "size_in_bytes": 4096,
        }
        cases = (
            ({"artifacts": []}, "exactly one"),
            ({"artifacts": [{**artifact, "expired": True}]}, "exactly one"),
            ({"artifacts": [artifact, artifact]}, "exactly one"),
            (
                {"artifacts": [{**artifact, "workflow_run": {"id": 999, "head_sha": "a" * 40}}]},
                "not bound",
            ),
            (
                {"artifacts": [{**artifact, "workflow_run": {"id": 12345, "head_sha": "c" * 40}}]},
                "head SHA",
            ),
            ({"artifacts": [{**artifact, "digest": "sha256:invalid"}]}, "valid SHA-256"),
            ({"artifacts": [{**artifact, "size_in_bytes": "4096"}]}, "valid size"),
        )

        for payload, message in cases:
            with self.subTest(payload=payload), self.assertRaisesRegex(ValueError, message):
                bind_source_artifact(source, payload, requested_run_id=12345)


    def _dispatch_run(self, run_id, **overrides):
        run = {
            "id": run_id,
            "conclusion": "success",
            "event": "workflow_dispatch",
            "head_branch": "main",
            "path": ".github/workflows/ci.yml@refs/heads/main",
        }
        return {**run, **overrides}

    def _latest_check(self, source_run_id, runs, current_run_id=500):
        return require_latest_source_run(
            {"source_run_id": source_run_id},
            {"workflow_runs": runs},
            current_run_id=current_run_id,
            current_branch="main",
        )

    def test_latest_source_run_is_accepted_and_recorded(self):
        runs = [self._dispatch_run(500, conclusion=None), self._dispatch_run(300), self._dispatch_run(200)]

        provenance = self._latest_check(300, runs)

        self.assertTrue(provenance["source_is_latest"])
        self.assertEqual(provenance["source_branch"], "main")

    def test_older_snapshot_replay_is_rejected(self):
        runs = [self._dispatch_run(300), self._dispatch_run(200)]

        with self.assertRaisesRegex(ValueError, "not the latest snapshot.*latest is 300"):
            self._latest_check(200, runs)

    def test_runs_that_cannot_hold_a_snapshot_do_not_count_as_newer(self):
        runs = [
            self._dispatch_run(500),
            self._dispatch_run(450, conclusion="failure"),
            self._dispatch_run(440, event="push"),
            self._dispatch_run(430, head_branch="other"),
            self._dispatch_run(420, path=".github/workflows/other.yml@refs/heads/main"),
            self._dispatch_run("410"),
            "not-a-run",
            self._dispatch_run(300),
        ]

        self.assertTrue(self._latest_check(300, runs)["source_is_latest"])

    def test_source_from_another_branch_is_rejected(self):
        runs = [self._dispatch_run(300, head_branch="other"), self._dispatch_run(200)]

        with self.assertRaisesRegex(ValueError, "not the latest snapshot.*latest is 200"):
            self._latest_check(300, runs)

    def test_automatic_selection_picks_newest_eligible_run_and_skips_the_current_one(self):
        runs = [
            self._dispatch_run(500),
            self._dispatch_run(450, conclusion="failure"),
            self._dispatch_run(300),
            self._dispatch_run(200),
        ]

        self.assertEqual(
            latest_source_run_id({"workflow_runs": runs}, current_run_id=500, current_branch="main"),
            300,
        )

    def test_automatic_selection_fails_closed_without_an_eligible_run(self):
        runs = [self._dispatch_run(500), self._dispatch_run(300, head_branch="other")]

        with self.assertRaisesRegex(ValueError, "No successful workflow_dispatch"):
            latest_source_run_id({"workflow_runs": runs}, current_run_id=500, current_branch="main")

    def test_latest_check_fails_closed_on_missing_or_malformed_run_list(self):
        cases = (
            ("no candidate runs", {"workflow_runs": []}, "No successful workflow_dispatch"),
            ("missing array", {}, "workflow_runs array"),
            ("not an object", [], "JSON object"),
        )
        for label, payload, message in cases:
            with self.subTest(case=label), self.assertRaisesRegex(ValueError, message):
                require_latest_source_run(
                    {"source_run_id": 300},
                    payload,
                    current_run_id=500,
                    current_branch="main",
                )


if __name__ == "__main__":
    unittest.main()
