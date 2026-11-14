# Architecture Decision Register

**Status:** Initial register, 2026-11-14. Decisions here describe the proposed target. Operational rules in AGENTS.md remain authoritative.

| ID | Decision | Status | Rationale / consequence |
|---|---|---|---|
| ADR-001 | Product goal is a universal bounded self-evolving system, not a software-project-only agent | ACCEPTED | Matches owner decision in AGENTS.md; software is the first domain |
| ADR-002 | Preserve the foundational domain model Ψ=(X,R) | ACCEPTED | State and relations remain the core abstraction |
| ADR-003 | History is append-oriented evidence; memory is a derived, versioned projection | PROPOSED | Prevents summaries and learned patterns from becoming authority or rewriting history |
| ADR-004 | Keep trusted kernel deterministic, small and free of network, credentials and LLM calls | ACCEPTED | Preserves existing repository policy |
| ADR-005 | Put provider, GitHub, CI, storage, scheduler and execution specifics behind adapters | ACCEPTED | Makes the core portable and limits trusted code |
| ADR-006 | Separate proposal, selection, verification, authorization, execution, commit and merge | ACCEPTED | Prevents evidence or status from implying authority |
| ADR-007 | Evidence dimensions are independent marks, not a mandatory linear pipeline | ACCEPTED | A CI check may precede runtime; report exactly what each check proves |
| ADR-008 | Task queue is a runtime coordination mechanism, not the evolution engine itself | ACCEPTED | Queue status does not prove learning, autonomy or progress |
| ADR-009 | Keep autopoesis/ package name during this restructuring | ACCEPTED | Rename is explicitly a separate pending owner decision |
| ADR-010 | Clone/fork/lineage/federation remain target capabilities, implemented after core identity and authority contracts | PROPOSED | Preserve original direction without prematurely multiplying trust boundaries |
| ADR-011 | Goal generation may be internal, but goal proposal does not authorize action | PROPOSED | Preserves endogenous evolution without hidden authority |
| ADR-012 | Memory and accepted knowledge must retain epistemic status and source provenance | PROPOSED | Prevents hypotheses or rejected claims from silently becoming facts |
| ADR-013 | A candidate transition declares parent state, affected relations, expected effects, risk, bounds and acceptance criteria | PROPOSED | Enables reproducible comparison and independent verification |
| ADR-014 | Self-modification is a late capability gated by bounded generation, execution, verification, governance and rollback | ACCEPTED | Avoids treating code generation as proof of self-improvement |

## Unresolved questions

1. **State identity and granularity:** Is the canonical state a whole graph snapshot, a set of versioned entities/relations, or both with a defined projection?
2. **History semantics:** Which events are immutable facts, and which are mutable indexes or projections?
3. **Memory learning:** How are patterns promoted, challenged, decayed or superseded without losing original evidence?
4. **Goal formation:** What objective function or policy constrains internally proposed goals, and how are conflicts resolved?
5. **Selection:** Which parts must be deterministic, and where may probabilistic ranking be used?
6. **Authorization trust:** What threat model, issuer identity and cryptographic mechanism are required for grants? A JSON field supplied by an executor is not trusted provenance.
7. **Execution isolation:** Which sandbox guarantees can be enforced in the current GitHub Actions/local environment, and which remain explicit limitations?
8. **Federation consistency:** How are divergent clone histories reconciled without transferring authority or losing lineage?
9. **Domain modules:** What is the minimal contract for a non-software domain, and how are domain-specific invariants registered?
10. **Progress measurement:** What measurable outcome demonstrates improvement rather than task throughput or successful execution?

## Rejected shortcuts

- Treating queue completion as evolution.
- Treating green CI as proof of runtime, persistence or autonomy.
- Treating a memory summary as canonical evidence.
- Treating a model's proposal as selection authority.
- Treating a PASS record as permission to execute or merge.
- Putting hidden clocks, global operators, provider clients or arbitrary code execution in the kernel.
- Building federation before identity, provenance, authority and conflict rules.
- Rewriting or renaming all existing modules in one migration.

## Change control

Each decision change must include: prior status, new status, reason, affected contracts/modules, migration impact and evidence. An unresolved item must not be silently treated as accepted.
