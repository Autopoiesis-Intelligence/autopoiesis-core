"""Each injected restore fault must be rejected at its own validation gate."""

import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from autopoesis.queue_snapshot import create_queue_snapshot_manifest, validate_queue_snapshot
from autopoesis.restore_fault_gates import (
    RESTORE_FAULT_GATES,
    expected_gate_label,
    inject_restore_fault,
    matched_gate,
)

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
SHA = "a" * 40
REPOSITORY = "Autopoiesis-Intelligence/autopoiesis-core"
RUN_ID = 123


def _rejection(fault):
    """Inject fault into a valid snapshot and return what validate_queue_snapshot raises."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        snapshot = root / "TASK_QUEUE.json"
        manifest_path = root / "QUEUE_SNAPSHOT_MANIFEST.json"
        snapshot.write_text(json.dumps({
            "version": 1,
            "items": [],
            "history": [{"event": "CANDIDATE_ADDED", "task_id": "CI-RESTORE-DONE-PROBE", "at": "2026-10-26T00:00:00Z"}],
        }), encoding="utf-8")
        manifest = create_queue_snapshot_manifest(
            snapshot, source_run_id=RUN_ID, source_head_sha=SHA, source_repository=REPOSITORY
        )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        inject_restore_fault(fault, snapshot, manifest_path)
        try:
            validate_queue_snapshot(
                snapshot,
                manifest_path,
                source_run_id=RUN_ID,
                source_head_sha=SHA,
                source_repository=REPOSITORY,
            )
        except ValueError as exc:
            return exc
    raise AssertionError(f"{fault} was not rejected")


class RestoreFaultGateTests(unittest.TestCase):
    def test_every_fault_is_rejected_at_its_own_gate(self):
        for fault in RESTORE_FAULT_GATES:
            with self.subTest(fault=fault):
                self.assertEqual(matched_gate(fault, _rejection(fault)), expected_gate_label(fault))

    def test_a_rejection_from_another_gate_is_not_counted(self):
        for fault in RESTORE_FAULT_GATES:
            for other in RESTORE_FAULT_GATES:
                if other == fault:
                    continue
                with self.subTest(fault=fault, rejected_by=other):
                    self.assertIsNone(matched_gate(fault, _rejection(other)))

    def test_unrelated_errors_and_unknown_faults_match_no_gate(self):
        self.assertIsNone(matched_gate("drop_queue", ValueError("Snapshot manifest run ID does not match verified source run")))
        self.assertIsNone(matched_gate("none", ValueError("Queue snapshot file is missing")))
        with self.assertRaisesRegex(ValueError, "tamper_archive"):
            expected_gate_label("tamper_archive")

    def test_gate_labels_are_distinct(self):
        labels = [label for label, _ in RESTORE_FAULT_GATES.values()]
        self.assertEqual(len(labels), len(set(labels)))


class WorkflowFaultGateWiringTests(unittest.TestCase):
    def test_workflow_uses_shared_fault_injection_and_gate_matchers(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("from autopoesis.restore_fault_gates import inject_restore_fault", workflow)
        self.assertIn("inject_restore_fault(fault, snapshot, manifest_path)", workflow)
        self.assertIn(
            "from autopoesis.restore_fault_gates import expected_gate_label, matched_gate",
            workflow,
        )
        self.assertIn("label = matched_gate(fault, exc)", workflow)
        self.assertIn("label == expected_gate_label(fault)", workflow)

    def test_workflow_does_not_reimplement_fault_gate_matchers(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn('task_queue_sha256_mismatch', workflow)
        self.assertNotIn('queue_json_decode_error', workflow)
        self.assertNotIn('invalid_queue_history_event', workflow)
        self.assertNotIn('missing_queue_snapshot', workflow)
        self.assertNotIn('missing_queue_manifest', workflow)


    def test_workflow_exposes_every_fault_and_asserts_its_canonical_label(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        input_block = workflow.split("      restore_fault:", 1)[1].split("\n  jobs:", 1)[0]
        for fault, (label, _) in RESTORE_FAULT_GATES.items():
            with self.subTest(fault=fault):
                self.assertIn(f"          - {fault}\n", input_block)
                self.assertIn(f"{fault}:{label}", workflow)


class WorkflowPythonHeredocTests(unittest.TestCase):
    # Raise this when a step adds a heredoc, so none escapes the compile check.
    EXPECTED_HEREDOCS = 8

    def test_every_python_heredoc_compiles(self):
        lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
        bodies = []
        index = 0
        while index < len(lines):
            if lines[index].rstrip().endswith("python - <<'PY'"):
                end = next(i for i in range(index + 1, len(lines)) if lines[i].strip() == "PY")
                bodies.append((index + 1, textwrap.dedent("\n".join(lines[index + 1:end]))))
                index = end
            index += 1
        self.assertEqual(len(bodies), self.EXPECTED_HEREDOCS)
        for line, body in bodies:
            with self.subTest(line=line):
                compile(body, f"ci.yml:{line}", "exec")


if __name__ == "__main__":
    unittest.main()
