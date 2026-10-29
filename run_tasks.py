"""Run bounded tasks and inspect the repository for development opportunities."""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autopoesis.core import EvolutionError, digest_state, evolve
from autopoesis.task_queue import record_outcome_file, record_verification_file, update_queue_file
from autopoesis.executor import apply_patch_to_sandbox, prepare_patch_artifact, verify_test_patch_in_sandbox


ROOT = Path(__file__).resolve().parent
IGNORED_PARTS = {".git", "__pycache__", ".venv", "venv"}


def verify_evolution_cycle() -> dict[str, Any]:
    current = {"counter": 1, "label": "start"}
    candidate = {"counter": 2, "label": "next"}
    transition = evolve(current, candidate)

    if transition["state_digest"] != digest_state(candidate):
        raise AssertionError("Candidate digest mismatch")

    try:
        evolve(candidate, candidate)
    except EvolutionError:
        noop_rejected = True
    else:
        noop_rejected = False

    if not noop_rejected:
        raise AssertionError("No-op transition was not rejected")

    return {
        "deterministic_digest": digest_state(candidate) == digest_state({"label": "next", "counter": 2}),
        "meaningful_transition_accepted": transition["accepted"],
        "noop_rejected": noop_rejected,
        "state_digest": transition["state_digest"],
    }


def create_agent_proposal(description: str) -> dict[str, Any]:
    return {
        "status": "PROPOSAL_ONLY",
        "description": description,
        "proposed_interface": {
            "input": "task object and current repository snapshot",
            "output": "patch files plus a machine-readable test report",
            "boundary": "no arbitrary task-provided shell execution",
        },
        "note": (
            "This runner does not generate code. A separate code-writing agent "
            "must be connected to implement this proposal."
        ),
    }


def discover_tasks(repository_root: Path) -> dict[str, Any]:
    """Find evidence-backed, low-risk follow-up tasks without modifying files."""
    candidates: list[dict[str, str]] = []
    python_files = sorted(
        path for path in repository_root.rglob("*.py")
        if not any(part in IGNORED_PARTS for part in path.parts)
    )

    for path in python_files:
        relative = path.relative_to(repository_root).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue

        if relative.startswith(("autopoesis/", "run_tasks.py")):
            for line_number, line in enumerate(source.splitlines(), start=1):
                marker = next((item for item in ("TODO", "FIXME", "HACK") if item in line), None)
                if marker:
                    candidate = {
                        "type": "proposal",
                        "source": relative,
                        "evidence": f"{marker} marker on line {line_number}",
                        "description": f"Review and resolve the {marker} marker in {relative}:{line_number}.",
                    }
                    candidate["id"] = "DISC-" + digest_state(candidate)[:12]
                    candidates.append(candidate)

        if relative.startswith("autopoesis/") and path.name != "__init__.py":
            expected_test = repository_root / "tests" / f"test_{path.stem}.py"
            if not expected_test.exists():
                candidate = {
                    "type": "proposal",
                    "source": relative,
                    "evidence": f"no conventional test file found at tests/test_{path.stem}.py",
                    "description": f"Add focused tests for {relative}.",
                }
                candidate["id"] = "DISC-" + digest_state(candidate)[:12]
                candidates.append(candidate)

    unique = {item["id"]: item for item in candidates}
    ordered = [unique[key] for key in sorted(unique)]
    return {
        "status": "CANDIDATES_FOUND" if ordered else "NO_CANDIDATES",
        "candidate_count": len(ordered),
        "candidates": ordered,
        "scope": "static Python source inspection only; no code execution or modification",
    }


def execute_task(task: dict[str, Any], queue_path: Path) -> dict[str, Any]:
    task_id = task.get("id")
    task_type = task.get("type")

    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("Each task needs a non-empty string id")

    if task_type == "verify_evolution_cycle":
        result = verify_evolution_cycle()
    elif task_type == "proposal":
        description = task.get("description", "")
        if not isinstance(description, str):
            raise ValueError("Task description must be a string")
        result = create_agent_proposal(description)
    elif task_type == "discover_tasks":
        result = discover_tasks(ROOT)
    elif task_type == "queue_discovered_tasks":
        discovery = discover_tasks(ROOT)
        result = update_queue_file(queue_path, discovery["candidates"])
        result["discovery_status"] = discovery["status"]
        result["discovered"] = discovery["candidate_count"]
    elif task_type == "update_task_status":
        target_id = task.get("task_id")
        status = task.get("status")
        note = task.get("note", "")
        if not isinstance(target_id, str) or not isinstance(status, str) or not isinstance(note, str):
            raise ValueError("update_task_status requires string task_id, status, and optional note")
        result = record_outcome_file(
            queue_path,
            target_id,
            status,
            note,
            lease_id=task.get("lease_id"),
            commit_sha=task.get("commit_sha"),
            tree_sha=task.get("tree_sha"),
        )
    elif task_type == "prepare_test_patch":
        result = prepare_patch_artifact(task, ROOT)
    elif task_type == "verify_test_patch_sandbox":
        result = verify_test_patch_in_sandbox(task, ROOT)
    elif task_type == "apply_test_patch_sandbox":
        artifact = prepare_patch_artifact(task, ROOT)
        with tempfile.TemporaryDirectory(prefix="autopoesis-patch-sandbox-") as directory:
            application = apply_patch_to_sandbox(artifact, Path(directory))
        result = {
            "artifact": artifact,
            "sandbox_application": application,
            "sandbox_lifetime": "temporary; removed after the task",
        }
    else:
        raise ValueError(f"Unsupported task type: {task_type!r}")

    if task_type == "verify_test_patch_sandbox" and result.get("verification_status") in {"PASS", "FAIL"}:
        record_verification_file(
            queue_path,
            task_id,
            result["verification_status"],
            "GENERATED_TEST_EXECUTION",
            result.get("artifact_sha256"),
        )

    task_status = "FAIL" if result.get("verification_status") == "FAIL" else "PASS"
    record: dict[str, Any] = {
        "id": task_id,
        "type": task_type,
        "status": task_status,
        "result": result,
    }
    if task_type == "prepare_test_patch":
        record["verification"] = {
            "level": "PATCH_ARTIFACT_PREPARED_AND_VALIDATED",
            "generated_code_executed": False,
            "tests_executed": False,
            "meaning": "PASS confirms artifact preparation and static validation only.",
        }
    elif task_type == "apply_test_patch_sandbox":
        record["verification"] = {
            "level": "PATCH_APPLIED_TO_DISPOSABLE_SANDBOX",
            "generated_code_executed": False,
            "tests_executed": False,
            "repository_modified": False,
            "meaning": "PASS confirms sandbox application only; generated tests were not run.",
        }
    else:
        record["verification"] = {
            "level": "TASK_HANDLER_COMPLETED",
            "meaning": "PASS confirms the task handler returned without an exception; interpret result details for the actual checks performed.",
        }
    return record


def run(tasks_path: Path, results_path: Path, queue_path: Path = Path("TASK_QUEUE.json")) -> int:
    timestamp = datetime.now(timezone.utc).isoformat()
    output: dict[str, Any] = {
        "version": 1,
        "run_at": timestamp,
        "tasks": [],
    }

    try:
        document = json.loads(tasks_path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or not isinstance(document.get("tasks"), list):
            raise ValueError("Task file must contain a 'tasks' array")
        seen_ids: set[str] = set()
        for task in document["tasks"]:
            if not isinstance(task, dict):
                raise ValueError("Each task must be a JSON object")
            task_id = task.get("id")
            if isinstance(task_id, str) and task_id in seen_ids:
                raise ValueError(f"Duplicate task id: {task_id}")
            if isinstance(task_id, str):
                seen_ids.add(task_id)
            try:
                output["tasks"].append(execute_task(task, queue_path))
            except Exception as exc:
                output["tasks"].append({
                    "id": task_id,
                    "type": task.get("type"),
                    "status": "FAIL",
                    "error": f"{type(exc).__name__}: {exc}",
                })
    except Exception as exc:
        output["error"] = f"{type(exc).__name__}: {exc}"
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(
            json.dumps(output, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return 1

    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 1 if any(item["status"] == "FAIL" for item in output["tasks"]) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, default=Path("TASKS.json"))
    parser.add_argument("--results", type=Path, default=Path("RESULTS.json"))
    parser.add_argument("--queue", type=Path, default=Path("TASK_QUEUE.json"))
    args = parser.parse_args()
    return run(args.tasks, args.results, args.queue)


if __name__ == "__main__":
    raise SystemExit(main())
