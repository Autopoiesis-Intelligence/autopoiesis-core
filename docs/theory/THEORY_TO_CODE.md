# Theory to code

How each claim reaches the repository. Every row names the rule or decision, the roadmap stage, the code, the tests and the evidence, with exact SHAs. A link that does not exist yet is `none yet`.

Evidence levels are those of `AGENTS.md`. A row describes what the evidence shows; it does not authorize the next step.

Entry fields: `Claim`, `Rule or decision`, `Stage`, `Code`, `Tests`, `Evidence`, `Not proven`.

### T2C-001 — Audit verdicts are evidence, not authority
- Claim: CLM-001
- Rule or decision: `AGENTS.md` rule 1 and "Review and audit".
- Stage: A8 (governed acceptance).
- Code: `autopoesis/audit_verdict.py` at `685c5a0`.
- Tests: at `685c5a0`, among others `tests/test_audit_verdict.py::test_acceptance_without_green_ci_is_not_ready_for_owner`, `tests/test_audit_verdict.py::test_stale_sha_verdict_does_not_count`, `tests/test_audit_verdict.py::test_wrong_author_is_rejected_even_with_a_matching_agent_line`.
- Evidence: CI_PROVEN for these tests at `685c5a0`, CI run 39488355792 (push to `main`, success).
- Not proven: that only the owner merges. That rests on the `main-protection` ruleset and on agents following `AGENTS.md`, not on this code. Unattended application of the labels is not proven (`AGENTS.md`, "Enforcement").

### T2C-002 — Stage separation in the task lifecycle
- Claim: CLM-003
- Rule or decision: `AGENTS.md` rule 6.
- Stage: A3 (closed lifecycle), A7 (independent verification).
- Code: on `main`, none yet. PR #33 (A3, open) proposes it.
- Tests: none yet on `main`.
- Evidence: DESIGN only on `main`.
- Not proven: that the stages are independent in practice; see OQ-006.

### T2C-003 — No-op is not progress
- Claim: CLM-005
- Rule or decision: `AGENTS.md` rule 5.
- Stage: A9 (persistent progress).
- Code: `autopoesis/core.py` at `685c5a0` rejects a no-op state change.
- Tests: `tests/test_core.py::test_noop_is_rejected` at `685c5a0`.
- Evidence: CI_PROVEN for that test at `685c5a0`, CI run 39488355792.
- Not proven: progress measured as accepted, independently verified changes. A9 is not implemented on `main`; PR #36 (open) covers leases and recovery only.

### T2C-004 — X/R as the product state
- Claim: CLM-007, CLM-006
- Rule or decision: owner decision 2026-10-19 in `AGENTS.md`.
- Stage: none yet. A0–A12 prove bounded autonomy over the task queue, not the X/R model.
- Code: none yet.
- Tests: none yet.
- Evidence: DESIGN only.
- Not proven: everything beyond the goal statement; see OQ-001.

### T2C-005 — Homeostasis before fitness
- Claim: CLM-004
- Rule or decision: none yet on `main`.
- Stage: none yet.
- Code: none on `main`. Branch `docs/autopoiesis-core-architecture-baseline` at `c69452f` has `autopoesis/viability.py` and `autopoesis/evaluation.py`, never merged.
- Tests: none on `main`.
- Evidence: DESIGN only.
- Not proven: see OQ-005.

### T2C-006 — Research autonomy versus change authority in A10–A12
- Claim: CLM-009
- Rule or decision: owner decision 2026-10-23 (OQ-009); `AGENTS.md` rules 1 and 6.
- Stage: A7, A8 (already state that evidence is not authority), A10–A12 (must test the boundary).
- Code: none yet on `main`.
- Tests: none yet. Proposed before implementation, each with the observable result:
  1. A selected candidate with a PASS whose patch targets the core, a test, a policy file or CI is refused; the queue file and the repository tree are byte-identical afterwards, and the refusal is a history event.
  2. A research-`ACCEPTED` hypothesis or a selector decision passed where authority is required is refused with a typed error; nothing is written.
  3. A run with no owner approval record for a core change stops before any write and reports why.
  4. A run inside its pre-authorized scope completes select → execute → verify without human input, and its history shows no approval step.
  5. Across an A11 trial, the report counts attempted out-of-scope writes and shows each one blocked; zero accepted without approval.
  6. A12: a capability expansion proposed by the system cannot be approved by the system; the expansion requires an owner approval record naming the policy version.
- Evidence: DESIGN only.
- Not proven: everything; the tests above do not exist yet. The roadmap text does not yet state criteria 1–3 and 6 explicitly (proposal in the PR).
