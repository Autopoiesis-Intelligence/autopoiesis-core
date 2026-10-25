"""Fail-closed selection of the previous scheduled-cycle run."""

from __future__ import annotations

from typing import Any


WORKFLOW_PATH = ".github/workflows/autopoiesis-cycle.yml"


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
    if any(not isinstance(page, dict) or not isinstance(page.get("workflow_runs"), list)
           for page in pages):
        raise ValueError("workflow runs page is malformed")

    runs = [run for page in pages for run in page["workflow_runs"]]
    relevant = [
        run for run in runs
        if isinstance(run, dict)
        and run.get("id") != current_run_id
        and run.get("head_branch") == "main"
        and isinstance(run.get("path"), str)
        and run["path"].split("@", 1)[0] == WORKFLOW_PATH
    ]
    relevant.sort(
        key=lambda run: (run.get("run_number", 0), run.get("id", 0)),
        reverse=True,
    )
    prior = [
        run for run in relevant
        if run.get("conclusion") == "success"
        and run.get("run_attempt", 1) == 1
    ]

    if relevant and (not prior or relevant[0] is not prior[0]):
        latest = relevant[0]
        raise ValueError(
            "Refusing to restore or bootstrap after an unresolved prior cycle: "
            f"newest run {latest.get('id')} has conclusion={latest.get('conclusion')!r} "
            f"and run_attempt={latest.get('run_attempt', 1)!r}"
        )

    if prior and bootstrap:
        raise ValueError("Refusing bootstrap: a prior successful cycle already exists")
    if not prior and not bootstrap:
        raise ValueError("No successful prior snapshot; dispatch once with bootstrap=true")
    return prior[0] if prior else None
