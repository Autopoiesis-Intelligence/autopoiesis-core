# Claims

Registry of significant claims. Status vocabulary and claim kinds are defined in [INDEX.md](INDEX.md). A status says what kind of knowledge the claim is; it never authorizes work.

Entry fields: `Kind`, `Status`, `Claim`, `Grounds`, `Counterarguments`, `Alternatives` (design claims), `Risks` (design claims), `How to check`, `Links`, `History`.

### CLM-001 — Evidence is not authority
- Kind: design
- Status: ACCEPTED
- Claim: a passing test, a hash, green CI or an audit verdict never by itself authorizes a change to the core, a merge or a release.
- Grounds: `AGENTS.md` rule 1 on `main` at `685c5a0`.
- Counterarguments: requiring separate authority slows every change and keeps the owner in the loop, which limits autonomy.
- Alternatives: merge automatically on green CI plus an accepted audit. Not adopted.
- Risks: owner availability becomes the bottleneck (see the five-PR limit in `docs/PLAN.md`, PR #35).
- How to check: T2C-001.
- Links: CON-007, T2C-001.
- History: 2026-10-23 recorded from `AGENTS.md` (CL-016).

### CLM-002 — Autopoiesis is not self-modifying code
- Kind: scientific
- Status: HYPOTHESIZED
- Claim: biological autopoiesis concerns a self-producing network of processes; self-modifying code is neither necessary nor sufficient for it. The project therefore claims only an engineering analogue (CON-001), never biological equivalence.
- Grounds: second-hand summaries of SRC-001 and SRC-002 in `RESEARCH_REVIEW.md`. Status stays HYPOTHESIZED until those sources, or a primary source (OQ-002), are read; then it can become SUPPORTED.
- Counterarguments: none recorded yet.
- How to check: read SRC-001, SRC-002 and a primary source; record the supporting sections in SOURCES.md.
- Links: CON-001, OQ-002.
- History: 2026-10-23 recorded (CL-016).

### CLM-003 — Separating the stages lowers the risk of accepting wrong changes
- Kind: engineering
- Status: HYPOTHESIZED
- Claim: separating candidate generation, testing, selection and independent verification lowers the risk of accepting an erroneous change.
- Grounds: proposed by GPT (owner's message, 2026-10-23) as an example entry. Related sources, not checked: SRC-004, SRC-005, SRC-007, SRC-008.
- Counterarguments: separate stages are not independent checks by themselves; a shared wrong assumption can pass every stage. A verifier that repeats the generator's reasoning adds no independence.
- How to check: tests for verification bypass, stale results, races and illegal queue transitions; contracts between stages that the verifier cannot satisfy by copying the executor's result.
- Links: CON-003, T2C-002, OQ-006.
- History: 2026-10-23 recorded from the owner's message (CL-016).

### CLM-004 — Homeostasis and fitness are separate decisions
- Kind: design
- Status: HYPOTHESIZED
- Claim: safety and operating bounds are checked before, and separately from, ranking candidates by fitness.
- Grounds: `STATE_TRANSITION_CONTRACT.md` "Homeostasis is not fitness" on branch `docs/autopoiesis-core-architecture-baseline` at `c69452f`. Not on `main`; no owner decision recorded.
- Counterarguments: none recorded yet.
- Alternatives: one combined objective with penalties for unsafe states.
- Risks: without measured X/R there is nothing to bound yet, so the split may stay theoretical.
- How to check: none yet; needs OQ-001 and OQ-005 first.
- Links: CON-005, T2C-005, OQ-005.
- History: 2026-10-23 recorded (CL-016).

### CLM-005 — Progress means accepted, independently verified changes
- Kind: design
- Status: ACCEPTED
- Claim: progress is counted only as accepted, independently verified changes, not as task count, PASS count, queue status or a no-op.
- Grounds: `AGENTS.md` rule 5 and `docs/AUTONOMY_ROADMAP_SPEC.md` A9 on `main` at `685c5a0`. Related, not checked: SRC-006 (endpoint scores hide regressions), SRC-007 (an evolving policy can influence its own evaluator).
- Counterarguments: a strict count can hide useful partial work, such as a correct rejection.
- Alternatives: count benchmark scores or completed tasks. Not adopted.
- Risks: verification that is not truly independent makes the count misleading (CLM-003).
- How to check: T2C-003.
- Links: CON-007, T2C-003.
- History: 2026-10-23 recorded (CL-016).

### CLM-006 — The core stores a task queue, not X/R
- Kind: engineering
- Status: OBSERVED
- Claim: at `685c5a0` the persisted state of autopoiesis-core is a JSON task queue (`autopoesis/task_queue.py`); no module represents elements and relations (X/R).
- Grounds: file tree of `main` at `685c5a0`, read on 2026-10-23.
- Counterarguments: none.
- How to check: list `autopoesis/` at the current `main` head.
- Links: CON-004, T2C-004.
- History: 2026-10-23 observed (CL-016).

### CLM-007 — The product changes its own state and relations
- Kind: design
- Status: ACCEPTED
- Claim: the product goal is that the system changes its own state and relations, Ψ = (X, R), within delegated authority; code changes are one kind of change. This is a goal, not a proven property.
- Grounds: owner decision 2026-10-19, recorded in `AGENTS.md` ("What this repository is") on `main` at `685c5a0`.
- Counterarguments: without an exact X/R form the goal cannot be tested.
- Alternatives: limit the product to code changes. Not adopted by the owner.
- Risks: claiming progress toward the goal before X/R exists in the core (CLM-006).
- How to check: none yet; depends on OQ-001.
- Links: CON-004, T2C-004, OQ-001.
- History: 2026-10-23 recorded (CL-016).

### CLM-008 — One compact theory base, outside records cited by version
- Kind: design
- Status: ACCEPTED
- Claim: `docs/theory` is the core's only working theory base. Records in other repositories are cited by ID and exact version, never copied in bulk, and their own status is not evidence here.
- Grounds: owner decision 2026-10-23 on OQ-008.
- Counterarguments: citing outside records keeps them in a separate history that can drift or disappear.
- Alternatives: import all 183 Gnosis-Memory records; move the base to Gnosis-Knowledge. Not adopted.
- Risks: a cited SHA can become unreachable; the base can still grow too large if entries are added without a task.
- How to check: `tests/test_theory_docs.py` checks IDs and links; a reviewer checks that each outside citation names a SHA.
- Links: OQ-008, OQ-010.
- History: 2026-10-23 recorded (CL-016).

### CLM-009 — Autonomous research is not authority to change the core
- Kind: design
- Status: ACCEPTED
- Claim: the core may form candidates, run permitted checks, compare results and choose its next research step without a human selector. Internal selection, a research `ACCEPTED`, a PASS or a selector decision never grants authority to execute a change. Changes to the core itself pass a controlled commit boundary with owner approval until safety and authority are separately proven.
- Grounds: owner decision 2026-10-23 on OQ-009; consistent with `AGENTS.md` rules 1 and 6 and "Agents do not merge their own PRs".
- Counterarguments: Gnosis `PHILOSOPHY.md` treats endogenous closure as fundamental; a permanent approval gate can be read as an external selector. The decision answers this by separating selection (internal) from authority (governed).
- Alternatives: human approval of every research step; fully endogenous change after a trial. Not adopted.
- Risks: the line between a research action and a state change must be enforced in code, or "research" becomes a path around the commit boundary.
- How to check: T2C-006.
- Links: CON-003, CON-007, OQ-009, T2C-006.
- History: 2026-10-23 recorded (CL-016).
