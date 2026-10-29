"""Persistent, deterministic task queue primitives."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX platforms
    fcntl = None

from .core import EvolutionError, canonical_json


QUEUE_VERSION = 1
QUEUE_STATUSES = {"OPEN", "SELECTED", "IN_PROGRESS", "DONE", "REJECTED"}
QUEUE_HISTORY_EVENTS = {"CANDIDATE_ADDED", "STATUS_CHANGED", "VERIFICATION_RECORDED"}


def _write_queue_atomically(path: Path, queue: dict[str, Any]) -> None:
    """Write a complete queue snapshot before atomically replacing the old one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(queue, indent=2, ensure_ascii=False) + "\n"
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        mode = None

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            if mode is not None:
                os.fchmod(stream.fileno(), mode)
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


@contextmanager
def queue_write_lock(path: Path) -> Iterator[None]:
    """Hold an exclusive, non-blocking lock for one load-modify-write cycle.

    Atomic replacement alone prevents torn files but not lost updates: two
    writers that load the same snapshot would both succeed and the second
    would silently discard the first. A concurrent writer is rejected
    instead of waiting, so a caller never reports success for an update
    that another writer overwrote. The lock is not reentrant: do not nest
    helpers that take it, even in the same process.
    """
    if fcntl is None:
        raise EvolutionError("Task queue locking is not supported on this platform")
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")
    descriptor = os.open(
        lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600
    )
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise EvolutionError(
                f"Task queue {path.as_posix()} is locked by another writer"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def empty_queue() -> dict[str, Any]:
    return {"version": QUEUE_VERSION, "items": [], "history": []}


def _validate_history(history: list[Any]) -> None:
    """Reject malformed or unsupported queue history records."""
    for index, event in enumerate(history):
        prefix = f"Invalid task queue history entry at index {index}"
        if not isinstance(event, dict):
            raise EvolutionError(f"{prefix}: expected an object")
        event_type = event.get("event")
        if not isinstance(event_type, str) or event_type not in QUEUE_HISTORY_EVENTS:
            raise EvolutionError(f"{prefix}: unsupported event type {event_type!r}")
        task_id = event.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            raise EvolutionError(f"{prefix}: task_id must be a non-empty string")
        timestamp = event.get("at")
        if not isinstance(timestamp, str) or not timestamp.strip():
            raise EvolutionError(f"{prefix}: at must be a non-empty string")
        try:
            parsed_timestamp = datetime.fromisoformat(timestamp)
        except ValueError as exc:
            raise EvolutionError(f"{prefix}: at must be an ISO 8601 timestamp") from exc
        if parsed_timestamp.tzinfo is None or parsed_timestamp.utcoffset() is None:
            raise EvolutionError(f"{prefix}: at must include a timezone offset")
        if event_type == "STATUS_CHANGED":
            if not isinstance(event.get("from"), str) or event.get("from") not in QUEUE_STATUSES:
                raise EvolutionError(f"{prefix}: invalid source status")
            if not isinstance(event.get("to"), str) or event.get("to") not in QUEUE_STATUSES:
                raise EvolutionError(f"{prefix}: invalid destination status")
            if not isinstance(event.get("note"), str):
                raise EvolutionError(f"{prefix}: note must be a string")
        if event_type == "VERIFICATION_RECORDED":
            verification_status = event.get("verification_status")
            if not isinstance(verification_status, str) or verification_status not in {"PASS", "FAIL"}:
                raise EvolutionError(f"{prefix}: invalid verification status")
            level = event.get("verification_level")
            if not isinstance(level, str) or not level.strip():
                raise EvolutionError(f"{prefix}: verification_level must be a non-empty string")
            artifact_hash = event.get("artifact_sha256")
            if artifact_hash is not None and (
                not isinstance(artifact_hash, str)
                or len(artifact_hash) != 64
                or any(char not in "0123456789abcdef" for char in artifact_hash)
            ):
                raise EvolutionError(f"{prefix}: artifact_sha256 must be a lowercase SHA-256 hex digest")


def load_queue(path: Path) -> dict[str, Any]:
    """Load and validate a queue; a missing file means an empty queue."""
    try:
        raw_queue = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # Only a genuinely absent file represents a first-run empty queue.
        return empty_queue()
    except (OSError, UnicodeError) as exc:
        raise EvolutionError(f"Cannot read task queue: {exc}") from exc

    try:
        queue = json.loads(raw_queue)
    except json.JSONDecodeError as exc:
        raise EvolutionError(f"Cannot read task queue: {exc}") from exc
    if (
        not isinstance(queue, dict)
        or type(queue.get("version")) is not int
        or queue.get("version") != QUEUE_VERSION
    ):
        raise EvolutionError("Unsupported task queue format")
    if not isinstance(queue.get("items"), list) or not isinstance(queue.get("history"), list):
        raise EvolutionError("Task queue must contain items and history arrays")
    seen: set[str] = set()
    for item in queue["items"]:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("id"), str)
            or not item["id"].strip()
        ):
            raise EvolutionError("Every queued item needs a non-empty string id")
        if item["id"] in seen:
            raise EvolutionError(f"Duplicate queued task id: {item['id']}")
        seen.add(item["id"])
        if not isinstance(item.get("status"), str) or item.get("status") not in QUEUE_STATUSES:
            raise EvolutionError(f"Invalid status for queued task {item['id']}")
        attempts = item.get("attempts", 0)
        if type(attempts) is not int or attempts < 0:
            raise EvolutionError(f"Invalid attempts count for queued task {item['id']}")
    _validate_history(queue["history"])

    # The queue snapshot is the current state; its own audit trail must not
    # contradict that state. Histories may omit transitions for legacy items,
    # but when a transition exists, the final recorded destination must match
    # the persisted item status.
    latest_status: dict[str, str] = {}
    for event in queue["history"]:
        if event.get("event") != "STATUS_CHANGED":
            continue
        task_id = event["task_id"]
        previous_destination = latest_status.get(task_id)
        if previous_destination is not None and event["from"] != previous_destination:
            raise EvolutionError(
                f"Queue history transition chain mismatch for task {task_id!r}: "
                f"next transition starts at {event['from']!r}, "
                f"previous transition ended at {previous_destination!r}"
            )
        latest_status[task_id] = event["to"]
    for item in queue["items"]:
        task_id = item["id"]
        recorded_status = latest_status.get(task_id)
        if recorded_status is not None and recorded_status != item["status"]:
            raise EvolutionError(
                f"Queue status/history mismatch for task {task_id!r}: "
                f"item status is {item['status']!r}, latest history destination is {recorded_status!r}"
            )
    return queue


def merge_candidates(queue: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Add new candidates once; preserve existing statuses and append audit history."""
    # Validate and copy through canonical JSON so callers cannot mutate stored state.
    try:
        merged = json.loads(canonical_json(queue))
    except (TypeError, ValueError) as exc:
        raise EvolutionError(f"Invalid queue data: {exc}") from exc
    if not isinstance(merged, dict) or merged.get("version") != QUEUE_VERSION:
        raise EvolutionError("Unsupported task queue format")
    if not isinstance(merged.get("items"), list) or not isinstance(merged.get("history"), list):
        raise EvolutionError("Task queue must contain items and history arrays")

    known = {item.get("id"): item for item in merged["items"] if isinstance(item, dict)}
    added = 0
    timestamp = datetime.now(timezone.utc).isoformat()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise EvolutionError("Each candidate must be an object")
        candidate_id = candidate.get("id")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise EvolutionError("Each candidate needs a non-empty string id")
        if candidate_id in known:
            continue
        item = {
            **candidate,
            "status": "OPEN",
            "attempts": 0,
            "first_seen": timestamp,
        }
        merged["items"].append(item)
        known[candidate_id] = item
        merged["history"].append({
            "event": "CANDIDATE_ADDED",
            "task_id": candidate_id,
            "at": timestamp,
        })
        added += 1
    merged["items"].sort(key=lambda item: item["id"])
    merged["history"].sort(key=lambda item: (item.get("at", ""), item.get("task_id", ""), item.get("event", "")))
    return {"queue": merged, "added": added, "total": len(merged["items"])}


def _valid_git_sha(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(char in "0123456789abcdef" for char in value)
    )


def _matching_pass(
    history: list[dict[str, Any]],
    *,
    task_id: str,
    attempt: int,
    lease_id: str,
    commit_sha: str,
    tree_sha: str,
) -> bool:
    matching = [
        event for event in history
        if event.get("event") == "VERIFICATION_RECORDED"
        and event.get("task_id") == task_id
        and event.get("attempt") == attempt
        and event.get("lease_id") == lease_id
        and event.get("commit_sha") == commit_sha
        and event.get("tree_sha") == tree_sha
    ]
    return bool(matching) and matching[-1].get("verification_status") == "PASS"


def record_outcome(
    queue: dict[str, Any],
    task_id: str,
    status: str,
    note: str = "",
    *,
    lease_id: str | None = None,
    commit_sha: str | None = None,
    tree_sha: str | None = None,
) -> dict[str, Any]:
    """Record a lifecycle transition; DONE requires PASS bound to the active attempt."""
    if not isinstance(task_id, str) or not task_id.strip():
        raise EvolutionError("Task id must be a non-empty string")
    if not isinstance(status, str) or status not in QUEUE_STATUSES:
        raise EvolutionError(f"Unsupported queue status: {status!r}")
    if not isinstance(note, str):
        raise EvolutionError("Transition note must be a string")
    updated = json.loads(canonical_json(queue))
    matches = [item for item in updated.get("items", []) if item.get("id") == task_id]
    if len(matches) != 1:
        raise EvolutionError(f"Expected exactly one queued task with id {task_id!r}")
    item = matches[0]
    previous = item.get("status")
    if not isinstance(previous, str) or previous not in QUEUE_STATUSES:
        raise EvolutionError(f"Invalid status for queued task {task_id!r}")
    attempts = item.get("attempts", 0)
    if type(attempts) is not int or attempts < 0:
        raise EvolutionError(f"Invalid attempts count for queued task {task_id!r}")

    if status == "IN_PROGRESS":
        if not isinstance(lease_id, str) or not lease_id.strip():
            raise EvolutionError("IN_PROGRESS requires a non-empty lease_id")
        if not _valid_git_sha(commit_sha) or not _valid_git_sha(tree_sha):
            raise EvolutionError("IN_PROGRESS requires full lowercase commit_sha and tree_sha")
        item["attempts"] = attempts + 1
        item["lease_id"] = lease_id
        item["commit_sha"] = commit_sha
        item["tree_sha"] = tree_sha
        item["status"] = status
    elif status == "DONE":
        active_attempt = attempts
        active_lease = item.get("lease_id")
        active_commit = item.get("commit_sha")
        active_tree = item.get("tree_sha")
        if previous != "IN_PROGRESS":
            raise EvolutionError("DONE requires an active IN_PROGRESS attempt")
        if (
            not isinstance(active_lease, str) or not active_lease.strip()
            or not _valid_git_sha(active_commit)
            or not _valid_git_sha(active_tree)
            or not _matching_pass(
                updated.get("history", []),
                task_id=task_id,
                attempt=active_attempt,
                lease_id=active_lease,
                commit_sha=active_commit,
                tree_sha=active_tree,
            )
        ):
            raise EvolutionError("DONE requires matching PASS verification evidence for the active attempt")
        item["status"] = status
    else:
        item["status"] = status

    timestamp = datetime.now(timezone.utc).isoformat()
    event = {
        "event": "STATUS_CHANGED",
        "task_id": task_id,
        "from": previous,
        "to": status,
        "note": note,
        "at": timestamp,
    }
    if status in {"IN_PROGRESS", "DONE"}:
        event.update({
            "attempt": item.get("attempts", attempts),
            "lease_id": item.get("lease_id"),
            "commit_sha": item.get("commit_sha"),
            "tree_sha": item.get("tree_sha"),
        })
    updated.setdefault("history", []).append(event)
    return updated


def record_verification_file(
    path: Path,
    task_id: str,
    verification_status: str,
    verification_level: str,
    artifact_sha256: str | None = None,
    *,
    attempt: int | None = None,
    lease_id: str | None = None,
    commit_sha: str | None = None,
    tree_sha: str | None = None,
) -> dict[str, Any]:
    """Persist verification evidence, optionally bound to one exact task attempt."""
    if not isinstance(task_id, str) or not task_id.strip():
        raise EvolutionError("Verification task_id must be a non-empty string")
    if not isinstance(verification_status, str) or verification_status not in {"PASS", "FAIL"}:
        raise EvolutionError(f"Unsupported verification status: {verification_status!r}")
    if not isinstance(verification_level, str) or not verification_level.strip():
        raise EvolutionError("Verification level must be a non-empty string")
    if artifact_sha256 is not None and (
        not isinstance(artifact_sha256, str)
        or len(artifact_sha256) != 64
        or any(char not in "0123456789abcdef" for char in artifact_sha256)
    ):
        raise EvolutionError("artifact_sha256 must be a lowercase SHA-256 hex digest")
    bindings = (attempt, lease_id, commit_sha, tree_sha)
    if any(value is not None for value in bindings):
        if type(attempt) is not int or attempt < 1:
            raise EvolutionError("Bound verification requires a positive integer attempt")
        if not isinstance(lease_id, str) or not lease_id.strip():
            raise EvolutionError("Bound verification requires a non-empty lease_id")
        if not _valid_git_sha(commit_sha) or not _valid_git_sha(tree_sha):
            raise EvolutionError("Bound verification requires full lowercase commit_sha and tree_sha")

    with queue_write_lock(path):
        queue = load_queue(path)
        event = {
            "event": "VERIFICATION_RECORDED",
            "task_id": task_id,
            "verification_status": verification_status,
            "verification_level": verification_level,
            "artifact_sha256": artifact_sha256,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        if all(value is not None for value in bindings):
            event.update({
                "attempt": attempt,
                "lease_id": lease_id,
                "commit_sha": commit_sha,
                "tree_sha": tree_sha,
            })
        updated = json.loads(canonical_json(queue))
        updated["history"].append(event)
        _write_queue_atomically(path, updated)
    return {"task_id": task_id, "verification_status": verification_status, "path": path.as_posix()}


def update_queue_file(path: Path, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge discovered candidates into a local persistent JSON queue."""
    with queue_write_lock(path):
        current = load_queue(path)
        result = merge_candidates(current, candidates)
        _write_queue_atomically(path, result["queue"])
    return {"added": result["added"], "total": result["total"], "path": path.as_posix()}


def record_outcome_file(
    path: Path,
    task_id: str,
    status: str,
    note: str = "",
    *,
    lease_id: str | None = None,
    commit_sha: str | None = None,
    tree_sha: str | None = None,
) -> dict[str, Any]:
    """Persist a lifecycle transition and its audit event to the queue file."""
    with queue_write_lock(path):
        queue = load_queue(path)
        updated = record_outcome(
            queue, task_id, status, note,
            lease_id=lease_id, commit_sha=commit_sha, tree_sha=tree_sha,
        )
        _write_queue_atomically(path, updated)
    return {"task_id": task_id, "status": status, "path": path.as_posix()}
