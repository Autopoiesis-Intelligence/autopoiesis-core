# Autopoiesis — Target Architecture

**Status:** Proposed target architecture, version 0.1, 2026-11-14.  
**Authority:** Design proposal only. It does not change repository execution permissions or claim that described capabilities exist.

## 1. Product definition

Autopoiesis is a general-purpose, bounded self-organizing and evolutionary system. It observes a system and its environment, maintains explicit models and history, identifies opportunities or problems, generates candidate changes, tests and evaluates them, and changes its own state and relations only within delegated authority.

Software development is the first experimental domain, not the definition of the product. Code changes are one possible state transition. Other domains may use the same evolution contract with different domain models and adapters.

The product is not an autonomous LLM agent. Models, tools, workers, schedulers, repositories and execution environments are replaceable participants around a small trusted core.

## 2. Foundational model

The original model remains:

\[
\Psi = (X, R)
\]

- **X — state elements:** entities, properties, resources, observations, goals, constraints and other domain objects.
- **R — relations:** typed, directed or undirected relationships between state elements, including dependency, ownership, causality, containment and lineage.

A transition is a proposed transformation:

\[
T: (X_t, R_t) \rightarrow (X_{t+1}, R_{t+1})
\]

The transition is not accepted merely because it is generated or executed. It must satisfy domain invariants, policy constraints and declared acceptance criteria.

### History and memory are not additional authority

History and memory are essential, but they should not be added to the canonical state tuple as independent sources of authority without a separate justification.

- **History (H):** append-only records of observations, proposals, decisions, executions, verification results and accepted transitions. It records what happened and its provenance.
- **Memory (M):** queryable projections derived from history and approved knowledge. It helps the system reason; it cannot silently rewrite history or grant permission.
- **Current state:** a materialized, versioned view whose accepted changes can be traced to history.

This keeps \(\Psi=(X,R)\) as the domain model while making continuity and learning explicit architectural services.

## 3. Evolution cycle

The full cycle preserves the September concept while separating decision stages that must not be conflated:

1. **Observe** — collect a bounded, source-labelled view of the system and environment.
2. **Remember** — append observations and outcomes; retrieve relevant prior experience.
3. **Model** — update explicit state, relations, uncertainty and known constraints.
4. **Reflect** — detect contradictions, failures, missing capabilities and possible improvement.
5. **Formulate** — define goals or subgoals, success criteria, risk and resource bounds. Goals may be externally supplied or internally proposed; internal proposals do not authorize execution.
6. **Generate** — produce candidate transitions, each with rationale, scope and expected effects.
7. **Select** — rank candidates under a declared policy; preserve rejected and deferred alternatives.
8. **Experiment** — test candidates in a bounded, disposable or otherwise explicitly authorized environment.
9. **Verify** — independently compare observed results with predeclared acceptance criteria.
10. **Govern and authorize** — determine whether this exact transition is permitted. Evidence is not authority.
11. **Apply and persist** — apply only the authorized transition and record the resulting state identity and provenance.
12. **Learn and evolve** — update memory and revise models or mechanisms when evidence supports doing so.

This is a conceptual cycle, not a mandatory linear evidence ladder. For example, static analysis or CI may happen before a runtime trial. Every stage must still state what it proves and what it does not prove.

## 4. Architectural layers

### 4.1 Domain model
Owns the meaning of state elements, relations, invariants, identity and transition semantics. It must not depend on GitHub, a particular LLM, a scheduler or a specific application domain.

### 4.2 Trusted kernel
The smallest deterministic policy-enforcing foundation:
- canonical representation and stable identity;
- state/relation validation;
- pure transition evaluation;
- invariant checking;
- deterministic decision primitives where policy requires them;
- explicit error and refusal outcomes.

Constraints: Python standard library only for the current implementation; no network, credentials, model calls, hidden clock, arbitrary shell, eval or exec driven by task data. The kernel does not perform external side effects. Time, randomness, external identity and environment observations must be explicit inputs supplied by an adapter and validated against policy.

### 4.3 Evolution engine
Coordinates the evolution protocol: reflection, goal proposals, candidate generation contracts, selection, experiment planning, comparison and learning. It can request actions; it cannot grant itself authority.

Generation and selection must be separable and replaceable. A model may propose candidates, but the model is not the trusted decision authority.

### 4.4 History and memory
History is durable and append-oriented. Memory is derived, versioned and rebuildable where possible. Records must distinguish observed facts, supported conclusions, accepted knowledge, hypotheses, unresolved questions, rejected directions and superseded claims.

No memory summary may override exact repository/runtime evidence. A memory item is not an authorization token.

### 4.5 Governance and authority
Defines who or what may propose, approve, execute, commit and merge a change. These are distinct permissions.

An authorization decision must be scoped to the exact action, target, parent state, constraints and applicable policy. It must not be inferred from a PASS, hash, task status, PR label or successful CI. The current owner-controlled merge rule remains in force.

The trusted kernel may validate a supplied authorization record, but the mechanism that issues trusted grants and proves issuer identity requires a separately specified threat model. Do not claim cryptographic trust from a caller-supplied JSON field.

### 4.6 Execution and verification
Execution adapters perform bounded side effects in explicitly described environments. Verification is independent of generation where feasible and records the actual command, environment, source snapshot, resulting snapshot, verifier and acceptance criteria.

A temporary directory is not automatically a security sandbox. Every execution capability must state filesystem, network, process, resource and timeout limits, including limitations that cannot currently be enforced.

### 4.7 Adapters and interfaces
Adapters connect the core to replaceable external systems:
- observation and domain connectors;
- model/provider and candidate-generator connectors;
- storage and snapshot backends;
- bounded executors and verifiers;
- version-control and CI systems;
- schedulers and user interfaces.

The adapter boundary is the only place for network access, credentials, provider SDKs and infrastructure-specific behavior. An adapter cannot silently widen kernel authority.

### 4.8 Federation and lineage
Clone, fork, lineage and federation are future system-level capabilities, not kernel prerequisites. Each clone must have an explicit identity, parent/lineage record, policy boundary and state provenance. Sharing knowledge must not implicitly share authority. Conflict resolution and merge semantics require a separate consistency design before implementation.

## 5. Cross-cutting contracts

Every proposed transition should carry, at minimum:
- stable candidate and domain identifiers;
- parent state/version and canonical digest;
- affected elements and relations;
- rationale and source observations;
- expected benefit and declared risks;
- preconditions and postconditions;
- resource and execution bounds;
- acceptance criteria;
- generator identity/version, if applicable;
- experiment and verification references;
- authorization reference, when execution requires one.

Every execution/evidence record should identify the exact candidate, source snapshot, action, environment, result, verifier and relevant artifact digests. Missing or mismatched fields fail closed.

These are target contracts. They must be introduced through versioned schemas and migrations; do not silently reinterpret old queue records as stronger evidence.

## 6. Autonomy model

Use the existing repository levels:
- **L1:** independently discovers a problem.
- **L2:** independently proposes and checks a fix.
- **L3:** executes an authorized change in a bounded environment.
- **L4:** governs its own development within pre-set authority while remaining verifiable, refusable and reversible.

A level is claimed only for a declared domain and scope, after the corresponding end-to-end acceptance trial. Agent-assisted repository development is not evidence that the product itself has that autonomy.

## 7. Evidence and status

Keep design, implementation, reachability, runtime, persistence, audit and CI evidence distinct. These are evidence dimensions, not necessarily sequential lifecycle stages.

Use explicit epistemic labels for knowledge:
- OBSERVED
- SUPPORTED
- ACCEPTED
- HYPOTHESIZED
- UNRESOLVED
- REJECTED
- SUPERSEDED

A CI result proves only the checks that ran on its exact head SHA. Synthetic fixtures must remain labelled synthetic. Persistence requires a real restart/restore boundary. Runtime autonomy requires an observed end-to-end run under the declared authority and scope.

## 8. Product structure

The product should eventually expose:
- **Core:** domain-neutral state, relation, transition, invariant and governance contracts.
- **Modules:** domain models and evolution capabilities.
- **Adapters:** external providers, storage, execution, CI and integration.
- **Interfaces:** human oversight, inspection, reporting and operation.

This is a logical product boundary, not a decision to split the current repository into multiple repositories or services.

## 9. Non-goals and rejected shortcuts

- Do not equate a task queue with evolution.
- Do not equate code generation with self-improvement.
- Do not treat a green CI run as runtime or persistence proof.
- Do not put provider-specific logic, credentials or network calls in the trusted kernel.
- Do not add an implicit scheduler, global operator or hidden autonomous selector to the kernel.
- Do not let memory summaries replace source records.
- Do not let verification imply approval, execution permission, commit or merge.
- Do not implement federation before identity, lineage, provenance and conflict semantics are defined.
- Do not rewrite all existing modules in one migration.

## 10. Definition of architectural completion

The architecture is ready to guide implementation when:
1. Each current module has one primary responsibility and an explicit target layer.
2. Domain contracts and data schemas are versioned.
3. Kernel/adapter boundaries are testable without external services.
4. Authority, evidence, execution and persistence have independent contracts.
5. Migration and rollback paths exist for persisted data.
6. Every roadmap capability has acceptance criteria that name the evidence level and autonomy scope.
7. Unresolved decisions are recorded rather than silently treated as settled.
