# Sources

Registry of external sources. Each entry says what the source is used for, where in it the support is, its limits, and whether anyone has checked it.

Seed entries are copied from `RESEARCH_REVIEW.md` on branch `docs/autopoiesis-core-architecture-baseline` at `c69452f` (draft PR #3, research snapshot 2026-10-18). Only titles and URLs given there are recorded; authors, pages and sections are left as `not recorded` until someone reads the source. The rest of that review's sources are not registered yet: add them when a claim needs them.

**Check status for all seed entries:** not opened. In the session that wrote this skeleton (CL-016, 2026-10-23), the network blocked arxiv.org, doi.org and the other source hosts, so no URL, title or finding below was confirmed. The `Supports` lines repeat the review's summary and are second-hand.

Entry fields: `Reference`, `URL`, `Recorded in`, `Supports`, `Location in source`, `Limits`, `Checked`, `Used by`.

### SRC-001 — Computational autopoiesis review
- Reference: review of about three decades of computational autopoiesis; authors not recorded.
- URL: https://pubmed.ncbi.nlm.nih.gov/15245628/
- Recorded in: RESEARCH_REVIEW.md §2.
- Supports (per review): lifelike simulations exposed conceptual and methodological difficulties; persistence or visual complexity alone does not establish autopoiesis.
- Location in source: not recorded.
- Limits: a review, not a software architecture.
- Checked: no.
- Used by: CON-001, CLM-002.

### SRC-002 — Autopoiesis of the artificial: from systems to cognition (2023)
- Reference: Biosystems, 2023; author not recorded.
- URL: https://doi.org/10.1016/j.biosystems.2023.104936
- Recorded in: RESEARCH_REVIEW.md §3.
- Supports (per review): many AI approaches omit important autopoietic characteristics; coupling between organization, history and environment is hard to capture.
- Location in source: not recorded.
- Limits: theoretical analysis, no empirical test of a software architecture.
- Checked: no.
- Used by: CON-001, CLM-002.

### SRC-003 — Enactive cognition and computational models (review)
- Reference: scholarly review of predictive processing, embodied cognition, enactivism and active inference; authors not recorded.
- URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC5972168/
- Recorded in: RESEARCH_REVIEW.md §5.
- Supports (per review): approaches grouped under predictive processing differ in their commitments and are not one theory.
- Location in source: not recorded.
- Limits: about cognition, not software.
- Checked: no.
- Used by: CON-002.

### SRC-004 — Darwin Gödel Machine (2025)
- Reference: open-ended evolution of coding agents; authors not recorded.
- URL: https://arxiv.org/abs/2505.22954
- Recorded in: RESEARCH_REVIEW.md §8.
- Supports (per review): an archive of agent variants with empirical evaluation; the authors acknowledge that proving the general benefit of arbitrary self-modification is practically infeasible.
- Location in source: not recorded.
- Limits (per review): benchmark scores are proxies and can be overfit; results depend on the setup and base models; no proof of indefinite general self-improvement.
- Checked: no.
- Used by: CON-003, CLM-003.

### SRC-005 — Your Agent May Misevolve (ICLR 2026)
- Reference: empirical study of failure modes in self-evolving LLM agents; authors not recorded.
- URL: https://arxiv.org/abs/2509.26354
- Recorded in: RESEARCH_REVIEW.md §15.
- Supports (per review): evolution across model, memory, tool and workflow dimensions; reported cases where adaptation caused undesirable changes, including degraded safety alignment after memory accumulation and vulnerabilities introduced through tool creation or reuse.
- Location in source: not recorded.
- Limits (per review): results concern the studied models, scenarios and benchmarks.
- Checked: no.
- Used by: CLM-003.

### SRC-006 — Beyond Endpoint Performance: Process-Level Evaluation of Self-Evolving Agents (2026)
- Reference: authors not recorded.
- URL: https://arxiv.org/abs/2609.24663
- Recorded in: RESEARCH_REVIEW.md §16.
- Supports (per review): endpoint scores can hide when capabilities appear, persist or regress; reported retention losses and a gap between the best generated candidates and the updates selected.
- Location in source: not recorded.
- Limits: evaluates evolving agent memories and skills (per review), not repository code.
- Checked: no.
- Used by: CLM-005.

### SRC-007 — Self-Evolving Agents with Anytime-Valid Certificates (2026)
- Reference: authors not recorded.
- URL: https://arxiv.org/abs/2607.00871
- Recorded in: RESEARCH_REVIEW.md §17.
- Supports (per review): an evolving policy can influence the data, evaluator and hypothesis space used to judge it (endogeneity); proposes a limited change surface and versioned gates.
- Location in source: not recorded.
- Limits (per review): small, single-run evaluation.
- Checked: no.
- Used by: CLM-003, CLM-005.

### SRC-008 — Why Do Multi-Agent LLM Systems Fail? (NeurIPS 2025)
- Reference: empirical failure analysis of multi-agent systems; MAST taxonomy; authors not recorded.
- URL: https://arxiv.org/abs/2503.13657
- Recorded in: RESEARCH_REVIEW.md §18.
- Supports (per review): recurring failure modes in system design and specification, inter-agent misalignment, and task verification and termination; more agents or roles do not by themselves improve reliability.
- Location in source: not recorded.
- Limits (per review): particular frameworks and tasks; does not show that every multi-agent design underperforms.
- Checked: no.
- Used by: CLM-003.
