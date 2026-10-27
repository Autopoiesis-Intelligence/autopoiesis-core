# Development plan — Autopoiesis Core

**Status:** Working proposal; owner review required.  
**Canonical code state:** GitHub refs and exact SHAs, not this file.  
**Rule:** No task may weaken AGENTS.md, auto-merge, or modify workflows/permissions/secrets/repository settings without explicit owner approval for that specific change.

## Operating goal

Build a minimal, bounded system that evolves project state and relations Ψ=(X,R), with code changes as one possible state change. Keep model providers outside the trusted core and interchangeable. The project must remain resumable when Claude or another model is unavailable.

## Queue

### P0 — Reconcile current evidence and architecture
- **Status:** READY FOR INVESTIGATION
- Re-read current main, all open PR heads/bases, relevant CI runs, and current architecture review artifacts.
- Recover the GPT proposal and Claude's dated review/consensus matrix from GitHub or user-provided project files; do not recreate missing details from memory.
- Resolve every recorded disagreement individually. For each: GPT position, Claude position, owner decision if known, evidence, chosen rule, consequences, and remaining uncertainty.
- Reconcile PR #66's current status and exact head with the current main. Do not treat prior runtime evidence as proof for a new SHA.
- **Acceptance:** an architecture decision record identifies agreed decisions and unresolved questions; each live code/CI claim points to exact SHA/run evidence.

### P1 — Establish durable project continuity
- **Status:** PROPOSED
- Keep this PLAN.md as the development backlog, separate from TASKS.json, which only contains deterministic core-runner task types.
- Maintain a concise checkpoint in reviewed project files: current baseline SHA, active PRs, accepted decisions, unresolved decisions, current task, blockers, and next task.
- Use GitHub as canonical state; never treat chat history, model memory, or a status label alone as proof.
- **Acceptance:** a new session can reconstruct the next safe action from repository state and linked evidence without asking the owner to restate project history.

### P2 — Define a replaceable executor contract
- **Status:** PROPOSED
- Specify the input snapshot/base SHA, allowed paths, output patch/artifacts, tests, resource limits, and structured result for each executor.
- Claude remains the preferred code writer, manually launched by the owner in bounded batches.
- GPT continues work when its current connected tools support it; otherwise it prepares the next complete Claude packet.
- Gemini/Groq remain optional until evaluated and connected through a replaceable adapter outside the trusted core.
- **Acceptance:** executor identity can change without changing the core task schema or granting a new executor additional authority.

### P3 — Design a safe dispatcher and checkpoint recovery
- **Status:** BLOCKED ON P0/P2 DESIGN
- Specify eligibility, deterministic priority, dependency handling, single-writer/concurrency, idempotency, retry/attempt caps, budget stops, resume behavior, and blocked-task reporting.
- Distinguish backlog selection from authorization, execution, verification, acceptance, commit, and merge.
- **Acceptance:** written state machine and adversarial tests cover duplicate dispatch, stale checkpoints, malformed state, interrupted writes, concurrent updates, quota exhaustion, provider timeout, invalid provider output, and fail-closed recovery.

### P4 — Implement in bounded PRs
- **Status:** NOT STARTED UNDER THIS PLAN
- Implement only after design review; one bounded change per PR with tests.
- Preserve current branch protection and owner-only merge.
- Workflow/permission/secret/repository-setting changes require explicit owner approval for the specific change.
- **Acceptance:** green CI on the exact PR head, independent review, and runtime/persistence evidence where the claim requires it.

### P5 — Evaluate optional model providers
- **Status:** DEFERRED
- Compare Gemini and Groq on a small, non-sensitive benchmark: CI-log diagnosis, architecture contradiction detection, and test-case generation.
- Record correctness, reviewer corrections, latency, available quota, data terms, and setup burden. Do not assume unlimited free usage.
- **Acceptance:** each provider receives only tasks where it demonstrates value; no secrets or private code are sent without an explicit data-handling decision.

### P6 — Reporting and continuation
- **Status:** PROPOSED
- Standard report: BEFORE → ACTION → AFTER → RESULT → PROVEN/NOT PROVEN → REJECTED DIRECTIONS → NEXT SEQ.
- Report exact baseline/head SHA, PR URL, CI run ID/conclusion/head SHA, runtime and persistence evidence, blockers, and estimates labelled as estimates.
- Automate delivery only after confirming a real supported scheduler and destination; do not claim unsolicited background notifications without evidence.
- **Acceptance:** every completed work unit leaves one recoverable next step and no requirement for the owner to send repeated "Далее" prompts.

## Explicit non-goals for this phase

- No changes to main directly.
- No auto-merge.
- No new paid service, API spend, or mandatory external model.
- No provider calls or credentials inside the trusted core.
- No workflow, permission, secret, or repository-setting changes before the owner approves that specific change.
- No claim of full autonomy based only on CI, synthetic tests, or a green run.

## Next action

Complete P0: retrieve the actual GPT architecture proposal and Claude review, reconcile them against the current repository and open PRs, and publish a decision record in a reviewable PR.
