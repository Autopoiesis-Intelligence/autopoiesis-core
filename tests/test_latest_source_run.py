"""Focused tests for selecting the newest eligible cross-run queue snapshot."""

import unittest

from autopoesis.queue_snapshot import (
    latest_source_run_id,
    require_latest_source_run,
)

WORKFLOW = ".github/workflows/ci.yml"
BRANCH = "gpt/a30-38-restore-selector-tests"


def run(run_id, *, branch=BRANCH, conclusion="success", event="workflow_dispatch",
        path=WORKFLOW, attempt=1):
    return {
        "id": run_id,
        "head_branch": branch,
        "conclusion": conclusion,
        "event": event,
        "path": f"{path}@refs/heads/{branch}",
        "run_attempt": attempt,
    }


def payload(*runs):
    return {"workflow_runs": list(runs)}


class LatestSourceRunTests(unittest.TestCase):
    def test_selects_highest_id_among_eligible_runs(self):
        runs = payload(
            run(10),
            run(12),
            run(11, conclusion="failure"),
            run(99, branch="main"),
            run(98, event="push"),
            run(97, path=".github/workflows/other.yml"),
        )
        self.assertEqual(
            latest_source_run_id(runs, current_run_id=20, current_branch=BRANCH),
            12,
        )

    def test_refuses_to_fall_back_when_newest_relevant_run_failed(self):
        runs = payload(
            run(10, conclusion="success"),
            run(30, conclusion="failure"),
            run(29, branch="main", conclusion="failure"),
            run(28, event="push", conclusion="failure"),
        )
        with self.assertRaisesRegex(ValueError, "newest workflow_dispatch snapshot run 30"):
            latest_source_run_id(
                runs,
                current_run_id=40,
                current_branch=BRANCH,
            )

    def test_refuses_to_fall_back_when_newest_relevant_run_was_rerun(self):
        runs = payload(
            run(10, conclusion="success", attempt=1),
            run(30, conclusion="success", attempt=2),
        )
        with self.assertRaisesRegex(ValueError, "run_attempt=1"):
            latest_source_run_id(
                runs,
                current_run_id=40,
                current_branch=BRANCH,
            )

    def test_excludes_current_run(self):
        runs = payload(run(10), run(20))
        self.assertEqual(
            latest_source_run_id(runs, current_run_id=20, current_branch=BRANCH),
            10,
        )

    def test_refuses_when_no_eligible_source_exists(self):
        cases = (
            payload(),
            payload(run(10, conclusion="failure")),
            payload(run(10, event="push")),
            payload(run(10, branch="main")),
            payload(run(10, path=".github/workflows/other.yml")),
            payload(run(20)),  # current run is never its own restore source
        )
        for candidate_runs in cases:
            with self.subTest(runs=candidate_runs):
                with self.assertRaisesRegex(ValueError, "No successful workflow_dispatch"):
                    latest_source_run_id(
                        candidate_runs,
                        current_run_id=20,
                        current_branch=BRANCH,
                    )

    def test_rejects_stale_source_and_accepts_latest_source(self):
        runs = payload(run(10), run(12))
        base_provenance = {
            "source_run_id": 10,
            "source_head_sha": "a" * 40,
        }
        with self.assertRaisesRegex(ValueError, "is not the latest snapshot"):
            require_latest_source_run(
                base_provenance,
                runs,
                current_run_id=20,
                current_branch=BRANCH,
            )

        accepted = require_latest_source_run(
            {**base_provenance, "source_run_id": 12},
            runs,
            current_run_id=20,
            current_branch=BRANCH,
        )
        self.assertTrue(accepted["source_is_latest"])
        self.assertEqual(accepted["source_branch"], BRANCH)

    def test_rejects_malformed_payload_or_branch(self):
        with self.assertRaisesRegex(ValueError, "JSON object"):
            latest_source_run_id([], current_run_id=20, current_branch=BRANCH)
        with self.assertRaisesRegex(ValueError, "entry 0 must be a JSON object"):
            latest_source_run_id(
                {"workflow_runs": [None, run(10)]},
                current_run_id=20,
                current_branch=BRANCH,
            )
        with self.assertRaisesRegex(ValueError, "entry 0 must contain an integer run ID"):
            latest_source_run_id(
                {"workflow_runs": [{"id": "10"}, run(10)]},
                current_run_id=20,
                current_branch=BRANCH,
            )
        with self.assertRaisesRegex(ValueError, "non-empty"):
            latest_source_run_id(payload(run(10)), current_run_id=20, current_branch="")


if __name__ == "__main__":
    unittest.main()
