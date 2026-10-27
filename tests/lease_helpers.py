"""Helpers for tests that walk the leased task lifecycle."""

from autopoesis.task_queue import advance_task, advance_task_file, load_queue

OWNER = "unit-test"


def token_of(queue, task_id):
    item = next(entry for entry in queue["items"] if entry["id"] == task_id)
    return (item.get("lease") or {}).get("token")


def step(queue, task_id, *statuses, note="", commit_sha=None, tree_sha=None):
    """Advance an in-memory queue through statuses as the current lease holder."""
    for status in statuses:
        queue = advance_task(queue, task_id, status, note, owner=OWNER, token=token_of(queue, task_id),
                             commit_sha=commit_sha, tree_sha=tree_sha)["queue"]
    return queue


def step_file(path, task_id, *statuses, note="", commit_sha=None, tree_sha=None):
    """Advance a queue file through statuses as the current lease holder."""
    result = None
    for status in statuses:
        token = token_of(load_queue(path), task_id)
        result = advance_task_file(path, task_id, status, note, owner=OWNER, token=token,
                                   commit_sha=commit_sha, tree_sha=tree_sha)
    return result
