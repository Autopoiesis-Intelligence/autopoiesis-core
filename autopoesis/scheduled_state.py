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


def select_prior_successful_run(
    pages: Any, *, current_run_id: int, bootstrap: bool
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
    for run in cycle_runs:
        if run["display_title"] == DISABLED_RUN_TITLE and (
            run.get("conclusion") != "failure" or run["run_attempt"] != 1
        ):
            raise ValueError(
                f"Emergency-stop run {run['id']} must have failed on its first attempt; "
                f"got conclusion={run.get('conclusion')!r}, run_attempt={run['run_attempt']!r}"
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
