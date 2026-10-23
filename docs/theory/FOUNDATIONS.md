# Foundations

Working definitions of the concepts the project builds on. A definition here is the project's operational reading, not a summary of a field. Where a definition has no checked source, it says so.

Entry fields: `Definition`, `Not to be confused with`, `Sources`, `Project use`, `Claims`.

### CON-001 — Autopoiesis (engineering analogue)
- Definition: in the literature, a network of processes that continually produces and maintains the organization that constitutes it. In this project, only an engineering analogue: the system keeps a declared set of critical components and relations, detects perturbations that threaten them, proposes changes that restore or improve them, and checks that the relations needed for operation remain intact.
- Not to be confused with: self-modifying code. A program can rewrite its source without being autopoietic.
- Sources: SRC-001, SRC-002 (not checked). No primary source registered yet; see OQ-002.
- Project use: the analogue is taken from `RESEARCH_REVIEW.md` ("Conceptual distinctions", branch `docs/autopoiesis-core-architecture-baseline` at `c69452f`). It is a design input, not on `main`.
- Claims: CLM-002.

### CON-002 — Structural coupling and enaction
- Definition: ongoing interaction between a system and its environment, where action shapes what is observed next. For software this needs declared observations (test results, task outcomes, runtime signals) with recorded provenance, not only reading its own files.
- Not to be confused with: an internal feedback loop alone.
- Sources: SRC-003 (not checked).
- Project use: `ARCHITECTURE.md` §4.5 "Structural coupling membrane" (branch only).
- Claims: none yet.

### CON-003 — Evolutionary cycle
- Definition: the loop observe → detect a problem → form a candidate → test → verify independently → obtain authority bound to this change and parent state → execute within it → commit and check persistence → observe consequences.
- Not to be confused with: one step of the loop existing in code. Steps existing ≠ the cycle being implemented.
- Sources: SRC-004 (archive of variants with empirical evaluation; not checked). The cycle itself is a project decision recorded in `PROJECT_UNDERSTANDING.md` (project files, 2026-10-19), not in the repository.
- Project use: `AGENTS.md` rule 6; roadmap stages A3–A9.
- Claims: CLM-003, CLM-009.

### CON-004 — State and relations, Ψ = (X, R)
- Definition: the system's state is a set of elements (X) and typed relations between them (R), versioned as snapshots. Units, measurement and the semantic layer (which relation types exist and what follows from them) are not defined.
- Not to be confused with: the current task queue, which is what the core stores today (CLM-006).
- Sources: no external source. Origin is the earlier Gnosis-Core code and owner decisions.
- Project use: product goal in `AGENTS.md`; `ARCHITECTURE.md` §2 (branch only) lists what must be defined before X/R becomes a control signal.
- Claims: CLM-006, CLM-007. Open: OQ-001.

### CON-005 — Homeostasis and fitness
- Definition: homeostasis is the set of explicit safety and operating bounds; fitness ranks candidates inside those bounds.
- Not to be confused with: each other. A fitter candidate outside the bounds is not acceptable.
- Sources: no external source registered. Stated in `STATE_TRANSITION_CONTRACT.md` "Homeostasis is not fitness" (branch only).
- Project use: none on `main`.
- Claims: CLM-004. Open: OQ-005.

### CON-006 — Second-order cybernetics and the observer
- Definition: none yet. Named in the request that started this base (owner and GPT, 2026-10-23) as a foundation, but no definition, source or project use is recorded anywhere in the project.
- Sources: none registered.
- Claims: none yet. Open: OQ-003.

### CON-007 — Evidence and authority
- Definition: evidence (a test, a hash, green CI, an audit) shows what is true at an exact SHA; authority permits a change. Evidence never becomes authority by itself.
- Sources: project rule, no external source.
- Project use: `AGENTS.md` rules 1–3 and the evidence ladder.
- Claims: CLM-001, CLM-005, CLM-009.
