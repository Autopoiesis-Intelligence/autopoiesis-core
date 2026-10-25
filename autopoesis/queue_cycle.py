"""One bounded, governed queue cycle for the supported sandbox verifier.

This coordinator intentionally handles one task type and at most one task per call.
It does not run a daemon, invoke arbitrary commands, or claim work it cannot verify.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from autopoesis.task_queue import (
    advance_task_file,
    current_attempt,
    load_queue,
    record_verification_file,
    select_next_task_file,
)
from run_tasks import ROOT, execute_task

SUPPORTED_CYCLE_TYPES = frozenset({"verify_test_patch_sandbox"})
OWNER = "bounded-queue-cycle-v1"
IGNORED_PARTS = {"__pycache__"}


def source_tree_digest(root: Path) -> str:
    """Hash a source tree deterministically without depending on file timestamps."""
    digest = hashlib.sha256()
    resolved_root = root.resolve()
    for path in sorted(resolved_root.rglob("*")):
        if not path.is_file() or any(part in IGNORED_PARTS for part in path.parts):
            continue
        relative = path.relative_to(resolved_root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def run_one_queue_cycle(queue_path: Path) -> dict[str, Any]:
    """Select, execute, verify and finalize at most one supported queue task.

    Outcomes are COMPLETED, NO_WORK, RETRYABLE_FAILURE, or REJECTED.
    A handler exception or FAIL verification returns IN_PROGRESS work to OPEN
    when its lease remains valid. DONE is written only after the verifier's
    PASS evidence is recorded and the tested source digest still matches.
    """
    selection = select_next_task_file(
        queue_path,
        OWNER,
        types=SUPPORTED_CYCLE_TYPES,
    )
    task_id = selection.get("selected")
    if task_id is None:
        return {
            "status": "NO_WORK",
            "reason": selection.get("reason", "no eligible task"),
            "deferred": selection.get("deferred", []),
        }

    queue = load_queue(queue_path)
    item = next((entry for entry in queue["items"] if entry.get("id") == task_id), None)
    lease = selection.get("lease")
    token = lease.get("token") if isinstance(lease, dict) else None
    if item is None or not isinstance(token, str):
        return {
            "status": "REJECTED",
            "task_id": task_id,
            "reason": "selected queue item or lease token could not be reloaded",
        }

    try:
        advance_task_file(
            queue_path,
            task_id,
            "IN_PROGRESS",
            "bounded queue cycle started execution",
            owner=OWNER,
            token=token,
        )
        attempt = current_attempt(queue_path, task_id)
        revision_before = source_tree_digest(ROOT / "autopoesis")
        task = dict(item)
        task["queue_task_id"] = task_id
        task["lease_token"] = token
        execution = execute_task(task, queue_path)
        verification = execution.get("result", {}).get("verification_status")

        if verification != "PASS":
            advance_task_file(
                queue_path,
                task_id,
                "OPEN",
                f"bounded verifier did not PASS (result={verification!r}); retry required",
                owner=OWNER,
                token=token,
            )
            return {
                "status": "RETRYABLE_FAILURE",
                "task_id": task_id,
                "verification_status": verification,
                "execution": execution,
            }

        current_revision = source_tree_digest(ROOT / "autopoesis")
        if revision_before != current_revision:
            advance_task_file(
                queue_path,
                task_id,
                "OPEN",
                "source tree changed after verification; result cannot complete task",
                owner=OWNER,
                token=token,
            )
            return {
                "status": "RETRYABLE_FAILURE",
                "task_id": task_id,
                "reason": "verified source digest differs from current source tree",
                "tested_revision": revision_before,
                "current_revision": current_revision,
            }

        # The base-branch verifier does not emit a source-tree digest. Bind a
        # coordinator-level PASS to the before/after digest and exact attempt.
        record_verification_file(
            queue_path,
            task_id,
            "PASS",
            "BOUNDED_SANDBOX_TEST_WITH_SOURCE_DIGEST",
            source=item["source"],
            attempt=attempt,
            revision=current_revision,
            token=token,
        )
        advance_task_file(
            queue_path,
            task_id,
            "DONE",
            "bounded verifier PASS bound to current source, attempt and lease",
            owner=OWNER,
            token=token,
            revision=current_revision,
        )
        return {
            "status": "COMPLETED",
            "task_id": task_id,
            "verification_status": "PASS",
            "revision": current_revision,
            "execution": execution,
        }
    except Exception as exc:
        # Never manufacture DONE on an exception. Reopen only if the current
        # lease still authorizes the transition; otherwise leave recovery to
        # the governed expired-lease path.
        reopened = False
        try:
            latest = load_queue(queue_path)
            current = next((entry for entry in latest["items"] if entry.get("id") == task_id), None)
            if current is not None and current.get("status") in {"SELECTED", "IN_PROGRESS"}:
                advance_task_file(
                    queue_path,
                    task_id,
                    "OPEN",
                    f"bounded cycle interrupted: {type(exc).__name__}",
                    owner=OWNER,
                    token=token,
                )
                reopened = True
        except Exception:
            pass
        return {
            "status": "RETRYABLE_FAILURE" if reopened else "REJECTED",
            "task_id": task_id,
            "reason": f"{type(exc).__name__}: {exc}",
            "reopened": reopened,
        }
