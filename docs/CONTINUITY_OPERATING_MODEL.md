# Continuity and interchangeable-agent operating model

**Status:** Proposal; not active repository policy until reviewed and merged by the owner.  
**Scope:** Development coordination and recovery. This document does not grant credentials, change permissions, enable unattended model calls, or authorize merges.

## Owner's operating goal

The project must remain resumable when any one model is unavailable or out of quota. The owner should normally ask for a report, not manually drive every next step. Claude is the preferred code-writing agent but is launched manually by the owner with a prepared batch. GPT may continue planning, reviewing, writing bounded changes, and using available repository tools when Claude is unavailable. No model is assumed to be continuously available.

## Canonical state and recovery

1. GitHub is canonical for repository content, branch refs, PRs, workflow runs, CI results, and artifacts.
2. AGENTS.md defines safety, evidence, review, merge, and reporting policy. This document does not override it.
3. TASKS.json defines tasks understood by the current deterministic core runner. It is not the whole software-development backlog.
4. PLAN.md is the human/agent development backlog and dependency map. It must not be treated as executable authority.
5. TASK_QUEUE.json, RESULTS.json, and QUEUE_RESTORE_PROVENANCE.json are generated/runtime state. Their existence or a status string is not proof by itself; validate the current artifact, source run, SHA, schema, and relevant CI.
6. docs/coordination/PROTOCOL.md is marked proposed. Do not treat it as active policy until the owner reviews and merges it.
7. Chat history, summaries, model memory, and agent reports are pointers for retrieval, not evidence of current repository state.

At the start of a resumed session, reconcile the current main SHA, open PR heads/bases, relevant CI run IDs and head SHAs, current task files, and unresolved architectural decisions. If sources disagree, stop the affected step and report RECONCILIATION REQUIRED.

## Roles

| Role | Default owner | Allowed work | Explicit boundary |
|---|---|---|---|
| Architecture and coordination | GPT in chat | Reconcile proposals, maintain backlog, define acceptance criteria, inspect evidence, prepare Claude work packets, review evidence | Chat availability is not a background worker or API entitlement |
| Main code implementation | Claude, manually launched by owner | Implement a bounded packet on a branch, add tests, run checks, open/update a PR, report exact SHA and CI | No self-merge; do not assume it will run when not launched or when quota is exhausted |
| Fallback implementation and review | GPT using tools actually available in the current session | Continue independent planning/review; make bounded branch/PR changes only when tool access and task scope permit | Never claim local execution, runtime proof, or a tool action that did not occur |
| Optional document/architecture analyst | Gemini, if owner enables an API/account and a reviewed adapter exists | Second opinion on documents, architecture contradictions, risk registers, test ideas | Not trusted authority; do not send secrets/private code without reviewing provider data terms |
| Optional fast diagnostics | Groq, if owner enables an API/account and a reviewed adapter exists | Short CI-log classification, test-case suggestions, structured summaries | Rate limits apply; not a security gate or autonomous repository writer by default |
| Deterministic verifier | GitHub Actions and repository tests | Execute specified checks, bind results to a commit, preserve logs/artifacts | Green CI proves only the checks actually run on that exact SHA |
| Queue dispatcher | Future repository-controlled mechanism | Select eligible tasks, persist checkpoints, bound retries/budget, stop safely, produce summaries | Must not call external models from trusted core, invent credentials, change workflow permissions, or merge |
| Owner | Human | Resolve policy/architecture decisions requiring authority; approve protected changes; merge reviewed PRs | Owner approval remains the final merge gate |

Gemini and Groq are optional providers, not prerequisites. Do not add either until a small evaluation demonstrates a useful quality/cost advantage and the integration can be isolated outside the trusted core. Provider adapters must be replaceable and fail closed on missing credentials, rate limits, malformed responses, and ambiguous state.

## Work packet and handoff contract

Every Claude batch or fallback implementation task must specify:

- Task ID, priority, dependencies, and one bounded objective.
- Starting repository, branch, and exact base SHA.
- In-scope and prohibited paths; no workflow, permission, secret, or repository-setting changes without explicit owner approval for that change.
- Acceptance criteria and required tests before coding.
- Resource/time/retry limits where applicable.
- Required output: changed files, branch/PR, exact head SHA, CI run ID and its head SHA/conclusion, test evidence, known limitations, and next task.
- Stop conditions: conflicting architecture decisions, stale base, unexpected file scope, missing permissions, failing safety invariant, or unverified evidence.

The next packet is prepared from the current GitHub state, not copied unchanged from an old chat. The owner should be able to paste one packet to launch Claude; the packet should not require the owner to manually sequence each subtask.

## Recovery and continuation rules

1. Before work, read the current queue/backlog and reconcile it against GitHub.
2. Choose the highest-priority task whose dependencies are satisfied and whose scope does not conflict with an open claim or PR.
3. If Claude is unavailable, continue only tasks that GPT's current tools can genuinely perform. Otherwise prepare a complete Claude packet and continue independent analysis/documentation.
4. Never silently mark a blocked task complete, reset a queue, or count a no-op as progress.
5. After any interruption, resume from the last validated GitHub state and artifact; do not rely on an unpersisted chat checkpoint.
6. Keep at most one active owner per overlapping file scope. Avoid duplicate work across agents.
7. When no safe task is executable, record the exact blocker and continue unrelated eligible work. Do not manufacture activity.
8. Produce a report using the required AGENTS.md format. Distinguish implemented, reachable, runtime-observed, persisted, audited, and CI-proven claims.

## Reporting and owner interruption budget

The normal user-facing update should be a concise report containing: current SHA; work completed; exact PR/CI evidence; proven/not proven; blockers; estimated progress explicitly labelled as an estimate; and the next recommended action. Interrupt the owner only for a required decision, permission, secret/account setup, conflicting architecture choice, or merge.

This document does not configure scheduled messages or guarantee that ChatGPT can send unsolicited notifications. Delivery automation is a separate capability to verify.

## Rollout gates

- **Gate 1 — Reconcile:** confirm live main, open PRs, queue files, current architecture review, and actual Claude launch path.
- **Gate 2 — Agree architecture:** resolve each recorded GPT/Claude disagreement; mark unresolved questions explicitly. Do not call the architecture final before that.
- **Gate 3 — Operational backlog:** keep PLAN.md in sync with the accepted architecture and TASKS.json's narrower deterministic task scope.
- **Gate 4 — Dispatcher design:** specify idempotency, single-writer/concurrency, retry caps, checkpoint restore, model/provider adapters, and fail-closed behavior before changing code or workflows.
- **Gate 5 — Safe implementation:** implement in small PRs; no auto-merge. Workflow, permissions, secret, and repository-setting changes require explicit owner approval for the specific change.
- **Gate 6 — Evidence:** prove each feature on exact SHAs with CI and, where claimed, runtime and persistence probes. A successful unit test is not proof of unattended autonomy.
