"""Behavioral tests for scheduled-cycle source selection."""

import unittest

from autopoesis.scheduled_state import DISABLED_RUN_TITLE, select_prior_successful_run


WORKFLOW = ".github/workflows/autopoiesis-cycle.yml"


def run(run_id, number, *, conclusion="success", branch="main", path=WORKFLOW, title="Autopoiesis scheduled cycle", attempt=1):
    return {
        "id": run_id,
        "run_number": number,
        "run_attempt": attempt,
        "display_title": title,
        "conclusion": conclusion,
        "head_branch": branch,
        "path": path,
        "head_sha": f"{run_id:040x}",
    }


class ScheduledStateSelectionTests(unittest.TestCase):
    def test_finds_latest_success_after_first_api_page(self):
        first_page = {"workflow_runs": [run(i, i) for i in range(1, 101)]}
        second_page = {"workflow_runs": [run(101, 101)]}
        selected = select_prior_successful_run(
            [first_page, second_page], current_run_id=102, bootstrap=False
        )
        self.assertEqual(selected["id"], 101)

    def test_newer_failed_cycle_refuses_rollback_to_older_snapshot(self):
        pages = [{"workflow_runs": [
            run(10, 10, conclusion="success"),
            run(11, 11, conclusion="failure"),
        ]}]
        with self.assertRaisesRegex(ValueError, "unresolved prior cycle"):
            select_prior_successful_run(pages, current_run_id=12, bootstrap=False)

    def test_newer_cancelled_cycle_refuses_rollback(self):
        pages = [{"workflow_runs": [
            run(10, 10, conclusion="success"),
            run(11, 11, conclusion="cancelled"),
        ]}]
        with self.assertRaisesRegex(ValueError, "newest run 11"):
            select_prior_successful_run(pages, current_run_id=12, bootstrap=False)

    def test_rerun_attempt_is_never_selected_as_persisted_state(self):
        pages = [{"workflow_runs": [
            run(10, 10, conclusion="success"),
            {**run(11, 11, conclusion="success"), "run_attempt": 2},
        ]}]
        with self.assertRaisesRegex(ValueError, "run_attempt=2"):
            select_prior_successful_run(pages, current_run_id=12, bootstrap=False)

    def test_skipped_runs_from_the_disable_switch_are_ignored(self):
        disabled_only = [{"workflow_runs": [run(11, 11, conclusion="skipped")]}]
        self.assertIsNone(select_prior_successful_run(disabled_only, current_run_id=12, bootstrap=True))
        with self.assertRaisesRegex(ValueError, "No successful prior snapshot"):
            select_prior_successful_run(disabled_only, current_run_id=12, bootstrap=False)
        paused_after_success = [{"workflow_runs": [
            run(10, 10, conclusion="success"),
            run(11, 11, conclusion="skipped"),
        ]}]
        selected = select_prior_successful_run(paused_after_success, current_run_id=12, bootstrap=False)
        self.assertEqual(selected["id"], 10)

    def test_emergency_stop_failures_do_not_block_the_cycle_after_re_enabling(self):
        stopped = [{"workflow_runs": [
            run(10, 10),
            run(11, 11, conclusion="failure", title=DISABLED_RUN_TITLE),
            run(12, 12, conclusion="failure", title=DISABLED_RUN_TITLE),
        ]}]
        self.assertEqual(select_prior_successful_run(stopped, current_run_id=13, bootstrap=False, verified_disabled_run_ids={11, 12})["id"], 10)
        with self.assertRaisesRegex(ValueError, "Refusing bootstrap"):
            select_prior_successful_run(stopped, current_run_id=13, bootstrap=True, verified_disabled_run_ids={11, 12})
        stopped_before_any_cycle = [{"workflow_runs": [run(11, 11, conclusion="failure", title=DISABLED_RUN_TITLE)]}]
        self.assertIsNone(select_prior_successful_run(stopped_before_any_cycle, current_run_id=12, bootstrap=True, verified_disabled_run_ids={11, 12}))

        real_failure_after_stop = [{"workflow_runs": [
            run(10, 10),
            run(11, 11, conclusion="failure", title=DISABLED_RUN_TITLE),
            run(12, 12, conclusion="failure"),
        ]}]
        with self.assertRaisesRegex(ValueError, "newest run 12"):
            select_prior_successful_run(real_failure_after_stop, current_run_id=13, bootstrap=False, verified_disabled_run_ids={11, 12})

        for odd in (run(11, 11, conclusion="success", title=DISABLED_RUN_TITLE),
                    run(11, 11, conclusion="failure", title=DISABLED_RUN_TITLE, attempt=2),
                    run(11, 11, conclusion=None, title=DISABLED_RUN_TITLE)):
            with self.assertRaisesRegex(ValueError, "Emergency-stop run 11"):
                select_prior_successful_run([{"workflow_runs": [run(10, 10), odd]}], current_run_id=13, bootstrap=False, verified_disabled_run_ids={11, 12})

        untitled = run(11, 11)
        del untitled["display_title"]
        with self.assertRaisesRegex(ValueError, "display_title"):
            select_prior_successful_run([{"workflow_runs": [untitled]}], current_run_id=13, bootstrap=False, verified_disabled_run_ids={11, 12})

    def test_bootstrap_refused_after_failed_only_history(self):
        pages = [{"workflow_runs": [run(11, 11, conclusion="failure")]}]
        with self.assertRaisesRegex(ValueError, "unresolved prior cycle"):
            select_prior_successful_run(pages, current_run_id=12, bootstrap=True)

    def test_bootstrap_refused_after_cancelled_only_history(self):
        pages = [{"workflow_runs": [run(11, 11, conclusion="cancelled")]}]
        with self.assertRaisesRegex(ValueError, "unresolved prior cycle"):
            select_prior_successful_run(pages, current_run_id=12, bootstrap=True)

    def test_bootstrap_refused_when_success_is_only_on_later_page(self):
        pages = [
            {"workflow_runs": [run(i, i, conclusion="failure") for i in range(1, 101)]},
            {"workflow_runs": [run(101, 101)]},
        ]
        with self.assertRaisesRegex(ValueError, "prior successful cycle"):
            select_prior_successful_run(pages, current_run_id=102, bootstrap=True)

    def test_malformed_page_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "malformed"):
            select_prior_successful_run([{"unexpected": []}], current_run_id=102, bootstrap=True)

    def test_non_object_run_entry_fails_closed(self):
        pages = [{"workflow_runs": [run(10, 10), "malformed"]}]
        with self.assertRaisesRegex(ValueError, "non-object"):
            select_prior_successful_run(pages, current_run_id=11, bootstrap=True)

    def test_missing_or_non_integer_required_fields_fail_closed(self):
        for field, value in (
            ("id", None),
            ("id", "10"),
            ("id", True),
            ("run_number", None),
            ("run_number", "10"),
            ("run_number", False),
            ("run_attempt", None),
            ("run_attempt", "1"),
            ("run_attempt", True),
        ):
            with self.subTest(field=field, value=value):
                malformed = run(10, 10)
                if value is None:
                    malformed.pop(field)
                else:
                    malformed[field] = value
                with self.assertRaisesRegex(ValueError, "missing or malformed"):
                    select_prior_successful_run(
                        [{"workflow_runs": [malformed]}],
                        current_run_id=11,
                        bootstrap=True,
                    )

    def test_missing_or_non_string_branch_and_path_fail_closed(self):
        for field, value in (
            ("head_branch", None),
            ("head_branch", 3),
            ("path", None),
            ("path", 3),
        ):
            with self.subTest(field=field, value=value):
                malformed = run(10, 10)
                malformed[field] = value
                with self.assertRaisesRegex(ValueError, "missing or malformed"):
                    select_prior_successful_run(
                        [{"workflow_runs": [malformed]}],
                        current_run_id=11,
                        bootstrap=True,
                    )

    def test_bootstrap_only_allowed_when_no_prior_cycle_exists(self):
        pages = [{"workflow_runs": []}]
        self.assertIsNone(select_prior_successful_run(pages, current_run_id=2, bootstrap=True))
        with self.assertRaisesRegex(ValueError, "No successful prior snapshot"):
            select_prior_successful_run(pages, current_run_id=2, bootstrap=False)


    def test_emergency_stop_requires_step_evidence(self):
        history = [{"workflow_runs": [run(10, 10), run(11, 11, conclusion="failure", title=DISABLED_RUN_TITLE)]}]
        with self.assertRaisesRegex(ValueError, "lacks verified guard/step evidence"):
            select_prior_successful_run(history, current_run_id=12, bootstrap=False)

    def test_emergency_stop_job_history_matches_the_real_jobs_api_shape(self):
        # Step names as the jobs API reports them; checked against run 40099720954's jobs.
        def jobs(guard="failure", after="skipped", *, extra=()):
            steps = [{"name": "Set up job", "conclusion": "success"},
                     {"name": "Enforce emergency stop", "conclusion": guard},
                     {"name": "Run actions/checkout@v4", "conclusion": after},
                     {"name": "Run actions/setup-python@v5", "conclusion": "skipped"},
                     *extra,
                     {"name": "Complete job", "conclusion": "success"}]
            return [{"jobs": [{"name": "cycle", "status": "completed", "conclusion": "failure", "steps": steps}]}]

        self.assertTrue(validate_emergency_stop_job_history(jobs()))
        # Race: the run was titled while disabled, then the variable was cleared, so the guard was skipped.
        with self.assertRaisesRegex(ValueError, "guard did not fail"):
            validate_emergency_stop_job_history(jobs(guard="skipped", after="success"))
        with self.assertRaisesRegex(ValueError, "was not skipped"):
            validate_emergency_stop_job_history(jobs(after="success"))
        with self.assertRaisesRegex(ValueError, "was not skipped"):
            validate_emergency_stop_job_history(jobs(extra=({"name": "Persist next queue state", "conclusion": "success"},)))
        truncated = jobs()
        truncated[0]["jobs"][0]["steps"].pop()
        with self.assertRaisesRegex(ValueError, "Complete job"):
            validate_emergency_stop_job_history(truncated)
        with self.assertRaises(ValueError):
            validate_emergency_stop_job_history([{"jobs": []}])

if __name__ == "__main__":
    unittest.main()
