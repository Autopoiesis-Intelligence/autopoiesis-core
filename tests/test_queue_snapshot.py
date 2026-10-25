"""Focused tests for queue snapshot integrity and restore provenance."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from autopoesis.queue_snapshot import (
    bind_source_artifact,
    create_queue_snapshot_manifest,
    install_validated_queue_snapshot,
    validate_queue_snapshot,
    validate_restore_source_run,
)


REPOSITORY = "Autopoiesis-Intelligence/autopoiesis-core"
SHA = "a" * 40
RUN_ID = 12345
ARTIFACT_DIGEST = "sha256:" + "b" * 64


class QueueSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.snapshot = self.root / "TASK_QUEUE.json"
        self.manifest = self.root / "QUEUE_SNAPSHOT_MANIFEST.json"
        self.snapshot.write_text(
            json.dumps({"version": 1, "items": [], "history": []}) + "\n",
            encoding="utf-8",
        )

    def write_manifest(self, manifest):
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")

    def valid_manifest(self):
        return create_queue_snapshot_manifest(
            self.snapshot,
            source_run_id=RUN_ID,
            source_head_sha=SHA,
            source_repository=REPOSITORY,
        )

    def valid_run(self):
        return {
            "id": RUN_ID,
            "run_attempt": 1,
            "conclusion": "success",
            "event": "workflow_dispatch",
            "path": ".github/workflows/ci.yml@refs/heads/main",
            "repository": {"full_name": REPOSITORY},
            "head_sha": SHA,
            "html_url": "https://github.com/example/run/12345",
        }

    def valid_provenance(self):
        return validate_restore_source_run(
            self.valid_run(),
            requested_run_id=RUN_ID,
            expected_repository=REPOSITORY,
        )

    def valid_artifacts(self):
        return {
            "artifacts": [{
                "id": 77,
                "name": "autopoesis-core-results",
                "expired": False,
                "digest": ARTIFACT_DIGEST,
                "size_in_bytes": 1024,
                "workflow_run": {"id": RUN_ID, "head_sha": SHA},
            }]
        }

    def test_atomic_install_replaces_destination_with_validated_queue(self):
        destination = self.root / "installed" / "TASK_QUEUE.json"
        destination.parent.mkdir()
        old_bytes = b'{"version": 1, "items": [], "history": []}\\n'
        destination.write_bytes(old_bytes)
        expected = {"version": 1, "items": [], "history": []}

        result = install_validated_queue_snapshot(
            self.snapshot,
            destination,
            expected_queue=expected,
            expected_sha256=hashlib.sha256(self.snapshot.read_bytes()).hexdigest(),
            expected_size_bytes=self.snapshot.stat().st_size,
        )

        self.assertEqual(json.loads(destination.read_text(encoding="utf-8")), expected)
        self.assertEqual(result["size_bytes"], self.snapshot.stat().st_size)
        self.assertFalse(list(destination.parent.glob("*.staged")))

    def test_atomic_install_replace_failure_preserves_existing_destination(self):
        destination = self.root / "installed" / "TASK_QUEUE.json"
        destination.parent.mkdir()
        old_bytes = b'{"version": 1, "items": [], "history": []}\\n'
        destination.write_bytes(old_bytes)

        with patch(
            "autopoesis.queue_snapshot.os.replace",
            side_effect=OSError("simulated replace failure"),
        ):
            with self.assertRaisesRegex(OSError, "simulated replace failure"):
                install_validated_queue_snapshot(
                    self.snapshot,
                    destination,
                    expected_queue={"version": 1, "items": [], "history": []},
                    expected_sha256=hashlib.sha256(self.snapshot.read_bytes()).hexdigest(),
                    expected_size_bytes=self.snapshot.stat().st_size,
                )

        self.assertEqual(destination.read_bytes(), old_bytes)
        self.assertEqual(list(destination.parent.glob("*.staged")), [])

    def test_atomic_install_rejects_staged_queue_mismatch_without_replacing(self):
        destination = self.root / "installed" / "TASK_QUEUE.json"
        destination.parent.mkdir()
        old_bytes = b'{"version": 1, "items": [], "history": []}\\n'
        destination.write_bytes(old_bytes)

        with self.assertRaisesRegex(ValueError, "Staged queue differs"):
            install_validated_queue_snapshot(
                self.snapshot,
                destination,
                expected_queue={"version": 1, "items": [{"id": "unexpected"}], "history": []},
                expected_sha256=hashlib.sha256(self.snapshot.read_bytes()).hexdigest(),
                expected_size_bytes=self.snapshot.stat().st_size,
            )

        self.assertEqual(destination.read_bytes(), old_bytes)
        self.assertEqual(list(destination.parent.glob("*.staged")), [])

    def test_manifest_binds_snapshot_bytes_and_source(self):
        manifest = self.valid_manifest()
        self.assertEqual(manifest["source_run_id"], RUN_ID)
        self.assertEqual(manifest["source_head_sha"], SHA)
        self.assertEqual(manifest["source_repository"], REPOSITORY)
        self.write_manifest(manifest)

        result = validate_queue_snapshot(
            self.snapshot, self.manifest,
            source_run_id=RUN_ID,
            source_head_sha=SHA,
            source_repository=REPOSITORY,
        )
        self.assertEqual(result["queue"], {"version": 1, "items": [], "history": []})
        self.assertEqual(result["task_queue_sha256"], manifest["task_queue_sha256"])

    def test_manifest_rejects_wrong_run_sha_or_repository(self):
        manifest = self.valid_manifest()
        for field, value in (
            ("source_run_id", RUN_ID + 1),
            ("source_head_sha", "c" * 40),
            ("source_repository", "someone/else"),
        ):
            with self.subTest(field=field):
                changed = dict(manifest)
                changed[field] = value
                self.write_manifest(changed)
                with self.assertRaises(ValueError):
                    validate_queue_snapshot(
                        self.snapshot, self.manifest,
                        source_run_id=RUN_ID,
                        source_head_sha=SHA,
                        source_repository=REPOSITORY,
                    )

    def test_manifest_rejects_snapshot_byte_tampering(self):
        self.write_manifest(self.valid_manifest())
        self.snapshot.write_text('{"version":1,"items":[],"history":[]}\n ', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            validate_queue_snapshot(
                self.snapshot, self.manifest,
                source_run_id=RUN_ID,
                source_head_sha=SHA,
                source_repository=REPOSITORY,
            )

    def test_manifest_rejects_invalid_digest_and_size(self):
        original = self.valid_manifest()
        for field, value in (
            ("task_queue_sha256", "invalid"),
            ("task_queue_size_bytes", True),
            ("task_queue_size_bytes", -1),
        ):
            with self.subTest(field=field, value=value):
                changed = dict(original)
                changed[field] = value
                self.write_manifest(changed)
                with self.assertRaises(ValueError):
                    validate_queue_snapshot(
                        self.snapshot, self.manifest,
                        source_run_id=RUN_ID,
                        source_head_sha=SHA,
                        source_repository=REPOSITORY,
                    )

    def test_manifest_rejects_missing_snapshot_or_manifest(self):
        with self.assertRaisesRegex(ValueError, "snapshot file is missing"):
            validate_queue_snapshot(
                self.root / "missing.json", self.manifest,
                source_run_id=RUN_ID, source_head_sha=SHA,
                source_repository=REPOSITORY,
            )
        with self.assertRaisesRegex(ValueError, "manifest file is missing"):
            validate_queue_snapshot(
                self.snapshot, self.manifest,
                source_run_id=RUN_ID, source_head_sha=SHA,
                source_repository=REPOSITORY,
            )

    def test_manifest_rejects_malformed_json(self):
        self.manifest.write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Cannot read queue snapshot manifest"):
            validate_queue_snapshot(
                self.snapshot, self.manifest,
                source_run_id=RUN_ID, source_head_sha=SHA,
                source_repository=REPOSITORY,
            )

    def test_manifest_creation_rejects_invalid_source_metadata(self):
        for run_id, sha, repository in (
            (True, SHA, REPOSITORY),
            ("12x", SHA, REPOSITORY),
            (RUN_ID, "not-a-sha", REPOSITORY),
            (RUN_ID, SHA, " "),
        ):
            with self.subTest(run_id=run_id, sha=sha, repository=repository):
                with self.assertRaises(ValueError):
                    create_queue_snapshot_manifest(
                        self.snapshot, source_run_id=run_id,
                        source_head_sha=sha, source_repository=repository,
                    )

    def test_restore_run_rejects_rerun_attempt(self):
        run = self.valid_run()
        run["run_attempt"] = 2
        with self.assertRaisesRegex(ValueError, "original attempt"):
            validate_restore_source_run(
                run,
                requested_run_id=RUN_ID,
                expected_repository=REPOSITORY,
            )

    def test_restore_run_accepts_valid_workflow_dispatch_run(self):
        result = self.valid_provenance()
        self.assertEqual(result["source_run_id"], RUN_ID)
        self.assertEqual(result["source_head_sha"], SHA)
        self.assertEqual(result["source_repository"], REPOSITORY)

    def test_restore_run_rejects_wrong_identity_or_untrusted_run(self):
        cases = (
            ({"id": RUN_ID + 1}, "run ID"),
            ({"conclusion": "failure"}, "conclusion=success"),
            ({"event": "pull_request"}, "workflow_dispatch"),
            ({"path": ".github/workflows/other.yml@refs/heads/main"}, "workflow"),
            ({"repository": {"full_name": "other/repo"}}, "different repository"),
            ({"head_sha": "bad"}, "valid 40-character"),
        )
        for change, message in cases:
            with self.subTest(change=change):
                run = self.valid_run()
                run.update(change)
                with self.assertRaisesRegex(ValueError, message):
                    validate_restore_source_run(
                        run, requested_run_id=RUN_ID,
                        expected_repository=REPOSITORY,
                    )

    def test_restore_run_rejects_non_object_and_invalid_requested_id(self):
        with self.assertRaisesRegex(ValueError, "JSON object"):
            validate_restore_source_run(
                [], requested_run_id=RUN_ID, expected_repository=REPOSITORY,
            )
        with self.assertRaisesRegex(ValueError, "decimal digits"):
            validate_restore_source_run(
                self.valid_run(), requested_run_id="12x",
                expected_repository=REPOSITORY,
            )

    def test_artifact_binding_accepts_matching_unexpired_artifact(self):
        result = bind_source_artifact(
            self.valid_provenance(), self.valid_artifacts(),
            requested_run_id=RUN_ID,
        )
        self.assertEqual(result["source_artifact_id"], 77)
        self.assertEqual(result["source_artifact_digest"], ARTIFACT_DIGEST)
        self.assertEqual(result["source_artifact_size_bytes"], 1024)

    def test_artifact_binding_rejects_missing_duplicate_or_expired_artifact(self):
        cases = (
            {"artifacts": []},
            {"artifacts": [
                self.valid_artifacts()["artifacts"][0],
                self.valid_artifacts()["artifacts"][0],
            ]},
            {"artifacts": [{**self.valid_artifacts()["artifacts"][0], "expired": True}]},
        )
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(ValueError, "exactly one unexpired"):
                    bind_source_artifact(
                        self.valid_provenance(), payload, requested_run_id=RUN_ID,
                    )

    def test_artifact_binding_rejects_run_sha_digest_and_size_mismatch(self):
        artifact = self.valid_artifacts()["artifacts"][0]
        cases = (
            ({**artifact, "workflow_run": {"id": RUN_ID + 1, "head_sha": SHA}}, "requested run"),
            ({**artifact, "workflow_run": {"id": RUN_ID, "head_sha": "c" * 40}}, "head SHA"),
            ({**artifact, "digest": "invalid"}, "SHA-256 archive digest"),
            ({**artifact, "size_in_bytes": True}, "valid size"),
        )
        for changed, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    bind_source_artifact(
                        self.valid_provenance(), {"artifacts": [changed]},
                        requested_run_id=RUN_ID,
                    )


if __name__ == "__main__":
    unittest.main()
