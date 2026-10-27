# E4.4 Negative Security Test Plan

**Status:** Test design only; tests have not yet been implemented or executed.
**Baseline reviewed:** `4ae19f49f480246a2b42a3e9457190d43f03db6b`
**Scope:** GitHub Actions execution of generated test artifacts and trusted task-state handling.

## 1. Current positive control observed

The reviewed `.github/workflows/copilot-test-writer.yml` has a distinct `verify` job with `permissions: {}`, no declared secrets, a throwaway repository copy, and a Docker command using `--network none`, `--read-only`, `--user 65534:65534`, `--cap-drop ALL`, and `--security-opt no-new-privileges`. It pins the Python image by digest. These are meaningful isolation controls for the generated test process.

They do not by themselves prove full isolation: the container shares the runner kernel; the artifact is handled by earlier runner steps; and termination of descendants after an external timeout must be tested. The workflow's writer job separately receives `COPILOT_GITHUB_TOKEN` to invoke Copilot; that secret must never cross into the verify job.

This is a source-level observation, not a claim that the negative tests below have passed.

## 2. Test execution rules

- Use disposable runner state and never test against the live trusted queue.
- Use synthetic, non-secret canary values only. Never print or collect actual secret values.
- Each test records source SHA, workflow revision, run ID, job, command, exit status, and observed postconditions.
- A test passes only when the stated postcondition is observed. Expected output embedded in a fixture is not evidence.
- Avoid persistent self-hosted runners and privileged follow-up jobs that execute candidate artifacts.
- Any test that requires changing workflow permissions, secrets, repository settings, or protected branches needs explicit owner authorization before implementation.

## 3. Prioritized negative tests

| ID | Priority | Adversarial probe | Required observation |
|---|---|---|---|
| E4-N01 | P0 | Handler returns a fabricated PASS with incorrect task/source/attempt identity | Trusted validator rejects it; no DONE or trusted state update |
| E4-N02 | P0 | Candidate attempts to edit queue and verification files | Candidate cannot reach writable trusted state; post-run trusted-state digest unchanged |
| E4-N03 | P0 | Replay a PASS from an earlier attempt or lease | Validator rejects stale identity; no DONE transition |
| E4-N04 | P0 | Change source input between request creation and execution | Pinned SHA/tree mismatch causes rejection |
| E4-N05 | P1 | Test path traversal, absolute paths, duplicate paths, and symlink parents in an artifact | Artifact rejected before any out-of-scope write |
| E4-N06 | P1 | Generated test reads a synthetic canary from environment | Canary is absent from the test container environment |
| E4-N07 | P1 | Generated test attempts an outbound network connection | Connection fails under the declared `--network none` policy |
| E4-N08 | P1 | Generated test attempts writes to the mounted source tree and root filesystem | Writes fail; disposable `/tmp` is the only intended writable location |
| E4-N09 | P1 | Generated test starts a child process that sleeps past the timeout | Container and descendants are no longer running after timeout handling completes |
| E4-N10 | P1 | Generated test emits oversized output or creates oversized files | Limits reject or terminate the run without trusted-state changes |
| E4-N11 | P1 | Artifact includes extra files or oversized JSON | Validation rejects it before execution |
| E4-N12 | P1 | Generated test attempts to access Docker socket or runner paths | No socket/runner filesystem mount is available inside the test container |
| E4-N13 | P1 | Writer job fails after obtaining its token | Token is not emitted to logs/artifacts; verify job receives no writer secret |
| E4-N14 | P2 | Re-run the workflow and submit an artifact from an earlier run | Run/task/source identity mismatch rejects the stale artifact |

## 4. Test details and cautions

### E4-N01: Forged PASS
Construct a fake handler/result in a unit test. Verify the acceptance layer does not trust a handler's status alone and requires the authoritative verification record to match the exact task, source, attempt, lease, and resulting tree. Assert that queue bytes and history remain unchanged on rejection.

### E4-N02: Queue mutation
Do not mount the real queue or the runner workspace writable into the candidate container. Use a disposable sentinel file representing trusted state. Attempt to overwrite it from the candidate process and compare its digest after execution. The desired architecture should make the state unreachable or read-only, not merely restore it afterward.

### E4-N07: Network policy
Test a local listener and an external address separately where feasible. Record the actual result. Do not infer network isolation from an environment variable or from the fact that the test process has no credentials.

### E4-N09: Descendant cleanup
Start a child process that records a marker only after the expected timeout. After the job reports timeout, check that the child is no longer alive and the marker was not created. The check must occur outside the process being timed out. Document any limitations of the runner/container mechanism.

### E4-N13: Secret boundary
The test should verify job configuration and the absence of secrets in the verify job, not retrieve or display actual secret values. Never use the actual Copilot token as a test canary.

## 5. Acceptance and evidence format

For each test retain a compact JSON record with:
- `test_id`
- `source_sha`
- `workflow_ref`
- `run_id` and `job_id`
- `input_digest`
- `expected_postcondition`
- `observed_result`
- `exit_code` and timeout state
- `evidence_artifact_digest`
- `review_status`

The record is itself untrusted until its origin and integrity are checked. Store no secrets or sensitive environment dumps.

## 6. Exit criteria

E4 must remain **BLOCKED / NOT PROVEN** until:
1. P0 tests pass on an exact SHA.
2. Applicable P1 tests pass in GitHub Actions.
3. Workflow permissions and secret boundaries are independently reviewed.
4. The exact process-tree and network behavior is demonstrated.
5. Trusted state remains unchanged after rejected hostile attempts.
6. An independent reviewer checks the evidence and records residual risks.

A passing test suite is not authorization to merge. The PR remains a draft until its review and CI evidence are complete.
