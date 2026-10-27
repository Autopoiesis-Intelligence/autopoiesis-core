"""Bind each injected CI restore fault to the validator rejection it must trigger.

A negative restore dispatch fails by design, so a failed job alone proves nothing. The
workflow labels a rejection only when it matches the gate the selected fault targets.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .core import EvolutionError

_HISTORY_EVENT_REJECTION = re.compile(
    r"^Invalid task queue history entry at index \d+: unsupported event type 'UNKNOWN_EVENT'$"
)


def _is_json_decode_rejection(exc: ValueError) -> bool:
    return (
        isinstance(exc, EvolutionError)
        and str(exc).startswith("Cannot read task queue: ")
        and isinstance(exc.__cause__, json.JSONDecodeError)
    )


# Fault name -> (gate label, matcher for the exception validate_queue_snapshot raises).
RESTORE_FAULT_GATES = {
    "tamper_bytes": (
        "queue_digest_mismatch",
        lambda exc: str(exc) == "TASK_QUEUE.json SHA-256 does not match source snapshot manifest",
    ),
    "corrupt_json": ("queue_json_unreadable", _is_json_decode_rejection),
    "bad_version": (
        "unsupported_queue_version",
        lambda exc: isinstance(exc, EvolutionError) and str(exc) == "Unsupported task queue format",
    ),
    "bad_history": (
        "unsupported_history_event",
        lambda exc: isinstance(exc, EvolutionError)
        and _HISTORY_EVENT_REJECTION.match(str(exc)) is not None,
    ),
    "drop_queue": (
        "queue_snapshot_missing",
        lambda exc: str(exc) == "Queue snapshot file is missing",
    ),
    "drop_manifest": (
        "queue_manifest_missing",
        lambda exc: str(exc) == "Queue snapshot manifest file is missing",
    ),
}


def expected_gate_label(fault: str) -> str:
    """Return the gate label a negative run with this fault must report."""
    if fault not in RESTORE_FAULT_GATES:
        raise ValueError(f"No snapshot validation gate is defined for restore fault {fault!r}")
    return RESTORE_FAULT_GATES[fault][0]


def matched_gate(fault: str, exc: ValueError) -> str | None:
    """Return the gate label when exc is the rejection this fault targets, else None."""
    gate = RESTORE_FAULT_GATES.get(fault)
    if gate is None or not gate[1](exc):
        return None
    return gate[0]


def inject_restore_fault(fault: str, snapshot: Path, manifest_path: Path) -> None:
    """Damage a downloaded snapshot so that validation must reject it at the fault's gate."""

    def rebind(data: bytes) -> None:
        # Keep the manifest consistent so the queue loader, not the hash check, must reject it.
        snapshot.write_bytes(data)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["task_queue_sha256"] = hashlib.sha256(data).hexdigest()
        manifest["task_queue_size_bytes"] = len(data)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if fault == "tamper_bytes":
        snapshot.write_bytes(snapshot.read_bytes() + b" ")
    elif fault == "corrupt_json":
        rebind(b'{"version": 1, "items": [')
    elif fault == "bad_version":
        queue = json.loads(snapshot.read_text(encoding="utf-8"))
        queue["version"] = 2
        rebind(json.dumps(queue).encode("utf-8"))
    elif fault == "bad_history":
        queue = json.loads(snapshot.read_text(encoding="utf-8"))
        queue["history"].append({"event": "UNKNOWN_EVENT", "task_id": "CI-RESTORE-DONE-PROBE"})
        rebind(json.dumps(queue).encode("utf-8"))
    elif fault == "drop_queue":
        snapshot.unlink()
    elif fault == "drop_manifest":
        manifest_path.unlink()
    else:
        raise ValueError(f"Unknown restore_fault {fault!r}")
