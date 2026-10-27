# E4: Trust Boundaries and Untrusted Execution

**Status:** Proposed; documentation only. Implementation and runtime isolation are not proven.
**Baseline reviewed:** `4ae19f49f480246a2b42a3e9457190d43f03db6b`
**Scope:** Candidate code and generated tests executed by GitHub Actions.

## 1. Security objective

Untrusted candidate execution must not be able to modify trusted queue state, forge trusted completion evidence, access credentials it does not need, or acquire authority to change protected repository state.

A successful test is evidence about a particular input and execution. It is not authorization to accept a candidate or merge a pull request.

## 2. Assets

- Protected branches, repository settings, workflow permissions, and credentials.
- Task queue, event history, leases, attempts, and verification records.
- Provenance of source SHA, execution inputs, test commands, results, and artifacts.
- Runner filesystem, environment, process tree, and network boundary.
- Integrity and reproducibility of audit evidence.

## 3. Adversary assumptions

Treat candidate code, generated tests, handler output, patches, and downloaded artifacts as hostile. They may attempt to:

- Read environment variables or accessible files.
- Modify the checkout, queue, history, or verification records.
- Forge PASS, task identity, attempt, source SHA, commit, or tree values.
- Escape a workspace using path traversal or symlinks.
- Access the network or exfiltrate accessible data.
- Spawn child processes that outlive a timeout.
- Exhaust CPU, memory, disk, or output limits.
- Change tests or evidence used to evaluate the candidate.

A subprocess, temporary directory, clean environment, or successful CI run alone is not proof of OS-level isolation.

## 4. Trust boundaries

### TB-1: Trusted coordinator

The coordinator resolves and records the source SHA, validates task policy, issues a bounded request, assigns the attempt identity, and independently validates returned evidence. Executor-controlled fields are claims, not authority.

Only the trusted coordinator may authorize a transition to DONE. The transition must bind to the expected task, source, attempt, lease, verification result, and resulting commit/tree where applicable. Missing, stale, mismatched, or failed evidence must fail closed.

### TB-2: Untrusted execution job

- Use an ephemeral GitHub-hosted runner for hostile candidate execution; do not use persistent self-hosted runners for this purpose.
- Use minimum token permissions, defaulting to `contents: read` where sufficient.
- Provide no repository, deployment, or third-party secrets to the untrusted job.
- Do not grant write permissions, `id-token: write`, or privileged environment access.
- Never execute untrusted pull-request code in a privileged `pull_request_target` workflow.
- Pin execution inputs to an exact commit/SHA rather than a mutable branch.
- Bound duration, output, artifact size, file count, and resource consumption.
- Demonstrate timeout cleanup for the entire process tree, not only the direct child.
- State the actual filesystem and network controls. Do not claim network denial unless enforced and tested.

These controls reduce exposure but do not by themselves establish complete hostile-code containment.

### TB-3: Artifacts and reports

Treat every report and artifact from the execution job as untrusted data. Before use, validate:

- Closed schema and supported schema version.
- Repository, source SHA, task ID, attempt ID, and execution identity.
- Patch and artifact digests.
- Allowed paths, file types, sizes, and file counts.
- Command identity, exit status, timeout state, and required output.
- Consistency between the pinned input and the evidence returned.

Reject path traversal, symlinks where disallowed, duplicate or unexpected paths, malformed patches, and digest mismatches. A digest proves byte identity, not safety or truth of the report.

Do not execute an untrusted artifact in a privileged job. Job dependencies and artifact transfer are not security boundaries by themselves.

### TB-4: Acceptance and protected state

The executor cannot authorize its own result. A handler-provided PASS, synthetic persistence probe, or green CI badge is insufficient by itself. Acceptance requires independent verification against the pinned task and execution inputs.

No automatic merge or protected-branch write is permitted. Changes to repository permissions, secrets, or security-sensitive workflow triggers require explicit owner authorization.

## 5. Required workflow properties

1. Separate hostile-code execution from jobs that can write repository state, publish releases, deploy, or access secrets.
2. Keep the untrusted job secret-free and least-privileged.
3. Pin source and candidate inputs; record exact workflow revision and run ID.
4. Transfer only the minimum report or patch needed for review.
5. Validate all transferred data before use; never treat it as executable trusted code.
6. Keep verification and acceptance authority in trusted code that the candidate cannot modify during the same execution.
7. Preserve logs and evidence without leaking secrets.
8. Document the enforcement mechanism and residual risks for filesystem, network, process, and resource boundaries.

## 6. Negative security test plan

| ID | Attack | Acceptance criterion |
|---|---|---|
| E4-N01 | Read secret-like environment variables | No secrets are provisioned to the untrusted job; test records only safe presence/absence facts |
| E4-N02 | Modify trusted queue/history | Trusted state remains unchanged; attempted write is denied or occurs only in disposable state |
| E4-N03 | Path traversal or symlink escape | Input is rejected; no out-of-scope file changes |
| E4-N04 | Forge PASS, task ID, attempt, SHA, or tree | Independent validator rejects the forged record |
| E4-N05 | Change source after snapshot creation | Executed input remains pinned or the run is rejected |
| E4-N06 | Spawn a child that survives timeout | Entire process tree is terminated within the declared bound |
| E4-N07 | Attempt outbound network access | Observed behavior matches an explicit, enforced network policy |
| E4-N08 | Flood output or create oversized artifacts | Bounded failure; trusted state remains intact |
| E4-N09 | Malformed/duplicate/unexpected artifact entries | Artifact is rejected |
| E4-N10 | Verification failure or timeout | No DONE transition |
| E4-N11 | Seek write-capable credentials | No write-capable credential is available to the untrusted job |
| E4-N12 | Replay stale evidence after retry | Stale attempt/lease evidence is rejected |
| E4-N13 | Modify tests or verification logic during execution | Acceptance uses trusted verification logic outside candidate control |
| E4-N14 | Candidate writes to checkout/queue through shared filesystem | No trusted state is shared writable with the candidate |

For every test, record the exact SHA, CI run/job, observed result, and retained evidence. A fixture that merely contains an expected result is not a runtime test.

## 7. Isolation levels

- **Level 0 — Workspace separation:** temporary directory or copied package only. Not a hostile-code security boundary.
- **Level 1 — Restricted CI job:** ephemeral hosted runner, no secrets, least-privilege token, bounded execution, minimal environment, and validated artifacts. Reduces risk; does not prove complete containment.
- **Level 2 — Enforced execution boundary:** demonstrated filesystem, process, resource, and network controls, backed by adversarial runtime tests. The concrete mechanism and residual escape risks must be named.

Do not claim Level 2 until the selected enforcement mechanism and tests support that claim. A container alone must not be described as complete isolation from hostile code.

## 8. Evidence gate

E4 remains BLOCKED until evidence includes:

- Exact source SHA and workflow revision.
- Exact CI run ID and relevant job links.
- Review of the actual call paths and permission configuration.
- Negative-test outcomes for the applicable threats.
- Evidence that the untrusted job received no secrets or write-capable credentials.
- Demonstrated timeout and descendant-process behavior.
- Demonstrated artifact validation and network/filesystem policy.
- Independent review and explicit residual-risk list.

Track evidence through the project's ladder:
`DESIGN → IMPLEMENTED → REACHABLE → RUNTIME → PERSISTED → AUDITED → CI_PROVEN`.

Evidence for one stage does not imply later stages.

## 9. Explicit non-goals

This document does not authorize automatic merge, protected-branch writes, permission expansion, new secrets, or claims of complete isolation based solely on temporary directories or passing unit tests.

## 10. Acceptance decision

E4 may pass only for a clearly stated scope when controls are implemented, negative tests pass on an exact revision, and runtime evidence supports each claim. Until then, hostile-code isolation is **BLOCKED / NOT PROVEN**.

## 11. Implementation sequence

1. Map every candidate-execution call path and every queue/evidence write.
2. Identify whether untrusted code can reach trusted state through shared filesystem, injected handlers, imports, subprocesses, or artifacts.
3. Design the smallest trusted/untrusted boundary consistent with the threat model.
4. Implement only on a feature branch; do not alter protected branch or privileged workflow settings as part of an unreviewed change.
5. Add negative tests and run them in CI.
6. Audit the exact resulting SHA and record residual risks before claiming E4 completion.
