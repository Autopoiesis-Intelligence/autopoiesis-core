# Open questions

Contradictions, untested assumptions and decisions that are still open. An entry is closed only with a reason, a date and a link to what closed it; closed entries stay in place.

Entry fields: `Question`, `Why it matters`, `Options`, `Who decides`, `Blocks`, `Status`.

### OQ-001 — What is the exact form of X/R in autopoiesis-core?
- Question: which elements and relation types exist, what they mean, how they are measured, and how a candidate is checked against them.
- Why it matters: the product goal (CLM-007) cannot be tested until this is defined; today the core stores a task queue (CLM-006).
- Options: port the Gnosis-Core model; define a smaller model for the queue first; defer until A9.
- Who decides: the owner (`PROJECT_UNDERSTANDING.md`, "Open questions").
- Blocks: T2C-004, CLM-004.
- Status: UNRESOLVED

### OQ-002 — Which primary sources define autopoiesis for this project?
- Question: no primary source on autopoiesis is registered; the seed sources are reviews and second-hand summaries.
- Why it matters: CON-001 and CLM-002 rest on summaries nobody has checked.
- Options: register primary sources with exact bibliographic data after reading them; keep only reviews.
- Who decides: GPT proposes sources with exact references; Claude checks them against the claim.
- Blocks: CLM-002 becoming SUPPORTED.
- Status: UNRESOLVED

### OQ-003 — Is second-order cybernetics a foundation of the project?
- Question: it is named as a foundation in the request that started this base, but no definition, source or project use is recorded (CON-006).
- Why it matters: a foundation without a definition cannot be used to check a design decision.
- Options: define it with sources and link it to a claim; drop it from the foundations.
- Who decides: the owner and GPT.
- Blocks: CON-006.
- Status: UNRESOLVED

### OQ-004 — `ACCEPTED` means two different things
- Question: `ACCEPTED` is both a knowledge status here and an audit verdict in `AGENTS.md`.
- Why it matters: a reader can take an accepted design claim for an accepted audit, or the reverse. The verdict parser is not affected: it only reads a `Verdict:` block that opens a PR comment.
- Options: keep the word and always say "knowledge status" or "verdict"; rename the knowledge status (for example `ADOPTED`).
- Who decides: the owner.
- Blocks: nothing; a naming risk.
- Status: UNRESOLVED

### OQ-005 — Should homeostasis and fitness be separate decisions on `main`?
- Question: the split exists only in an unmerged design document and prototype code (T2C-005).
- Why it matters: it decides how candidates are evaluated once evaluation exists.
- Options: adopt with a roadmap stage; leave as a design input until X/R exists.
- Who decides: the owner, after OQ-001.
- Blocks: CLM-004.
- Status: UNRESOLVED

### OQ-006 — How independent is "independent verification" with one shared account?
- Question: all agents use one GitHub account; verdicts are told apart only by the auditor app id. Do the generator and the verifier share assumptions, prompts or context?
- Why it matters: CLM-003 predicts a lower error rate only if the checks are independent.
- Options: measure disagreement between Codex reviews and Claude's own checks over time; require the verifier to use inputs the executor did not produce.
- Who decides: GPT and the owner propose a check; Claude implements tests.
- Blocks: CLM-003 moving beyond HYPOTHESIZED.
- Status: UNRESOLVED

### OQ-007 — Should the architecture baseline documents move to `main`?
- Question: `RESEARCH_REVIEW.md`, `ARCHITECTURE.md`, `STATE_TRANSITION_CONTRACT.md` and `IMPLEMENTATION_GAP_ANALYSIS.md` exist only on branch `docs/autopoiesis-core-architecture-baseline` (draft PR #3), together with unmerged code.
- Why it matters: this base cites them, but citations to an unmerged branch can change or disappear.
- Options: move the documents alone to `docs/` in a separate PR; fold their content into this base entry by entry; keep citing the branch at `c69452f`.
- Who decides: the owner.
- Blocks: nothing; it affects how stable the citations are.
- Status: UNRESOLVED

### OQ-008 — Which claims registry is canonical?
- Question: three registries already exist outside this repository: 183 claim records `C-0001`…`C-0183` in Gnosis-Memory `research_machine/records/` at `7a77642`, `CLAIMS.md` and the record schema in `research/INDEX.md` in Gnosis at `935233c`, and Gnosis-Knowledge at `13beebb`, whose README describes this same role but holds no content.
- Why it matters: a fourth parallel registry repeats the drift that stalled Gnosis. All 183 Gnosis-Memory records are `FORMALIZED`, `RESEARCH_ONLY` and have `evidence: []`; their sources are lines of an internal chat-derived file (`AI_CONTEXT.md`), not external literature.
- Options: keep this folder as the core's small working base and cite outside records as `Gnosis-Memory:C-0025@7a77642` only when a task needs one (recommended); import selected records with a re-check; move the base to Gnosis-Knowledge.
- Who decides: the owner.
- Blocks: importing outside records.
- Status: ACCEPTED
- Decision (owner, 2026-10-23): this folder stays the core's compact working theory base. No parallel registry, no bulk copy of the 183 records. Rules: every significant claim has a stable ID, status, source and scope; an outside record such as `Gnosis-Memory:C-0025` may be cited only with the exact version or SHA it resolves to, and its `FORMALIZED` status is not evidence; primary sources, formal definitions, mathematical proofs, test results and architectural hypotheses are kept apart, and no status is raised without matching evidence. Gnosis-Knowledge is not filled by copying: its role is OQ-010. Recorded as CLM-008.

### OQ-009 — Is human approval part of the target loop or outside it?
- Question: Gnosis `PHILOSOPHY.md` and `CLAIMS.md` §E (at `935233c`) reject a permanent external selector or human confirmation as a necessary part of the endogenous core, and Gnosis-Core `docs/MASTER_SPEC.md` §2–3 (at `a209a96`) says the test is not an external operator. Gnosis-Memory `FINAL_PRODUCT_TZ_R2.md` §17 (at `7a77642`) keeps human governance at promotion boundaries. In this repository only the owner merges (`AGENTS.md`).
- Why it matters: it decides what A10–A12 must prove, and whether an external auditor is a permanent part of the product or scaffolding for the development loop.
- Options: endogenous selection inside the core with human governance only at promotion to the outside world; human approval as a permanent stage; human approval removed after a proven trial. SRC-007 (not checked) argues that a policy judging itself is a risk, which counts against full endogeneity.
- Who decides: the owner.
- Blocks: acceptance criteria for A10–A12.
- Status: ACCEPTED
- Decision (owner, 2026-10-23): a human is not a required selector of the internal research and learning loop, but internal selection, research acceptance of a hypothesis and authority to change the system are different operations. Changing the core itself stays behind a controlled commit boundary with owner approval until safety and authority are separately proven. No auto-merge, and no new agent authority through theory documents. A10–A12 must test these boundaries. Recorded as CLM-009; criteria-to-test mapping in T2C-006.

### OQ-010 — What is Gnosis-Knowledge for?
- Question: the role and responsibility boundaries of Gnosis-Knowledge relative to Gnosis-Memory, Gnosis `CLAIMS.md` and this folder.
- Why it matters: OQ-008 forbids filling it by copying; until its role is defined it stays empty.
- Options: a public, cross-project knowledge layer that cites this folder and Gnosis-Memory by SHA; retire it; merge its role into Gnosis-Memory.
- Who decides: the owner.
- Blocks: any content in Gnosis-Knowledge.
- Status: UNRESOLVED

### OQ-011 — What do the Lean files in Gnosis prove?
- Question: Gnosis `formal/` at `935233c` has 18 Lean 4 files with 49 theorems and no `sorry` or `axiom`, but no `lean-toolchain`, no `lakefile` and no CI step, so the Lean version is not pinned and no build was ever recorded. Several invariants are placeholders defined as `True` (`formal/ConcreteInvariant.lean` lines 13–16, `formal/Sigma.lean` line 15, `formal/CanonicalBoundary.lean` line 15), so theorems about them hold trivially.
- Why it matters: until a pinned build succeeds they are not checked proofs; even then, a theorem over a `True` placeholder says nothing about the code.
- Options: pin a toolchain and add a build-only CI job in Gnosis (needs the owner's approval for a workflow change in that repository); replace placeholders with real definitions before citing any theorem.
- Who decides: the owner for the CI change; Claude can run the build once a Lean toolchain host is reachable.
- Blocks: citing any Gnosis theorem as a proof.
- Status: UNRESOLVED
