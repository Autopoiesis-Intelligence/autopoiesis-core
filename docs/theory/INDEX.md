# Theory base: index

This folder holds the project's theory: concepts, sources, claims, how they reach the code, and what is still open. It exists so that an agent can check the reasoning behind a task from the repository, without relying on chat history.

**Status of this folder:** a skeleton (CL-016). The seed entries below come only from documents already in the project. No source listed here was re-opened when this skeleton was written (see `Checked:` in [SOURCES.md](SOURCES.md)). Do not treat the base as ready to use until the sources are checked and the links to the current architecture are reviewed.

## Authority

- Theory documents never authorize a change to the core, a merge, a workflow or a setting. Authority comes only from [AGENTS.md](../../AGENTS.md) and the owner.
- A claim's status describes the kind of knowledge it is, not permission to build it. An `ACCEPTED` design claim still needs a task, tests, CI on the exact SHA, an audit and an owner merge.
- `AGENTS.md` wins over anything here. If a theory entry contradicts it, the entry is wrong or needs an owner decision, recorded in [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

## Files

| File | Holds | IDs |
|---|---|---|
| [FOUNDATIONS.md](FOUNDATIONS.md) | Concepts and their working definitions | `CON-NNN` |
| [SOURCES.md](SOURCES.md) | Registry of external sources: exact reference, what it supports, limits, check status | `SRC-NNN` |
| [CLAIMS.md](CLAIMS.md) | Registry of claims with status, grounds, counterarguments, how to check | `CLM-NNN` |
| [THEORY_TO_CODE.md](THEORY_TO_CODE.md) | From a claim to a rule, roadmap stage, code, tests and evidence | `T2C-NNN` |
| [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) | Contradictions, untested assumptions, pending decisions | `OQ-NNN` |

Read in this order before challenging or implementing a design decision: this index, the claim in CLAIMS.md, its sources, its row in THEORY_TO_CODE.md, then the related open questions.

## Existing documents this base links to (not duplicated)

| Document | Where | What it already covers |
|---|---|---|
| `AGENTS.md` | `main` | Project rules, evidence ladder, audit verdicts, report format |
| `docs/AUTONOMY_ROADMAP_SPEC.md` | `main` | Stages A0–A12: requirements and acceptance gates |
| `docs/PLAN.md` | PR #35, not merged | Ordered task plan |
| `RESEARCH_REVIEW.md`, `ARCHITECTURE.md`, `STATE_TRANSITION_CONTRACT.md`, `IMPLEMENTATION_GAP_ANALYSIS.md` | branch `docs/autopoiesis-core-architecture-baseline` at `c69452f` (draft PR #3), not on `main` | Literature review, design baseline, transition contract, gap analysis |

Entries that rely on a document not on `main` say so. Such a document is a design input, not an accepted rule.

## Two status scales

Two scales exist and must not be mixed.

**Knowledge status** (this folder, every `CLM`):

| Status | Meaning |
|---|---|
| `OBSERVED` | Seen directly: a file at an exact SHA, a CI run, a runtime record. Name it. |
| `SUPPORTED` | Backed by checked sources or evidence, which are named. Not absolute truth. |
| `ACCEPTED` | Adopted as a working project decision by the owner or by a rule on `main`. Not scientific proof. |
| `HYPOTHESIZED` | Proposed; needs a check that is described. |
| `UNRESOLVED` | Open; competing answers exist or nothing decides it yet. |
| `REJECTED` | Ruled out; the reason is recorded. |
| `SUPERSEDED` | Replaced; names the claim that replaces it. |

**Evidence level** (`AGENTS.md`, for implementation claims): `DESIGN`, `IMPLEMENTED`, `REACHABLE`, `RUNTIME`, `PERSISTED`, `AUDITED`, `CI_PROVEN`, always with an exact SHA.

Other vocabularies exist in the older repositories: Gnosis `research/INDEX.md` (12 statuses from `RESEARCH` to `SUPERSEDED`), Gnosis `CLAIMS.md`, and Gnosis-Memory records (`FORMALIZED`, `OPEN`, `HISTORICAL`, `IMPLEMENTED_PENDING_RUNTIME_VERIFICATION`). When citing such a record, quote its status as written and give this base's status separately; never translate one into the other silently. Which registry is canonical is OQ-008.

A claim about the theory uses a knowledge status. A claim that something works in the code also names its evidence level and SHA in THEORY_TO_CODE.md. The word `ACCEPTED` here is not an audit verdict (`Verdict: ACCEPTED` in `AGENTS.md`); see OQ-004.

## Claim kinds

Every claim names one kind, because they are checked differently:

- `scientific`: about the world or the literature. Checked against sources.
- `design`: a project decision. Checked against goals, alternatives and owner decisions.
- `engineering`: a prediction about how the code will behave. Checked by tests and runs.

## Trace chain

Each link names the next one, so that any step can be checked:

`SRC` → `CLM` → rule or decision (AGENTS.md, owner decision) → stage (A0–A12) → task (PLAN.md / PR) → test → evidence (SHA, CI run) → audit verdict.

A missing link is written as `none yet`, never left out or guessed.

## Rules for editing

1. Every significant statement gets an ID and a traceable ground. IDs are never reused or renumbered.
2. Never invent sources, quotes, page numbers or results. If a source was not opened, say so in `Checked:`. If it supports only part of a claim, say which part.
3. Keep scientific claims, design decisions and engineering hypotheses apart (claim kinds above).
4. A design claim lists alternatives, risks and how it is checked.
5. If a claim conflicts with the behaviour of the core, stop the related task and record the conflict in OPEN_QUESTIONS.md. Neither the theory nor the code is assumed right.
6. Change a status only with a reason and date in the entry. `REJECTED` and `SUPERSEDED` entries stay in place.
7. Keep it small: add an entry when a task or a decision needs it, not to cover a field.

`tests/test_theory_docs.py` checks the mechanical part: relative links resolve, every referenced ID is defined exactly once, statuses and kinds use the vocabulary above, and source entries carry `URL:` and `Checked:` lines. It does not check that a source says what we claim.
