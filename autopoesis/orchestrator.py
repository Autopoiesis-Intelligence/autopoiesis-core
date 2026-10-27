"""A10: one unattended cycle over the task queue, with a bounded handler.

snapshot the checkout's HEAD commit -> recover expired leases -> select one task
the runner can execute -> IN_PROGRESS -> run its allowlisted handler on the
snapshot -> record verification with the commit and tree -> DONE, OPEN or REJECTED.

Outcomes and exit codes: COMPLETED (DONE), NO_WORK and DISABLED exit 0;
RETRYABLE_FAILURE (back to OPEN) and REJECTED exit 2; RECOVERY_REQUIRED exits 3
and means the queue refused a step, so the persisted state needs inspection.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import subprocess
import tarfile
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .core import EvolutionError
from .executor import verify_test_patch_in_sandbox
from .task_queue import (
    LEASE_TTL,
    MAX_ATTEMPTS,
    advance_task_file,
    current_attempt,
    load_queue,
    record_verification_file,
    recover_expired_leases_file,
    select_next_task_file,
)

Handler = Callable[[dict[str, Any], Path], dict[str, Any]]


def verify_test_scaffold(item: dict[str, Any], repository_root: Path) -> dict[str, Any]:
    """Run the bounded generated import test for the item's source in a disposable sandbox."""
    result = verify_test_patch_in_sandbox({"id": item["id"], "source": item["source"]}, repository_root)
    return {
        "verification_status": result["verification_status"],
        "verification_level": "GENERATED_TEST_EXECUTION",
        "artifact_sha256": result.get("artifact_sha256"),
        "revision": result.get("source_tree_sha256"),
        "detail": result.get("failure_reason"),
    }


# The allowlist: an item runs only if its type is a key here. Task data never names code to run.
HANDLERS: dict[str, Handler] = {"verify_test_scaffold": verify_test_scaffold}
DEFAULT_BUDGET_SECONDS = 600
LOCK_RETRIES = 50
LOCK_RETRY_SECONDS = 0.1
EXIT_CODES = {"COMPLETED": 0, "NO_WORK": 0, "DISABLED": 0, "RETRYABLE_FAILURE": 2, "REJECTED": 2,
              "RECOVERY_REQUIRED": 3}


def _when_unlocked(call: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Queue writers fail fast on a held lock; a runner waits briefly instead of dropping its own step."""
    for remaining in range(LOCK_RETRIES, 0, -1):
        try:
            return call(*args, **kwargs)
        except EvolutionError as exc:
            if "locked by another writer" not in str(exc) or remaining == 1:
                raise
            time.sleep(LOCK_RETRY_SECONDS)
    raise AssertionError("unreachable")


MAX_RESULT_BYTES = 4 * 1024 * 1024
GIT_TIMEOUT_SECONDS = 60


def _git(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, timeout=GIT_TIMEOUT_SECONDS
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EvolutionError(f"git {args[0]} failed: {exc}") from exc
    if completed.returncode != 0:
        raise EvolutionError(f"git {args[0]} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def _tree_of(root: Path, commit_sha: str) -> str:
    return _git(root, "rev-parse", "--verify", f"{commit_sha}^{{tree}}")


def _snapshot(root: Path, destination: Path) -> tuple[str, str, Path]:
    """Extract the HEAD commit of the repository at `root` into `destination`.

    Returns (commit_sha, tree_sha, path). The handler runs on this extraction,
    so uncommitted or untracked files in the checkout never reach it.
    """
    if Path(_git(root, "rev-parse", "--show-toplevel")).resolve() != root.resolve():
        raise EvolutionError(f"{root.as_posix()} is not the top level of a git repository")
    commit_sha = _git(root, "rev-parse", "--verify", "HEAD^{commit}")
    tree_sha = _tree_of(root, commit_sha)
    archive = destination.with_suffix(".tar")
    try:
        with archive.open("wb") as handle:
            completed = subprocess.run(
                ["git", "-C", str(root), "archive", "--format=tar", commit_sha],
                stdout=handle, stderr=subprocess.PIPE, timeout=GIT_TIMEOUT_SECONDS,
            )
        if completed.returncode != 0:
            raise EvolutionError(f"git archive failed: {completed.stderr.decode(errors='replace').strip()}")
        destination.mkdir()
        with tarfile.open(archive) as bundle:
            bundle.extractall(destination, filter="data")
    except (OSError, subprocess.TimeoutExpired, tarfile.TarError) as exc:
        raise EvolutionError(f"Cannot snapshot commit {commit_sha}: {exc}") from exc
    finally:
        archive.unlink(missing_ok=True)
    return commit_sha, tree_sha, destination


def _run_handler(handler: Handler, item: dict[str, Any], root: Path, result_path: Path) -> None:
    try:
        result = handler(item, root)
    except Exception as exc:  # A handler failure is the task's outcome, not the runner's crash.
        result = {"verification_status": "FAIL", "verification_level": "HANDLER_ERROR",
                  "detail": f"{type(exc).__name__}: {exc}"}
    # Serialize inside the child, so slow or huge results are still under the parent's deadline.
    partial = result_path.with_suffix(".partial")
    partial.write_text(json.dumps(result, default=str), encoding="utf-8")
    partial.replace(result_path)


def _bounded(handler: Handler, item: dict[str, Any], root: Path, seconds: float) -> dict[str, Any] | None:
    """Run the handler in a child process and kill it at the deadline; None means it ran out of time.

    The child writes its result to a file and exits; the parent only waits on the child, so nothing
    the handler returns can keep the parent past the deadline.
    """
    context = multiprocessing.get_context("fork")
    with tempfile.TemporaryDirectory(prefix="autopoesis-cycle-") as directory:
        result_path = Path(directory) / "result.json"
        child = context.Process(target=_run_handler, args=(handler, item, root, result_path), daemon=True)
        child.start()
        child.join(max(seconds, 0))
        if child.is_alive():
            child.kill()
            child.join()
            return None
        if not result_path.is_file():
            return {"verification_status": "FAIL", "verification_level": "HANDLER_ERROR",
                    "detail": f"handler exited with code {child.exitcode} and no result"}
        if result_path.stat().st_size > MAX_RESULT_BYTES:
            return {"verification_status": "FAIL", "verification_level": "HANDLER_ERROR",
                    "detail": f"handler result exceeds {MAX_RESULT_BYTES} bytes"}
        return json.loads(result_path.read_text(encoding="utf-8"))


def run_cycle(
    queue_path: Path,
    owner: str,
    repository_root: Path,
    *,
    handlers: dict[str, Handler] | None = None,
    disable_path: Path | None = None,
    budget_seconds: float = DEFAULT_BUDGET_SECONDS,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Run at most one task to an outcome; never raises for a task's own failure.

    Time bounds: `budget_seconds` bounds the handler, including building and handing over its
    result, because that all happens in a child process killed at the deadline. Each queue step
    waits at most LOCK_RETRIES * LOCK_RETRY_SECONDS for the lock and then refuses. Not covered
    by either bound: queue reads and writes in this process once a lock is held, and the
    git calls (each capped at GIT_TIMEOUT_SECONDS). The whole cycle has no single wall-time limit.
    The budget plus five lock waits must stay under LEASE_TTL, since the runner never renews
    its lease; a larger budget is refused before any write.
    A handler that does not finish within the budget gets no verification and no DONE. The
    result size cap limits what is accepted, not the child's memory use while it builds the result.

    `repository_root` must be the top level of a git repository. Before any queue write the
    cycle extracts its HEAD commit with `git archive`; the handler runs on that extraction,
    and the verification and DONE name that commit and its tree. The snapshot is the code the
    handler sees, not a limit on what the handler process may do. A root that is not a git
    repository, or a tree that is not the commit's tree, is RECOVERY_REQUIRED.
    """
    # The runner does not renew its lease, so the whole locked part of the cycle must fit inside it.
    if not (0 < budget_seconds and budget_seconds + 5 * LOCK_RETRIES * LOCK_RETRY_SECONDS < LEASE_TTL.total_seconds()):
        raise ValueError(
            f"budget_seconds must leave the cycle inside the {LEASE_TTL.total_seconds():.0f}s lease TTL"
        )
    handlers = HANDLERS if handlers is None else handlers
    if disable_path is not None and disable_path.exists():
        return {"status": "DISABLED", "reason": f"disable switch present at {disable_path.as_posix()}"}
    report: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="autopoesis-snapshot-") as directory:
        try:
            commit_sha, tree_sha, snapshot = _snapshot(repository_root, Path(directory) / "tree")
        except EvolutionError as exc:
            return {"status": "RECOVERY_REQUIRED", "reason": str(exc)}
        report["commit_sha"], report["tree_sha"] = commit_sha, tree_sha
        return _cycle(queue_path, owner, repository_root, snapshot, commit_sha, tree_sha, handlers,
                      budget_seconds, clock, clock(), report)


def _cycle(
    queue_path: Path,
    owner: str,
    repository_root: Path,
    snapshot: Path,
    commit_sha: str,
    tree_sha: str,
    handlers: dict[str, Handler],
    budget_seconds: float,
    clock: Callable[[], float],
    started: float,
    report: dict[str, Any],
) -> dict[str, Any]:
    try:
        report["recovered"] = _when_unlocked(recover_expired_leases_file, queue_path)["recovered"]
        # Recovery returns a task to OPEN, but one that used its last attempt would only be
        # deferred forever by selection; it ends REJECTED with the reason in its history.
        report["rejected_after_recovery"] = []
        if report["recovered"]:
            items = {entry["id"]: entry for entry in load_queue(queue_path)["items"]}
            for recovered_id in report["recovered"]:
                if items[recovered_id]["status"] == "OPEN" and items[recovered_id].get("attempts", 0) >= MAX_ATTEMPTS:
                    _when_unlocked(advance_task_file, queue_path, recovered_id, "REJECTED",
                                   "lease expired on the last attempt; attempt limit reached")
                    report["rejected_after_recovery"].append(recovered_id)
        selection = _when_unlocked(select_next_task_file, queue_path, owner, types=frozenset(handlers))
        if selection["selected"] is None:
            return {**report, "status": "NO_WORK", "reason": selection["reason"]}

        task_id = selection["selected"]
        token = selection["lease"]["token"]
        report["task_id"] = task_id
        _when_unlocked(advance_task_file, queue_path, task_id, "IN_PROGRESS", f"started by {owner}", token=token)
        attempt = current_attempt(queue_path, task_id)
        item = next(entry for entry in load_queue(queue_path)["items"] if entry["id"] == task_id)
        report["attempt"] = attempt
        outcome = _bounded(handlers[item["type"]], item, snapshot, budget_seconds - (clock() - started))
        if outcome is not None and outcome.get("verification_status") not in {"PASS", "FAIL"}:
            outcome = {"verification_status": "FAIL", "verification_level": "HANDLER_ERROR",
                       "detail": f"handler returned verification_status {outcome.get('verification_status')!r}"}

        if outcome is None or clock() - started > budget_seconds:
            # Evidence that arrives after the budget is not trusted; release the task untouched by it.
            _when_unlocked(advance_task_file, queue_path, task_id, "OPEN",
                           f"time budget of {budget_seconds}s exceeded", token=token)
            return {**report, "status": "RETRYABLE_FAILURE", "final": "OPEN",
                    "reason": f"time budget of {budget_seconds}s exceeded"}
        report["verification"] = outcome["verification_status"]
        report["detail"] = outcome.get("detail")

        _when_unlocked(
            record_verification_file, queue_path, task_id, outcome["verification_status"],
            outcome.get("verification_level", "UNSPECIFIED"), outcome.get("artifact_sha256"), item["source"],
            attempt, outcome.get("revision"), token, commit_sha=commit_sha, tree_sha=tree_sha,
        )
        failure = None
        if outcome["verification_status"] != "PASS":
            failure = f"verification failed: {outcome.get('detail')}"
        if failure is None:
            # The commit and tree come from the coordinator's own snapshot, never from the handler.
            if _tree_of(repository_root, commit_sha) != tree_sha:
                raise EvolutionError(f"Recorded tree {tree_sha} is not the tree of commit {commit_sha}")
            _when_unlocked(advance_task_file, queue_path, task_id, "DONE", f"verified by {owner}",
                           token=token, commit_sha=commit_sha, tree_sha=tree_sha)
            return {**report, "status": "COMPLETED", "final": "DONE"}
        final = "REJECTED" if attempt >= MAX_ATTEMPTS else "OPEN"
        _when_unlocked(advance_task_file, queue_path, task_id, final, failure, token=token)
        report["reason"] = failure
    except EvolutionError as exc:
        # The queue refused a step (for example a stale lease after recovery); nothing more is written.
        return {**report, "status": "RECOVERY_REQUIRED", "reason": str(exc)}
    return {**report, "status": "REJECTED" if final == "REJECTED" else "RETRYABLE_FAILURE", "final": final}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=Path("TASK_QUEUE.json"))
    parser.add_argument("--owner", required=True)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--disable-file", type=Path)
    parser.add_argument("--budget-seconds", type=float, default=DEFAULT_BUDGET_SECONDS)
    args = parser.parse_args()
    result = run_cycle(args.queue, args.owner, args.root.resolve(), disable_path=args.disable_file,
                       budget_seconds=args.budget_seconds)
    print(json.dumps(result, indent=2, sort_keys=True))
    return EXIT_CODES[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
