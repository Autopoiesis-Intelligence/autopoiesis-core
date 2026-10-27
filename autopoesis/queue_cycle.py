"""One bounded, governed queue cycle for the supported sandbox verifier.

This coordinator intentionally handles one task type and at most one task per call.
It does not run a daemon, invoke arbitrary commands, or claim work it cannot verify.
"""
from __future__ import annotations

import argparse
import json

from autopoesis.executor import source_tree_digest as executor_source_tree_digest
from pathlib import Path
from typing import Any

from autopoesis.task_queue import (
    advance_task_file,
    current_attempt,
    load_queue,
    MAX_ATTEMPTS,
    record_verification_file,
    recover_expired_leases_file,
    select_next_task_file,
)
from run_tasks import ROOT, execute_task

SUPPORTED_CYCLE_TYPES = frozenset({"verify_test_patch_sandbox"})
OWNER = "bounded-queue-cycle-v1"


def source_tree_digest(root: Path) -> str:
    """Use the executor's digest format so tested and observed revisions are comparable."""
    return executor_source_tree_digest(root)


def run_one_queue_cycle(queue_path: Path) -> dict[str, Any]:
    """Select, execute, verify and finalize at most one supported queue task.

    Outcomes are COMPLETED, NO_WORK, RETRYABLE_FAILURE, REJECTED, or
    RECOVERY_REQUIRED. The latter means the coordinator cannot confirm a safe
    persisted state and requires inspection; it is not a terminal task status.
    A failed attempt returns work to OPEN until MAX_ATTEMPTS, then REJECTED.
    DONE is bound to the digest of the exact source snapshot reported by the
    executor. Live-tree comparisons remain fail-closed checks during the cycle,
    but they cannot prove the live tree stayed unchanged after the last check.
    """
    # Recovery runs before selection, so its rejections belong in every outcome,
    # not only NO_WORK; the list fills in place and survives a later failure.
    rejected_after_recovery: list[str] = []
    result = _run_cycle(queue_path, rejected_after_recovery)
    result["rejected_after_recovery"] = rejected_after_recovery
    return result


def _run_cycle(queue_path: Path, rejected_after_recovery: list[str]) -> dict[str, Any]:
    try:
        # A cycle that died mid-task (runner timeout, OOM) leaves its lease behind;
        # without this, every later cycle would report "work already active" forever.
        recovered = recover_expired_leases_file(queue_path)["recovered"]
        # Recovery returns work to OPEN; a task that already used every attempt would then
        # only be deferred forever, so it ends REJECTED here instead.
        if recovered:
            items = {entry.get("id"): entry for entry in load_queue(queue_path)["items"]}
            for recovered_id in recovered:
                entry = items.get(recovered_id, {})
                if entry.get("status") == "OPEN" and entry.get("attempts", 0) >= MAX_ATTEMPTS:
                    advance_task_file(
                        queue_path, recovered_id, "REJECTED",
                        "lease expired on the last attempt; attempt limit reached; task rejected",
                    )
                    rejected_after_recovery.append(recovered_id)
        selection = select_next_task_file(
            queue_path,
            OWNER,
            types=SUPPORTED_CYCLE_TYPES,
        )
    except Exception as exc:
        # Selection may fail before a task ID or lease can be trusted.
        # Surface the failed cycle as recoverable instead of leaking an
        # unstructured exception or implying that no work exists.
        return {
            "status": "RECOVERY_REQUIRED",
            "task_id": None,
            "reason": f"queue selection failed: {type(exc).__name__}: {exc}",
            "reopened": False,
        }

    task_id = selection.get("selected")
    if task_id is None:
        return {
            "status": "NO_WORK",
            "reason": selection.get("reason", "no eligible task"),
            "deferred": selection.get("deferred", []),
        }

    try:
        queue = load_queue(queue_path)
    except Exception as exc:
        return {
            "status": "RECOVERY_REQUIRED",
            "task_id": task_id,
            "reason": f"selected task state could not be reloaded: {type(exc).__name__}: {exc}",
            "reopened": False,
        }
    item = next((entry for entry in queue["items"] if entry.get("id") == task_id), None)
    lease = selection.get("lease")
    token = lease.get("token") if isinstance(lease, dict) else None
    if item is None or not isinstance(token, str) or not token:
        # Selection metadata is not proof that a valid persisted lease exists.
        # Do not report a terminal task rejection when lifecycle state was not
        # transitioned; leave the queue untouched and require recovery review.
        return {
            "status": "RECOVERY_REQUIRED",
            "task_id": task_id,
            "reason": "selected queue item or valid lease token could not be reloaded",
            "reopened": False,
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
            terminal = attempt is not None and attempt >= MAX_ATTEMPTS
            failure_status = "REJECTED" if terminal else "OPEN"
            advance_task_file(
                queue_path,
                task_id,
                failure_status,
                (
                    f"bounded verifier did not PASS (result={verification!r}); "
                    + ("attempt limit reached; task rejected" if terminal else "retry required")
                ),
                owner=OWNER,
                token=token,
            )
            return {
                "status": "REJECTED" if terminal else "RETRYABLE_FAILURE",
                "task_id": task_id,
                "verification_status": verification,
                "attempt": attempt,
                "execution": execution,
            }

        current_revision = source_tree_digest(ROOT / "autopoesis")
        reported_revision = execution.get("result", {}).get("source_tree_sha256")
        if revision_before != current_revision or reported_revision != revision_before:
            terminal = attempt is not None and attempt >= MAX_ATTEMPTS
            failure_status = "REJECTED" if terminal else "OPEN"
            advance_task_file(
                queue_path,
                task_id,
                failure_status,
                (
                    "tested source digest is missing or does not match the stable repository digest; "
                    + ("attempt limit reached; task rejected" if terminal else "retry required")
                ),
                owner=OWNER,
                token=token,
            )
            return {
                "status": "REJECTED" if terminal else "RETRYABLE_FAILURE",
                "task_id": task_id,
                "reason": "executor-reported source digest is missing or mismatched, or source tree changed",
                "attempt": attempt,
                "tested_revision": reported_revision,
                "revision_before": revision_before,
                "current_revision": current_revision,
            }

        # The executor already records its own lease-bound verification.
        # This additional PASS binds the coordinator's finalization to the same
        # tested revision and attempt; it is written only after exact digest equality.
        record_verification_file(
            queue_path,
            task_id,
            "PASS",
            "BOUNDED_SANDBOX_TEST_WITH_SOURCE_DIGEST",
            source=item["source"],
            attempt=attempt,
            revision=reported_revision,
            token=token,
        )
        # Recompute after persisting coordinator PASS. A change observed here is
        # still rejected, but a writer can race after this check. DONE therefore
        # records the tested snapshot digest, not a claim that the live tree is
        # immutable or still identical at the instant the status is persisted.
        final_revision = source_tree_digest(ROOT / "autopoesis")
        if final_revision != current_revision:
            terminal = attempt is not None and attempt >= MAX_ATTEMPTS
            failure_status = "REJECTED" if terminal else "OPEN"
            advance_task_file(
                queue_path,
                task_id,
                failure_status,
                (
                    "source tree changed after coordinator PASS evidence was recorded; "
                    + ("attempt limit reached; task rejected" if terminal else "retry required")
                ),
                owner=OWNER,
                token=token,
            )
            return {
                "status": "REJECTED" if terminal else "RETRYABLE_FAILURE",
                "task_id": task_id,
                "reason": "source tree changed after PASS evidence and before DONE finalization",
                "attempt": attempt,
                "verified_revision": current_revision,
                "final_revision": final_revision,
            }

        advance_task_file(
            queue_path,
            task_id,
            "DONE",
            "bounded verifier PASS bound to tested source snapshot, attempt and lease",
            owner=OWNER,
            token=token,
            revision=reported_revision,
        )
        return {
            "status": "COMPLETED",
            "task_id": task_id,
            "verification_status": "PASS",
            "revision": reported_revision,
            "revision_semantics": "SHA-256 of the exact copied source snapshot tested by the executor",
            "live_tree_immutability_proven": False,
            "execution": execution,
        }
    except Exception as exc:
        # Never manufacture DONE or REJECTED from an attempted transition.
        # If the lease prevents recovery, report that the persisted state needs
        # inspection instead of claiming a transition that may not have occurred.
        outcome = "RECOVERY_REQUIRED"
        reopened = False
        try:
            latest = load_queue(queue_path)
            current = next((entry for entry in latest["items"] if entry.get("id") == task_id), None)
            if current is not None:
                current_status = current.get("status")
                if current_status == "OPEN":
                    outcome = "RETRYABLE_FAILURE"
                    reopened = True
                elif current_status == "REJECTED":
                    outcome = "REJECTED"
                elif current_status in {"SELECTED", "IN_PROGRESS"}:
                    terminal = (
                        current_status == "IN_PROGRESS"
                        and current.get("attempts", 0) >= MAX_ATTEMPTS
                    )
                    failure_status = "REJECTED" if terminal else "OPEN"
                    advance_task_file(
                        queue_path,
                        task_id,
                        failure_status,
                        (
                            f"bounded cycle interrupted: {type(exc).__name__}; "
                            + ("attempt limit reached; task rejected" if terminal else "retry required")
                        ),
                        owner=OWNER,
                        token=token,
                    )
                    verified = load_queue(queue_path)
                    persisted = next(
                        (entry for entry in verified["items"] if entry.get("id") == task_id),
                        None,
                    )
                    if persisted is not None and persisted.get("status") == failure_status:
                        outcome = "REJECTED" if terminal else "RETRYABLE_FAILURE"
                        reopened = not terminal
        except Exception:
            # The queue/lease prevented a verified recovery transition.
            outcome = "RECOVERY_REQUIRED"
        return {
            "status": outcome,
            "task_id": task_id,
            "reason": f"{type(exc).__name__}: {exc}",
            "reopened": reopened,
        }


# A completed task or an empty queue is a normal cycle; anything else needs attention.
EXIT_CODES = {"COMPLETED": 0, "NO_WORK": 0, "RETRYABLE_FAILURE": 2, "REJECTED": 2, "RECOVERY_REQUIRED": 3}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one bounded queue cycle and print its outcome as JSON.")
    parser.add_argument("--queue", type=Path, default=Path("TASK_QUEUE.json"))
    args = parser.parse_args(argv)
    # The library reads a missing queue as an empty first-run queue; from the command line
    # a missing file is far more likely a wrong path, so it must not pass as NO_WORK.
    if not args.queue.is_file():
        result = {"status": "RECOVERY_REQUIRED", "task_id": None, "reopened": False,
                  "reason": f"queue file not found: {args.queue}"}
    else:
        result = run_one_queue_cycle(args.queue)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return EXIT_CODES.get(result.get("status"), 3)


if __name__ == "__main__":
    raise SystemExit(main())
