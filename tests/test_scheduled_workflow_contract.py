"""Regression checks for the scheduled workflow's safety contract.

These checks intentionally inspect the workflow source without requiring PyYAML.
The CI YAML parser separately validates syntax; this test protects key operational
guards from being accidentally removed during edits.
"""
from pathlib import Path
import unittest


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "autopoiesis-cycle.yml"


class ScheduledWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_schedule_and_manual_bootstrap_are_explicit(self):
        self.assertIn('cron: "17 */6 * * *"', self.source)
        self.assertIn("workflow_dispatch:", self.source)
        self.assertIn("default: false", self.source)
        self.assertIn("BOOTSTRAP: ${{ inputs.bootstrap || false }}", self.source)

    def test_execution_is_restricted_and_serialized(self):
        self.assertIn("github.repository == 'Autopoiesis-Intelligence/autopoiesis-core'", self.source)
        self.assertIn("github.ref == 'refs/heads/main'", self.source)
        self.assertIn("vars.AUTOPOIESIS_CYCLE_DISABLED == 'true'", self.source)
        self.assertIn("Enforce emergency stop", self.source)
        self.assertIn("cancel-in-progress: false", self.source)
        self.assertIn("timeout-minutes: 20", self.source)

    def test_disable_guard_fails_run_before_any_cycle_work(self):
        # A fully skipped workflow can still be reported successful by GitHub.
        # The emergency guard must fail the job before checkout/state selection,
        # so that run cannot be mistaken for a successful persisted cycle.
        lines = self.source.splitlines()
        jobs_at = lines.index("jobs:")
        job_names = [line for line in lines[jobs_at + 1:]
                     if line.startswith("  ") and not line.startswith("   ") and line.rstrip().endswith(":")]
        self.assertEqual(job_names, ["  cycle:"])
        job_if = lines[lines.index("  cycle:") + 1]
        self.assertIn("github.repository == 'Autopoiesis-Intelligence/autopoiesis-core'", job_if)
        self.assertIn("github.ref == 'refs/heads/main'", job_if)
        self.assertNotIn("AUTOPOIESIS_CYCLE_DISABLED", job_if)
        guard_at = lines.index("      - name: Enforce emergency stop")
        checkout_at = lines.index("      - uses: actions/checkout@v4")
        self.assertLess(guard_at, checkout_at)
        guard = "\n".join(lines[guard_at:checkout_at])
        self.assertIn("if: ${{ vars.AUTOPOIESIS_CYCLE_DISABLED == 'true' }}", guard)
        self.assertIn("exit 1", guard)
        self.assertNotIn("||", job_if)

    def test_restore_is_provenance_bound_and_fail_closed(self):
        self.assertIn("status=completed&per_page=100", self.source)
        self.assertIn("gh api --paginate --slurp", self.source)
        self.assertIn("from autopoesis.scheduled_state import select_prior_successful_run", self.source)
        selector = (Path(__file__).resolve().parents[1] / "autopoesis" / "scheduled_state.py").read_text(encoding="utf-8")
        self.assertIn("def _positive_integer(value: Any) -> bool:", selector)
        self.assertIn('if not _positive_integer(run.get("run_attempt")):', selector)
        self.assertIn('run["run_attempt"] == 1', selector)
        self.assertIn('if not _positive_integer(run.get("id")):', selector)
        self.assertIn('if not _positive_integer(run.get("run_number")):', selector)
        self.assertIn('if not isinstance(run.get("head_branch"), str):', selector)
        self.assertIn('if not isinstance(run.get("path"), str):', selector)
        self.assertIn("pages = json.loads(Path(\".cycle-runs-pages.json\").read_text())", self.source)
        self.assertIn("conclusion", self.source)
        self.assertIn("source_run_id", self.source)
        self.assertIn("source_head_sha", self.source)
        self.assertIn("workflow_run", self.source)
        self.assertIn("sha256:[0-9a-f]{64}", self.source)
        self.assertIn("validate_queue_snapshot", self.source)
        self.assertIn("install_validated_queue_snapshot", self.source)

    def test_cycle_is_bounded_and_failure_is_not_hidden(self):
        self.assertIn("--budget-seconds 600", self.source)
        self.assertIn("set -o pipefail", self.source)
        self.assertIn("continue-on-error: true", self.source)
        self.assertIn("steps.cycle.outcome == 'failure'", self.source)

    def test_state_is_persisted_with_manifest(self):
        self.assertIn("create_queue_snapshot_manifest", self.source)
        self.assertIn("QUEUE_SNAPSHOT_MANIFEST.json", self.source)
        self.assertIn("name: autopoiesis-cycle-state", self.source)
        self.assertIn("retention-days: 90", self.source)

    def test_emergency_stop_run_name_matches_the_selector_title(self):
        from autopoesis.scheduled_state import DISABLED_RUN_TITLE

        run_name = next(line for line in self.source.splitlines() if line.startswith("run-name: "))
        self.assertIn(f"vars.AUTOPOIESIS_CYCLE_DISABLED == 'true' && '{DISABLED_RUN_TITLE}'", run_name)
        guard = self.source.split("      - name: Enforce emergency stop", 1)[1].split("      - ", 1)[0]
        self.assertIn("if: ${{ vars.AUTOPOIESIS_CYCLE_DISABLED == 'true' }}", guard)
        self.assertIn("exit 1", guard)


    def test_restore_validates_emergency_stop_job_history(self):
        source = Path(WORKFLOW).read_text()
        self.assertIn("validate_emergency_stop_job_history", source)
        self.assertIn("/actions/runs/", source)
        self.assertIn("/jobs?per_page=100", source)
        self.assertIn("verified_disabled_run_ids", source)

if __name__ == "__main__":
    unittest.main()
