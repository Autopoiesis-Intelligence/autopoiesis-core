# Architecture reconciliation — GPT position after Claude review

**Date:** 2026-10-27  
**Status:** Working proposal only. Not an owner-approved architecture decision and not active policy.  
**Base main:** `4ae19f49f480246a2b42a3e9457190d43f03db6b`  
**Evidence note:** This document synthesizes the Claude architecture review and current repository policy. It does not substitute for rechecking every PR head, running comparative tests, an independent audit, or owner approval.

## Executive conclusion

GPT accepts Claude's strongest operational findings: stop adding parallel implementations, treat the current main as a bounded task runner rather than a proven self-developing system, use Git history as the authoritative accepted project history, and do not claim autonomous evolution without a real end-to-end runtime demonstration.

GPT does **not** accept the inference that Git alone represents the entire intended state `Ψ=(X,R)`. Git can be the canonical history of this software project and its accepted code/document changes. It is not, by itself, a complete semantic representation of arbitrary state-and-relation changes that the owner's product goal describes. The core must keep its domain model conceptually separate from the Git adapter.

No production code, workflow, permission, secret, repository setting, or main branch is changed by this proposal.

## Decisions that are already supported

1. **Goal:** The product goal is controlled change of state and relations `Ψ=(X,R)` within delegated authority. Code changes are one possible change, not the ultimate goal. This is stated in `AGENTS.md`; it is a goal, not an implementation claim.
2. **Evidence and authority remain separate.** CI success, hashes, test results, model output, and persisted artifacts are evidence; none independently authorizes a protected transition or merge.
3. **Human acceptance remains the gate.** No agent merges to main or changes repository security settings.
4. **No autonomy claim yet.** Main's CI success proves the relevant test suite passed on that SHA; it does not prove the whole system completed a real self-development loop.
5. **No parallel coordinators by default.** The two candidate orchestration lines must be compared and consolidated before further cycle features are added.
6. **Models are replaceable external workers.** GPT, Claude, Copilot, Gemini, Groq, or another provider must not become hidden sources of semantic authority. No additional model/API is required to continue architecture and repo work.
7. **History and recovery evidence must be SHA-bound.** Stale, mismatched, malformed or inconclusive evidence fails closed.

## Open architectural disagreements and proposed resolution

### A. What is the core?

**Claude concern:** Avoid importing a separate `Ψ` machine, instance model, and lineage system when Git already provides branches, commits and provenance.

**GPT position:** Reuse Git for source-control history, accepted code, branches, diffs and commit provenance. Do not equate these implementation mechanisms with the complete domain semantics of `Ψ=(X,R)`. A branch is not automatically a semantic instance; a commit is not automatically a valid domain transition. Those mappings require an explicit contract.

**Proposed resolution:** Define a small, provider-independent domain contract for candidate state, relations, invariants, evidence, eligibility, authorization, transition result and provenance. Use Git as the first persistence/transport adapter for software-project changes. Do not port the old Gnosis implementation wholesale or introduce a second persistent state engine until a demonstrated use case requires it.

### B. Where should accepted state live?

**Claude concern:** Actions artifacts plus restore logic have become a second state source and consumed disproportionate effort; accepted state should be in main.

**GPT position:** Agree that Git main is the authoritative accepted state for this repository. Artifacts may hold temporary run output or evidence, but must never silently override accepted state or authorize progress. This does not mean every future domain object must be encoded directly as source files.

**Proposed resolution:** For the first proven vertical slice, persist accepted project transitions through reviewed commits only. Treat run artifacts as disposable, bounded evidence/cache; restore may reconstruct diagnostics or a candidate run, never authoritative accepted state. Revisit non-Git durable storage only after the first complete cycle and with an explicit threat model and consistency contract.

### C. Which coordinator survives: Claude's `orchestrator.py` or GPT's `queue_cycle.py`?

**Current evidence from Claude's review:** Both lines share lifecycle/selection/lease concepts, while the coordinator differs. Claude recommends choosing by comparative tests and smaller implementation volume, and explicitly avoids voting for the line it authored.

**Proposed resolution:** Do not choose by author, age, PR count, or a green isolated CI run. Create a read-only comparison matrix against the same required behaviors:
- deterministic single-task selection;
- closed task lifecycle and attempt-bound evidence;
- bounded execution and output;
- timeout/refusal/stop behavior;
- stale-state and malformed-evidence rejection;
- exact source snapshot binding;
- recovery after interruption without duplicate or false completion;
- no privileged side effects before authorization;
- tests that reproduce known cross-PR schema incompatibilities.

Select one coordinator only after tests run against exact candidate SHAs. Prefer the smaller design only if it meets the same acceptance contract. Until then, neither line is the canonical design.

### D. How much audit history is needed?

**Claude concern:** Repeating the full old-repository audit and September chronology is unnecessary.

**GPT position:** Accept the existing ecosystem audit and cleanup records as historical inputs, subject to their exact source SHA and scope. Do not rerun broad audits without a concrete unresolved question.

**Proposed resolution:** Keep a short provenance/borrowing register: source repository and SHA, specific concept reused, reason, known failure/risk, and whether code was copied (currently the review says no old-repository code was copied). Reopen a historical audit only when a specific design dependency cannot be resolved from existing evidence.

### E. How should evidence be reported?

Adopt Claude's compact report format for routine status: **highest proven evidence level + exact SHA + CI/runtime run ID + unresolved blocker**. Preserve the full evidence ladder in audit documents. Never promote claims from CI_PROVEN to RUNTIME, PERSISTED, AUDITED or end-to-end autonomy without their own evidence.

## Immediate stabilization plan (no merges authorized)

### S0 — Freeze new feature branches and inventory
- Do not create more feature PRs while the open-PR limit/process is unresolved.
- Record each open PR's base SHA, head SHA, changed files, dependencies, CI/runtime evidence, owner/agent, and whether it belongs to the Claude or GPT coordinator line.
- Confirm the repository's actual open-PR rule and scope from current `AGENTS.md`; do not infer whether the limit is per-agent or global.

### S1 — Establish the comparison contract
- Write a small, behavior-based acceptance matrix from `AGENTS.md`, the roadmap spec, and known regression reports.
- Identify incompatible state schemas and dependencies between PRs.
- Run no destructive cleanup and close no implementation PR automatically.

### S2 — Compare the two coordinator candidates
- Pin both exact heads and record CI runs against those exact heads.
- Run the same targeted and regression tests.
- Request an independent review where available; if unavailable, report the gap rather than calling the result independent.
- Recommend one line, list rejected alternatives and evidence, and ask the owner before any merge or bulk closure.

### S3 — First real vertical slice
The minimum successful demonstration must show: a real task is selected; a candidate change is generated; execution is bounded; a test fails on the base or an explicit task acceptance criterion is evaluated; the candidate is verified; evidence is bound to the exact source and attempt; a human-authorized change is accepted; the accepted state survives as a Git commit; and the next run reads that accepted state. A synthetic fixture or unit-test-only run does not satisfy this gate.

### S4 — Only then consider unattended trials
Unattended scheduling, automatic PR creation, model-provider expansion, and any privilege changes remain separate decisions. They require an explicit threat model, permissions review, resource limits, emergency stop, and observable runtime evidence. No automatic merge.

## Stop conditions

Stop and report BLOCKED if:
- candidate branches are based on stale or incompatible source snapshots;
- a test's evidence cannot be bound to the exact source and attempt;
- two components claim authority over the same transition;
- a recovery path can turn missing evidence into success or an empty queue;
- execution of generated code has broader filesystem/network/credential access than explicitly approved;
- required independent review is unavailable but the decision would otherwise be represented as independently audited.

## Owner decisions still required

1. Confirm the semantic boundary: Git is canonical for accepted repository history, while `Ψ=(X,R)` remains the domain-level goal rather than a synonym for Git objects.
2. Approve the policy that artifacts are non-authoritative and cannot restore accepted state.
3. After the comparative matrix, approve which coordinator line is retained and the disposition of dependent PRs.
4. Approve any future unattended runtime or permission change separately.

Until these decisions and the runtime gate are resolved, the architecture is **proposed / partially supported, not finalized**.
