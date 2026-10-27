# E4.8 — Trust-boundary map for the existing GitHub Actions flow

Audit date: 2026-10-27
Audited base: `main` at `4ae19f49f480246a2b42a3e9457190d43f03db6b`
Related implementation proposal: PR #65
Status: source review only; no hostile runtime experiment performed.

## Trust zones

### Zone A — proposal writer job (token present)

`.github/workflows/copilot-test-writer.yml`, job `write`, invokes Copilot CLI with `COPILOT_GITHUB_TOKEN` in the process environment. The prompt limits tools and forbids shell/network/external tools, but prompt text is not a security boundary. Repository source and tests are input data and may contain adversarial instructions. The workflow must not treat model compliance as isolation.

Controls observed in source:
- workflow-level `contents: read`;
- checkout uses `persist-credentials: false`;
- supported source paths are allowlisted;
- generated response is parsed by `autopoesis.copilot_writer` and uploaded as an artifact;
- no push or PR creation is performed by this workflow.

Open questions / residual risk:
- establish whether the CLI or any invoked helper can expose the token to model-visible content, logs, diagnostics, or generated artifacts;
- redaction of stderr is a mitigation, not proof that all channels are secret-safe;
- ensure the token is narrowly scoped and revoke/rotate if disclosure is suspected.

### Zone B — proposal validation and artifact handoff

The writer job validates a response into `copilot-test-output/artifact.json`. The verify job downloads that artifact and applies it to a disposable workspace. Treat the artifact as untrusted input even though it was uploaded by a prior job in the same workflow.

Required properties:
- validate schema, path, size, and digest before touching the workspace;
- bind artifact to workflow run ID, source SHA, task ID, and target path in trusted workflow metadata;
- reject stale artifacts from any other run or source revision;
- never execute artifact content in the token-bearing job.

Source-level review does not prove these properties end-to-end; verify the implementation and tests for each explicitly.

### Zone C — test execution job (no token permissions)

The `verify` job declares `permissions: {}` and runs the proposed test in a Docker container using a digest-pinned Python image, `--network none`, `--read-only`, `--cap-drop ALL`, `no-new-privileges`, a non-root UID, and a read-only workspace mount. These are meaningful defense-in-depth controls.

They do not prove complete containment: the container shares the runner kernel, and Docker is invoked by a shell step on the runner. The workflow currently pipes container output through `tee` into a runner-host file; source inspection does not show a byte cap on this output stream. A hostile generated test could therefore produce excessive output during the bounded run and consume runner disk. Add a bounded-output capture that continues draining or terminates the container safely, plus tests for output flooding and descendant processes after timeout. Also test archive/artifact parsing and access to Docker socket/runner paths. The workflow log is not itself an independent trust attestation.

### Zone D — queue acceptance and DONE transition

The queue is local persistent state. A `VERIFICATION_RECORDED` event is data, not proof of authority. A local caller can supply a status string unless a trusted acceptance boundary independently validates it. The proposed attempt-binding change only rejects stale-attempt evidence; it does not establish a trusted producer or source-SHA provenance.

## Minimum acceptance contract

Before calling a task `DONE`, the trusted coordinator must establish all of the following:

1. The task ID resolves to exactly one current queue item.
2. The attempt ID is current and was issued by the coordinator.
3. The source SHA is the immutable revision actually checked out by the execution job.
4. The workflow run/job identity belongs to the expected workflow and repository.
5. The result artifact came from that run, has a valid schema and digest, and cannot be replayed across tasks, attempts, or SHAs.
6. The verifier result is produced by trusted code outside the untrusted test process and is independently checked before queue mutation.
7. Negative tests show stale, forged, cross-task, cross-attempt, and cross-SHA evidence is rejected.

Caller-provided fields alone do not satisfy items 2–6; they must be compared against trusted workflow/coordinator state.

## Next sequence

1. Inspect `autopoesis.copilot_writer` and `autopoesis.executor` for artifact schema, path/size validation, and process timeout semantics.
2. Add deterministic unit tests for queue attempt binding, after confirming the test fixture and status-transition invariants.
3. Add workflow-level provenance binding using trusted GitHub context; do not expose a write token to the verify job.
4. Add adversarial runtime probes on ephemeral runners and preserve run ID, exact SHA, job logs, and artifact digest as evidence.

**E4 remains BLOCKED / NOT PROVEN.** This document is a threat-boundary map, not proof of runtime isolation.
