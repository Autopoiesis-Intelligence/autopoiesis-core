# Repository Restructuring Plan

**Status:** Proposed migration plan, 2026-11-14.  
**Rule:** No bulk rewrite, no default-branch mutation and no package rename as a side effect.

## 1. Current baseline

- Main: 4ae19f49f480246a2b42a3e9457190d43f03db6b.
- Existing G3 candidate PR #69: head f3e9c7c02bd86c1cd1cf13d63916f06233030780.
- CI run 43618147026: success on that exact PR head.
- The run's ordinary PR path skipped the synthetic seed and restore probes. It does not prove cross-run persistence.
- This restructuring branch starts from main so that the documentation proposal does not silently absorb or duplicate PR #69. The G3 candidate remains a separate review item.

The repository currently contains one Python package, a file-driven runner, tests, workflow configuration, one autonomy roadmap and coordination documents. It does not yet contain the target architecture packages described below.

## 2. Current-to-target responsibility map

| Current path | Primary responsibility today | Target boundary | Action |
|---|---|---|---|
| autopoesis/core.py | Canonical JSON, state digest, simple transition | kernel contracts | Preserve the public API; split pure primitives only after contract tests |
| autopoesis/domain.py (new on restructuring branch) | Canonical state graph X and relation set R | domain model | Initial immutable snapshot contract; keep cohesive until complexity justifies a package |
| autopoesis/task_queue.py | Queue schema, lifecycle, history, persistence | runtime/queue or persistence adapter | Separate lifecycle rules from file I/O |
| autopoesis/queue_snapshot.py | Snapshot, restore and artifact provenance checks | adapters/storage + provenance contracts | Keep infrastructure-specific GitHub details outside kernel |
| autopoesis/executor.py | Patch artifact generation, sandbox application and test execution | adapters/execution + verification | Split generation, application and verification interfaces |
| autopoesis/audit_verdict.py | PR verdict validation and label-state logic | adapters/vcs + governance policy | Keep GitHub-specific parsing outside domain kernel |
| autopoesis/coordination.py | Agent publisher/coordination contracts | interfaces/coordination or development tooling | Do not confuse development-agent coordination with product autonomy |
| autopoesis/agent_budget.py | External agent usage/budget constraints | adapters/agent_runtime | Keep provider/runtime-specific |
| autopoesis/copilot_writer.py | One replaceable code writer | adapters/generation | Preserve as one implementation of a writer port |
| run_tasks.py | CLI, task dispatch, orchestration and output files | interfaces/cli + runtime/orchestrator | Thin CLI; move business decisions out |
| TASKS.json | Explicit local task input | Runtime input contract | Version schema; retain bounded task types |
| tests/ | Unit and integration checks | Mirror domain boundaries | Preserve historical tests; add contract/integration suites |
| .github/workflows/ci.yml | GitHub CI and optional snapshot seed/restore | GitHub adapter/CI | Keep outside core; changes need owner approval |
| AGENTS.md | Repository policy and authority rules | Repository governance | Keep as single policy source |
| docs/AUTONOMY_ROADMAP_SPEC.md | A0–A12 acceptance roadmap | Product capability gates | Retain; align terminology with target architecture |

The existing package spelling autopoesis/ is intentionally retained. A package rename is a separate compatibility/migration decision and must not be mixed with architectural separation.

## 3. Proposed logical package layout

Do not create empty directories just to make the tree look complete. Introduce each boundary when a real contract and implementation move together.

\`\`\`text
autopoesis/
  kernel/
    canonical.py
    identity.py
    invariants.py
    transition.py
    errors.py
  domain.py  # canonical StateGraph and domain records
  evolution/
    observe.py
    reflect.py
    goals.py
    generate.py
    select.py
    experiment.py
    learn.py
  memory/
    history.py
    knowledge.py
    projections.py
  governance/
    policy.py
    authorization.py
    decisions.py
  runtime/
    orchestrator.py
    lifecycle.py
    recovery.py
  ports/
    storage.py
    generator.py
    executor.py
    verifier.py
    observer.py
  adapters/
    filesystem/
    github/
    ci/
    model/
    execution/
  interfaces/
    cli.py
    reports.py

tests/
  contracts/
  unit/
  integration/
  fixtures/
docs/
  architecture/
  coordination/
\`\`\`

This is a target map, not a requirement to split every file into a separate module. Keep the trusted kernel small. Prefer fewer cohesive modules over a directory-per-concept structure.

## 4. Migration sequence

### R0 — Reconcile and freeze a baseline
- Record main, candidate PRs, exact heads, CI and open architectural blockers.
- Do not rebase or merge PR #69 as part of this work.
- Acceptance: a reproducible baseline table and no stale proof claims.

### R1 — Architecture and contract freeze
- Publish target architecture, module map and decision register.
- Define domain-neutral interfaces and explicit unresolved decisions.
- Acceptance: each existing module has a target responsibility; no code is moved yet.

### R2 — Domain/kernel extraction
- Add contract tests around canonical state, relations, invariants and transitions.
- Introduce a canonical StateGraph snapshot for X and R while preserving the existing core.py API.
- Keep domain representation separate from deterministic kernel primitives; do not prematurely split a small cohesive model into many files.
- Acceptance: duplicate IDs and dangling relations fail closed; equivalent graphs canonicalize identically; caller mutation cannot alter a snapshot; old digest/evolve behavior remains compatible; no adapter imports inside the domain or kernel.
- Current branch: the first StateGraph implementation and contract tests exist, but they are not CI-proven yet.

### R3 — Lifecycle and persistence separation
- Separate queue lifecycle transition rules from filesystem locks, atomic writes and snapshot handling.
- Version persisted schemas and define legacy-read behavior.
- Acceptance: negative tests for malformed, stale, duplicate and interrupted state; migration and rollback are tested.

### R4 — Evolution protocol
- Separate observation, reflection, goal proposal, candidate generation, selection, experiment planning and learning.
- Preserve explicit task execution as one adapter.
- Acceptance: one end-to-end candidate can be traced from source evidence through decision and outcome; no claim of self-directed autonomy from a scripted fixture.

### R5 — Governance and verification contracts
- Define exact scoped authorization and independent verification records.
- Keep approval, execution, commit and merge separate.
- Acceptance: mismatched, stale or missing evidence/authority fails closed; owner-only merge rule remains.

### R6 — Runtime and adapters
- Make CLI thin; add replaceable storage, generation, execution, verification and VCS adapters.
- Acceptance: kernel/domain tests run without network, provider credentials or GitHub.

### R7 — Self-modification
- Permit the system to propose changes to its own modules under bounded patch and execution policies.
- Acceptance: generated patch is bound to parent state, tested in a disposable environment, independently verified, authorized, reviewable and reversible.

### R8 — Federation and generalization
- Add domain modules, clone/fork/lineage and federation only after identity, memory provenance, authority and conflict semantics are specified.
- Acceptance: separate domain demonstration plus clone lineage and conflict/recovery tests.

## 5. Sequencing constraints

- R0 and R1 are documentation and reconciliation work.
- R2–R6 are bounded implementation migrations; each should be a separate PR or independently reviewable unit.
- R7 must not start before lifecycle, persistence, verification and governance contracts are proven for the chosen scope.
- R8 is deliberately late. Federation before identity and authority semantics would multiply ambiguity.
- Workflow, permissions, secrets, scheduling and branch protection changes require explicit owner approval under AGENTS.md.
- No PR auto-merge. The owner remains the merge authority.

## 6. Rollback and compatibility

- Do not rename autopoesis/ in the same change as moving modules.
- Keep compatibility re-exports temporarily when moving public functions.
- Read old persisted schemas explicitly; never guess missing authority or evidence.
- Write the new schema only after migration tests pass.
- Preserve rejected history and old artifacts; do not rewrite old evidence to match new terminology.
- Every migration records source schema, destination schema, code SHA and rollback path.

## 7. Current status

- R0: in progress; main and PR #69 reconciled at the SHAs above.
- R1: target proposal drafted in this branch.
- R2: initial `StateGraph` implementation and 22 contract tests are present on the restructuring branch. The tests have not been executed locally or in CI; implementation is not CI-proven and is not ready for owner review.
- Validation blocker: the branch has no workflow run. The repository currently has 29 open PRs; do not create another PR until the existing queue and per-agent limit in `AGENTS.md` are reconciled.
- R3–R8: not started.
- Runtime autonomy: not proven by this documentation change.
