"""Contract tests for CI restore source-history selection."""
from pathlib import Path
import unittest


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


class CIRestoreWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_latest_source_query_does_not_hide_failed_dispatches(self):
        self.assertNotIn("status=success", self.source)
        self.assertIn("event=workflow_dispatch&branch=${GITHUB_REF_NAME}&per_page=100", self.source)
        self.assertIn('gh api --paginate --slurp "repos/${GITHUB_REPOSITORY}/actions/workflows/ci.yml/runs?', self.source)

    def test_candidate_history_is_paginated_and_flattened_before_selection(self):
        self.assertIn(".restore-candidates-pages.json", self.source)
        self.assertIn('pages = json.loads(', self.source)
        self.assertIn('Path(".restore-candidates-pages.json").read_text(encoding="utf-8")', self.source)
        self.assertIn('not isinstance(page.get("workflow_runs"), list)', self.source)
        self.assertIn('Refusing: paginated workflow run history is malformed or incomplete', self.source)
        self.assertIn('"workflow_runs": [', self.source)
        self.assertIn('run for page in pages for run in page["workflow_runs"]', self.source)

    def test_latest_source_revalidation_uses_paginated_unfiltered_history(self):
        self.assertIn('"--paginate",\n                  "--slurp",', self.source)
        self.assertIn("run_pages = json.loads(runs_response.stdout)", self.source)
        self.assertIn('raise SystemExit("Refusing: workflow run history is malformed or incomplete")', self.source)
        self.assertIn("run_history = {\"workflow_runs\": [", self.source)
        self.assertIn("provenance,\n              run_history,", self.source)


if __name__ == "__main__":
    unittest.main()
