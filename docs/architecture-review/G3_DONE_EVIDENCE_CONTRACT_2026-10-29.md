# G3 DONE Evidence Contract

Status: implementation contract for the isolated `g3/done-evidence-contract` work branch. This document is not runtime or CI evidence.

## Problem

Queue status and verification evidence are currently independent: `record_outcome(..., "DONE")` can change the lifecycle state without a PASS event. A PASS event can also be recorded for a different task, and existing verification records do not bind the result to an attempt, lease, commit, or tree.

## Required invariant

A task may transition to `DONE` only when all of these values match the currently active attempt:

- `task_id`: exact queue item ID.
- `attempt`: positive integer equal to the item's current attempt number.
- `lease_id`: unique opaque token issued when that attempt enters `IN_PROGRESS`.
- `commit_sha`: full lowercase 40-character Git commit SHA that was checked out for the attempt.
- `tree_sha`: full lowercase 40-character Git tree SHA from that same commit.
- `verification_status`: `PASS`.
- `verification_level`: a non-empty description of what actually ran.
- `artifact_sha256`: optional digest of a produced report/artifact; it is not a substitute for the five identity bindings.

A PASS with a missing binding, malformed binding, a different task/attempt/lease/commit/tree, or a later FAIL for the same binding MUST NOT authorize DONE. Notes, event timestamps, commit messages, and a bare status string are not evidence bindings.

## Lifecycle/API boundary

1. An explicit start-attempt operation moves an eligible task to `IN_PROGRESS`, increments its attempt number, and stores the caller-supplied lease ID plus commit/tree identity. The function must reject empty or malformed values.
2. A verification-record operation accepts the complete binding and appends it to `VERIFICATION_RECORDED`; it does not itself change lifecycle status.
3. `DONE` checks the queue item's active binding against the latest verification record for that exact task/attempt/lease/commit/tree. It fails closed if there is no exact PASS.
4. A new attempt supersedes previous evidence for completion purposes. A PASS from an earlier attempt must never authorize the current attempt.
5. File-level operations retain the existing queue write lock and atomic replacement behavior. The in-memory transition and file transition must enforce the same rule.

## Caller responsibility

The executor/CI adapter must derive the full commit SHA and tree SHA from the exact source snapshot it actually tested, and must pass those values into the lifecycle API. The queue library cannot infer that the tests genuinely ran merely because a caller supplies a PASS label. Runtime provenance must be established by the adapter and checked separately.

## Compatibility and migration

Existing `DONE` calls that provide no bound PASS will intentionally fail. Existing persisted queue history remains readable only if the schema validator explicitly treats old records as legacy/unbound evidence; legacy records never authorize new DONE transitions. Do not silently infer missing bindings from timestamps or neighboring events.

## Out of scope

- No changes to `main`, branch protection, repository permissions, workflow triggers, secrets, or scheduled workflows.
- No claim of cross-run persistence or autonomous execution from these local queue tests.
- No claim that a lease ID by itself proves process isolation or prevents a malicious caller from forging verification records.
