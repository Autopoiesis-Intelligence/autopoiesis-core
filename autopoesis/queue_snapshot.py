"""Integrity helpers for CI task-queue snapshots."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from .task_queue import load_queue


_GIT_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
# ci.yml sets this run-name prefix on dispatches that inject a restore fault. Such a run must
# fail and never yields a selectable snapshot, so an expected failure does not block restore.
NEGATIVE_FAULT_TITLE_PREFIX = "Negative restore fault: "
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _run_id_text(value: str | int) -> str:
    if isinstance(value, bool):
        raise ValueError("Source run ID must contain decimal digits")
    text = str(value)
    if not text.isdigit():
        raise ValueError("Source run ID must contain decimal digits")
    return str(int(text))


def create_queue_snapshot_manifest(
    queue_path: Path,
    *,
    source_run_id: str | int,
    source_head_sha: str,
    source_repository: str,
) -> dict[str, Any]:
    """Create metadata binding a queue snapshot to its producing CI run."""
    if not queue_path.is_file():
        raise ValueError("Task queue snapshot file is missing")
    run_id = _run_id_text(source_run_id)
    if not isinstance(source_head_sha, str) or not _GIT_SHA.fullmatch(source_head_sha):
        raise ValueError("Source head SHA must be a 40-character hexadecimal commit hash")
    if not isinstance(source_repository, str) or not source_repository.strip():
        raise ValueError("Source repository must be a non-empty string")

    snapshot = queue_path.read_bytes()
    return {
        "source_run_id": int(run_id),
        "source_head_sha": source_head_sha.lower(),
        "source_repository": source_repository,
        "task_queue_sha256": hashlib.sha256(snapshot).hexdigest(),
        "task_queue_size_bytes": len(snapshot),
    }


def validate_queue_snapshot(
    snapshot_path: Path,
    manifest_path: Path,
    *,
    source_run_id: str | int,
    source_head_sha: str,
    source_repository: str,
) -> dict[str, Any]:
    """Validate snapshot provenance, byte integrity, size, and queue schema."""
    if not snapshot_path.is_file():
        raise ValueError("Queue snapshot file is missing")
    if not manifest_path.is_file():
        raise ValueError("Queue snapshot manifest file is missing")

    expected_run_id = _run_id_text(source_run_id)
    if not isinstance(source_head_sha, str) or not _GIT_SHA.fullmatch(source_head_sha):
        raise ValueError("Verified source head SHA must be a 40-character hexadecimal commit hash")
    if not isinstance(source_repository, str) or not source_repository.strip():
        raise ValueError("Verified source repository must be a non-empty string")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read queue snapshot manifest: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError("Queue snapshot manifest must be a JSON object")

    if str(manifest.get("source_run_id", "")) != expected_run_id:
        raise ValueError("Snapshot manifest run ID does not match verified source run")
    if manifest.get("source_head_sha") != source_head_sha.lower():
        raise ValueError("Snapshot manifest SHA does not match verified source run SHA")
    if manifest.get("source_repository") != source_repository:
        raise ValueError("Snapshot manifest repository does not match verified source repository")

    snapshot = snapshot_path.read_bytes()
    actual_digest = hashlib.sha256(snapshot).hexdigest()
    expected_digest = manifest.get("task_queue_sha256")
    if not isinstance(expected_digest, str) or not _SHA256.fullmatch(expected_digest):
        raise ValueError("Snapshot manifest has no valid task queue SHA-256")
    if expected_digest != actual_digest:
        raise ValueError("TASK_QUEUE.json SHA-256 does not match source snapshot manifest")

    expected_size = manifest.get("task_queue_size_bytes")
    if type(expected_size) is not int or expected_size < 0:
        raise ValueError("Snapshot manifest has no valid task queue size")
    if expected_size != len(snapshot):
        raise ValueError("TASK_QUEUE.json size does not match source snapshot manifest")

    queue = load_queue(snapshot_path)
    manifest_digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    return {
        "queue": queue,
        "source_manifest_sha256": manifest_digest,
        "task_queue_sha256": actual_digest,
        "task_queue_size_bytes": len(snapshot),
    }


def install_validated_queue_snapshot(
    snapshot_path: Path,
    destination_path: Path,
    *,
    expected_queue: dict[str, Any],
    expected_sha256: str,
    expected_size_bytes: int,
) -> dict[str, Any]:
    """Atomically install a previously validated queue snapshot.

    Stage in the destination directory, fsync and re-validate before replacing
    the destination. Any failure before os.replace leaves the old destination
    untouched.
    """
    if not snapshot_path.is_file():
        raise ValueError("Queue snapshot file is missing")
    if not isinstance(expected_sha256, str) or not _SHA256.fullmatch(expected_sha256):
        raise ValueError("Expected staged queue SHA-256 must be a 64-character lowercase hexadecimal digest")
    if type(expected_size_bytes) is not int or expected_size_bytes < 0:
        raise ValueError("Expected staged queue size must be a non-negative integer")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    staged_path: Path | None = None
    try:
        fd, staged_name = tempfile.mkstemp(
            prefix=f".{destination_path.name}.",
            suffix=".staged",
            dir=destination_path.parent,
        )
        staged_path = Path(staged_name)
        with os.fdopen(fd, "wb") as staged:
            with snapshot_path.open("rb") as source:
                while chunk := source.read(1024 * 1024):
                    staged.write(chunk)
            staged.flush()
            os.fsync(staged.fileno())

        staged_bytes = staged_path.read_bytes()
        staged_digest = hashlib.sha256(staged_bytes).hexdigest()
        if staged_digest != expected_sha256:
            raise ValueError("Staged queue SHA-256 differs from validated source snapshot")
        if len(staged_bytes) != expected_size_bytes:
            raise ValueError("Staged queue size differs from validated source snapshot")

        staged_queue = load_queue(staged_path)
        if staged_queue != expected_queue:
            raise ValueError("Staged queue differs from validated source queue")

        os.replace(staged_path, destination_path)
        staged_path = None
        installed_queue = load_queue(destination_path)
        if installed_queue != expected_queue:
            raise ValueError("Installed queue differs from validated source queue")
        return {
            "destination": str(destination_path),
            "size_bytes": destination_path.stat().st_size,
        }
    finally:
        if staged_path is not None:
            try:
                staged_path.unlink()
            except FileNotFoundError:
                pass


def validate_restore_source_run(
    run: Any,
    *,
    requested_run_id: str | int,
    expected_repository: str,
    expected_workflow_path: str = ".github/workflows/ci.yml",
) -> dict[str, Any]:
    """Validate the GitHub run metadata before trusting its artifact list."""
    if not isinstance(run, dict):
        raise ValueError("Source run metadata must be a JSON object")
    expected_id = _run_id_text(requested_run_id)
    if str(run.get("id", "")) != expected_id:
        raise ValueError("Source run ID does not match restore_run_id")
    if run.get("run_attempt") != 1:
        raise ValueError(
            "Source run must be the original attempt (run_attempt=1); "
            f"got {run.get('run_attempt')!r}"
        )
    if run.get("conclusion") != "success":
        raise ValueError(
            f"Source run must have conclusion=success; got {run.get('conclusion')!r}"
        )
    if run.get("event") != "workflow_dispatch":
        raise ValueError(
            "Source run must be an explicit workflow_dispatch seed run; "
            f"got {run.get('event')!r}"
        )
    path = run.get("path")
    workflow_path = path.split("@", 1)[0] if isinstance(path, str) else ""
    if workflow_path != expected_workflow_path:
        raise ValueError(
            f"Source run must use {expected_workflow_path}; got {path!r}"
        )
    repository_data = run.get("repository")
    repository = (
        repository_data.get("full_name")
        if isinstance(repository_data, dict)
        else None
    )
    if repository != expected_repository:
        raise ValueError("Source run belongs to a different repository")
    source_sha = run.get("head_sha")
    if not isinstance(source_sha, str) or not _GIT_SHA.fullmatch(source_sha):
        raise ValueError(
            "Source run does not expose a valid 40-character hexadecimal head SHA"
        )
    return {
        "source_run_id": run["id"],
        "source_run_url": run.get("html_url"),
        "source_repository": repository,
        "source_workflow_path": workflow_path,
        "source_head_sha": source_sha.lower(),
        "source_conclusion": run["conclusion"],
    }


def bind_source_artifact(
    provenance: dict[str, Any],
    artifacts_payload: Any,
    *,
    requested_run_id: str | int,
    expected_artifact_name: str = "autopoesis-core-results",
) -> dict[str, Any]:
    """Require one unexpired artifact whose run ID and SHA match provenance."""
    if not isinstance(provenance, dict):
        raise ValueError("Verified source provenance must be a JSON object")
    if not isinstance(artifacts_payload, dict):
        raise ValueError("Source artifacts response must be a JSON object")
    artifacts = artifacts_payload.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("Source artifacts response must contain an artifacts array")

    expected_id = _run_id_text(requested_run_id)
    matches = [
        artifact for artifact in artifacts
        if isinstance(artifact, dict)
        and artifact.get("name") == expected_artifact_name
        and not artifact.get("expired", True)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Source run must contain exactly one unexpired {expected_artifact_name} artifact"
        )
    artifact = matches[0]
    artifact_run = artifact.get("workflow_run")
    if not isinstance(artifact_run, dict) or str(artifact_run.get("id", "")) != expected_id:
        raise ValueError("Source artifact is not bound to the requested run")
    if artifact_run.get("head_sha") != provenance.get("source_head_sha"):
        raise ValueError("Source artifact head SHA does not match source run")

    digest = artifact.get("digest")
    if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("Source artifact does not expose a valid SHA-256 archive digest")
    size = artifact.get("size_in_bytes")
    if type(size) is not int or size < 0:
        raise ValueError("Source artifact does not expose a valid size")

    return {
        **provenance,
        "source_artifact_id": artifact.get("id"),
        "source_artifact_name": artifact.get("name"),
        "source_artifact_digest": digest,
        "source_artifact_size_bytes": size,
        "source_artifact_created_at": artifact.get("created_at"),
    }


def latest_source_run_id(
    runs_payload: Any,
    *,
    current_run_id: str | int,
    current_branch: str,
    expected_workflow_path: str = ".github/workflows/ci.yml",
) -> int:
    """Return the newest successful dispatch run of the workflow on this branch."""
    if not isinstance(current_branch, str) or not current_branch:
        raise ValueError("Current branch must be a non-empty string")
    if not isinstance(runs_payload, dict):
        raise ValueError("Workflow runs response must be a JSON object")
    runs = runs_payload.get("workflow_runs")
    if not isinstance(runs, list):
        raise ValueError("Workflow runs response must contain a workflow_runs array")

    current_id = int(_run_id_text(current_run_id))
    candidates = []
    for index, run in enumerate(runs):
        if not isinstance(run, dict):
            raise ValueError(
                f"Workflow run history entry {index} must be a JSON object"
            )
        if type(run.get("id")) is not int:
            raise ValueError(
                f"Workflow run history entry {index} must contain an integer run ID"
            )
        path = run.get("path")
        workflow_path = path.split("@", 1)[0] if isinstance(path, str) else ""
        if (
            run["id"] != current_id
            and run.get("event") == "workflow_dispatch"
            and run.get("head_branch") == current_branch
            and workflow_path == expected_workflow_path
        ):
            candidates.append(run)
    if not candidates:
        raise ValueError(
            f"No successful workflow_dispatch snapshot run found on branch {current_branch!r}"
        )

    # Fail closed on the newest relevant run rather than silently rolling back
    # to an older successful snapshot when the latest dispatch failed/cancelled.
    newest = max(candidates, key=lambda candidate: candidate["id"])
    title = newest.get("display_title")
    if isinstance(title, str) and title.startswith(NEGATIVE_FAULT_TITLE_PREFIX):
        raise ValueError(
            f"Newest workflow_dispatch run {newest['id']} is a negative restore fault run; "
            "create a fresh successful seed snapshot before restoring"
        )
    if newest.get("run_attempt") != 1:
        raise ValueError(
            f"No successful workflow_dispatch snapshot run: newest workflow_dispatch "
            f"snapshot run {newest['id']} must have run_attempt=1; "
            f"got {newest.get('run_attempt')!r}"
        )
    if newest.get("conclusion") != "success":
        raise ValueError(
            f"No successful workflow_dispatch snapshot run: newest workflow_dispatch "
            f"snapshot run {newest['id']} must have conclusion=success; "
            f"got {newest.get('conclusion')!r}"
        )
    return newest["id"]


def require_latest_source_run(
    provenance: dict[str, Any],
    runs_payload: Any,
    *,
    current_run_id: str | int,
    current_branch: str,
    expected_workflow_path: str = ".github/workflows/ci.yml",
) -> dict[str, Any]:
    """Reject replay: the source must be the newest successful dispatch run on this branch."""
    if not isinstance(provenance, dict):
        raise ValueError("Verified source provenance must be a JSON object")
    source_id = int(_run_id_text(provenance.get("source_run_id", "")))
    latest_id = latest_source_run_id(
        runs_payload,
        current_run_id=current_run_id,
        current_branch=current_branch,
        expected_workflow_path=expected_workflow_path,
    )
    if source_id != latest_id:
        raise ValueError(
            f"Source run {source_id} is not the latest snapshot on branch "
            f"{current_branch!r}; latest is {latest_id}"
        )
    return {**provenance, "source_branch": current_branch, "source_is_latest": True}
