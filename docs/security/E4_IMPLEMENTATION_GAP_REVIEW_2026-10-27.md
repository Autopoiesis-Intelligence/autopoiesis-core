# E4.3 Implementation Gap Review

**Status:** Source review only; no new tests executed during this review.
**Reviewed baseline:** `4ae19f49f480246a2b42a3e9457190d43f03db6b`
**Scope:** `autopoesis/executor.py`, `run_tasks.py`, `.github/workflows/ci.yml`, and `docs/AUTONOMY_ROADMAP_SPEC.md`.

## Findings

| ID | Area | Observed in reviewed source | Gap / evidence status | Priority |
|---|---|---|---|---|
| G-01 | Workspace | Executor uses a temporary directory and copies the package for generated-test verification | Workspace separation is not OS isolation; hostile-code containment not proven | P0 |
| G-02 | Environment | Child process receives a restricted environment | Reduces inherited environment exposure; does not prove filesystem or network denial | P0 |
| G-03 | Timeout | Subprocess timeout is configured | Termination of the complete descendant process tree is not proven | P1 |
| G-04 | Evidence authority | Queue and orchestration code contain verification/state-transition logic | Must verify every injected handler and write path; a handler-provided PASS must not be authoritative | P0 |
| G-05 | Source pinning | Snapshot and source identity concepts exist | Must trace every execution path to prove exact inputs are pinned end-to-end | P1 |
| G-06 | CI permissions | Reviewed `ci.yml` declares `actions: read` and `contents: read` | Positive least-privilege signal for that workflow; does not prove all workflows/jobs are safe | P1 |
| G-07 | Network | No enforced network-denial control was established by the reviewed executor code | Network policy and runtime behavior not proven | P1 |
| G-08 | Artifact handling | Workflow uploads artifacts; executor creates temporary workspaces | Need prove artifacts are treated only as hostile data and never executed in a privileged job | P1 |
| G-09 | Adversarial tests | Existing unit tests cover executor and queue behavior | No malicious runtime probes were run as part of this review | P1 |

## Required next actions

1. Trace the full call graph for generated tests, handlers, queue writes, verification writes, and transition to DONE.
2. Identify the smallest shared writable state reachable by candidate execution.
3. Add isolated negative tests for forged PASS, queue mutation, path traversal/symlinks, timeout descendants, stale evidence replay, and artifact validation.
4. Inspect every workflow that can run candidate-controlled code, not only `ci.yml`.
5. Choose and document the actual execution isolation mechanism. Do not infer network denial or process-tree cleanup from a timeout parameter.
6. Run the tests in GitHub Actions and retain exact SHA, run ID, logs, and outcomes.
7. Request independent review before changing E4 to PASS.

## Decision

**E4 remains BLOCKED / NOT PROVEN.** This is an evidence gap and a security-boundary concern, not a claim that every listed attack has been reproduced. No workflow permissions, secrets, or protected-branch settings were changed in this review.
