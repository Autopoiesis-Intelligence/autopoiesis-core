"""Fail-closed selection of the previous scheduled-cycle run."""

from __future__ import annotations

from typing import Any


WORKFLOW_PATH = ".github/workflows/autopoiesis-cycle.yml"
# autopoiesis-cycle.yml sets this run-name while AUTOPOIESIS_CYCLE_DISABLED is 'true'. Such a run
# fails at the emergency-stop step before checkout, so it changed no state and must not block the
# cycle once the owner re-enables it.
DISABLED_RUN_TITLE = "Autopoiesis cycle disabled by emergency stop"


def _positive_integer(value: Any) -> bool:
    """Return true for positive integers, excluding bool values."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def validate_emergency_stop_job_history(payload: Any) -> bool:
    """Accept only job evidence proving the guard stopped execution before checkout."""
    if not isinstance(payload, list) or not payload:
        raise ValueError("emergency-stop jobs history is incomplete or malformed")
    jobs = []
    for page in payload:
        if not isinstance(page, dict) or not isinstance(page.get("jobs"), list):
            raise ValueError("emergency-stop jobs page is malformed")
        jobs.extend(page["jobs"])
    if len(jobs) != 1 or not isinstance(jobs[0], dict) or jobs[0].get("name") != "cycle":
        raise ValueError("emergency-stop run must have exactly one cycle job")
    job = jobs[0]
    if job.get("status") != "completed" or job.get("conclusion") != "failure":
        raise ValueError("emergency-stop cycle job did not complete with failure")
    steps = job.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("emergency-stop step history is missing")
    names = [step.get("name") if isinstance(step, dict) else None for step in steps]
    if any(not isinstance(name, str) for name in names) or len(names) != len(set(names)):
        raise ValueError("emergency-stop step history is malformed or ambiguous")
    guard_name = "Enforce emergency stop"
    # The jobs API names an unnamed `uses:` step "Run <action>", e.g. "Run actions/checkout@v4".
    checkout_name = "Run actions/checkout@v4"
    if names.count(guard_name) != 1 or names.count(checkout_name) != 1:
        raise ValueError("emergency-stop guard or checkout step is missing or duplicated")
    guard_index = names.index(guard_name)
    checkout_index = names.index(checkout_name)
    if checkout_index <= guard_index:
        raise ValueError("checkout appears before the emergency-stop guard")
    if steps[guard_index].get("conclusion") != "failure":
        raise ValueError("emergency-stop guard did not fail")
    # The runner always appends "Complete job"; every workflow step after the guard must be skipped.
    if names[-1] != "Complete job":
        raise ValueError("emergency-stop step history does not end with the runner's Complete job step")
    if any(step.get("conclusion") != "skipped" for step in steps[guard_index + 1:-1]):
        raise ValueError("a step after the emergency-stop guard was not skipped")
    return True

def select_prior_successful_run(
    pages: Any, *, current_run_id: int, bootstrap: bool,
    verified_disabled_run_ids: set[int] | None = None
) -> dict[str, Any] | None:
    """Select the newest successful main-branch cycle from all API pages.

    Refuse malformed history and refuse to roll back to an older snapshot when a
    newer cycle failed or was rerun. Bootstrap is allowed only when no prior
    cycle run exists at all, so a failed run cannot be silently discarded.
    """
    if not isinstance(pages, list) or not pages:
        raise ValueError("workflow runs history is incomplete or malformed")
    if any(
        not isinstance(page, dict) or not isinstance(page.get("workflow_runs"), list)
        for page in pages
    ):
        raise ValueError("workflow runs page is malformed")

    runs = [run for page in pages for run in page["workflow_runs"]]
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("workflow runs history contains a non-object run entry")
        if not _positive_integer(run.get("id")):
            raise ValueError("workflow run id is missing or malformed")
        if not _positive_integer(run.get("run_number")):
            raise ValueError("workflow run run_number is missing or malformed")
        if not _positive_integer(run.get("run_attempt")):
            raise ValueError("workflow run run_attempt is missing or malformed")
        if not isinstance(run.get("head_branch"), str):
            raise ValueError("workflow run head_branch is missing or malformed")
        if not isinstance(run.get("path"), str):
            raise ValueError("workflow run path is missing or malformed")
        if run.get("conclusion") is not None and not isinstance(run.get("conclusion"), str):
            raise ValueError("workflow run conclusion is malformed")
        if not isinstance(run.get("display_title"), str):
            raise ValueError("workflow run display_title is missing or malformed")

    cycle_runs = [
        run
        for run in runs
        if run["id"] != current_run_id
        and run["head_branch"] == "main"
        and run["path"].split("@", 1)[0] == WORKFLOW_PATH
    ]
    verified_disabled_run_ids = verified_disabled_run_ids or set()
    for run in cycle_runs:
        if run["display_title"] == DISABLED_RUN_TITLE:
            if run.get("conclusion") != "failure" or run["run_attempt"] != 1:
                raise ValueError(
                    f"Emergency-stop run {run['id']} must have failed on its first attempt; "
                    f"got conclusion={run.get('conclusion')!r}, run_attempt={run['run_attempt']!r}"
                )
            if run["id"] not in verified_disabled_run_ids:
                raise ValueError(
                    f"Emergency-stop run {run['id']} has no verified job history"
                )
    relevant = [
        run
        for run in cycle_runs
        if run["display_title"] != DISABLED_RUN_TITLE
        # A skipped run never started the job (repository or branch guard), so it changed no state.
        and run.get("conclusion") != "skipped"
    ]
    relevant.sort(
        key=lambda run: (run["run_number"], run["id"]),
        reverse=True,
    )
    prior = [
        run
        for run in relevant
        if run.get("conclusion") == "success" and run["run_attempt"] == 1
    ]

    if relevant and (not prior or relevant[0] is not prior[0]):
        latest = relevant[0]
        raise ValueError(
            "Refusing to restore or bootstrap after an unresolved prior cycle: "
            f"newest run {latest['id']} has conclusion={latest.get('conclusion')!r} "
            f"and run_attempt={latest['run_attempt']!r}"
        )

    if prior and bootstrap:
        raise ValueError("Refusing bootstrap: a prior successful cycle already exists")
    if not prior and not bootstrap:
        raise ValueError("No successful prior snapshot; dispatch once with bootstrap=true")
    return prior[0] if prior else None
