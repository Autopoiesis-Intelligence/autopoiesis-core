# Open PR consolidation inventory — 2026-10-27

**Status:** Read-only snapshot; not a merge order or authorization to close PRs.  
**Repository:** `Autopoiesis-Intelligence/autopoiesis-core`  
**Observed open PRs:** 27 at inventory time.  
**Current main baseline:** `4ae19f49f480246a2b42a3e9457190d43f03db6b` (recheck before any action).

## Immediate observations

1. The open PR count is 27. This is a coordination/merge-risk signal, not a reason to bulk-close work.
2. PRs #51, #55–#63 form the newer GPT queue-cycle line; several are based on the non-main branch `feat/queue-lifecycle-migration-20261025` or earlier commits on that branch. They must be assessed as a dependency chain, not independently cherry-picked or merged.
3. PRs #45 and #40 form the Claude coordinator/scheduled-cycle line; #41–#44 and #46–#49 depend on those branches. This is a competing lifecycle/coordinator line, so do not combine both stacks before selecting one coordinator.
4. PRs #33–#37 are earlier standalone lifecycle, selection, leases, plan, and theory changes based on main. The open PRs are not all equivalent: some may be foundational, some superseded, and some may be documentation-only.
5. PRs #64–#66 are a separate E4 safety investigation line on main. CI success does not by itself prove the runtime security property; the known output-overflow probe remains limited in what it demonstrates.
6. This list is a live snapshot of PR metadata only. It does not include per-PR changed-file diffs, mergeability, current check state, independent review verdict, or proof of runtime behavior. Those are required before recommending merge/closure.

## Proposed disposition workflow

- **P0 — Freeze expansion:** create no additional feature PRs until the two coordinator lines and open-PR policy are reconciled.
- **P1 — Capture dependencies:** fetch each PR's changed files, parent/base relationship, latest CI run IDs and conclusions, reviews/comments, and any known regression.
- **P2 — Classify:** `FOUNDATION`, `COORDINATOR-CLAUDE`, `COORDINATOR-GPT`, `SAFETY-E4`, `DOCS/THEORY`, `SUPERSEDED-CANDIDATE`, or `UNKNOWN`. Classification is provisional until diffs are read.
- **P3 — Compare coordinators:** use one shared acceptance matrix; pin exact SHAs; run same tests; record incompatible schemas and known regressions.
- **P4 — Recommend a single integration path:** explicitly list retain / port / supersede / close candidates with evidence and dependency rationale. Owner approves any merge or bulk closure.
- **P5 — Verify after each accepted merge:** exact resulting main SHA, CI run ID and conclusion, then regression tests for the next dependency. Do not rely on pre-merge branch CI as proof for the new main SHA.

## Full open-PR snapshot

| PR | Title | Head branch | Head SHA | Base branch | State | Last updated (UTC) |
|---|---|---|---|---|---|---|
| [#66](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/66) | fix(security): cap generated test output | `gpt/e4-bounded-output-2026-10-27` | `dc6b8a319c2a52a74dffaef6b69b999428b26fc6` | `main` | draft | 2026-10-27T16:20:47Z |
| [#65](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/65) | fix(security): bind queue verification to current attempt | `gpt/e4-attempt-bound-verification-2026-10-27` | `8737d5747ce1662235de6ed2332adb3adc4ef228` | `main` | draft | 2026-10-27T15:38:23Z |
| [#64](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/64) | docs(security): define E4 trust boundaries and isolation gaps | `gpt/e4-trust-boundaries-2026-10-27` | `512426e6481231bb413633f2859b66e3ac04914a` | `main` | draft | 2026-10-27T15:27:47Z |
| [#63](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/63) | Bind restored DONE history to PASS revision | `fix/done-history-revision-binding-20261027` | `6d00f8ad0eb5fc5a9c143b18a4cbdfa3968b8876` | `feat/queue-lifecycle-migration-20261025` | draft | 2026-10-27T01:25:23Z |
| [#62](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/62) | Bind queue DONE evidence to tested source snapshot | `fix/snapshot-bound-done-evidence-20261027` | `8d3f42df50337b86828e64066bdcc1018aa17b5a` | `feat/queue-lifecycle-migration-20261025` | draft | 2026-10-27T00:50:47Z |
| [#60](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/60) | Integrate queue cycle and archive limits | `integrate/queue-cycle-and-archive-limits-20261026` | `8339dc6792ae66c86a7f300c89fab1c36a5647b1` | `feat/queue-lifecycle-migration-20261025` | draft | 2026-10-27T00:21:34Z |
| [#59](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/59) | Reconcile bounded queue cycle with current lifecycle head | `reconcile/queue-cycle-on-04ac1d1-20261026` | `a9b263e8ea31b164a17eecbc6a4fd1383e2d73bd` | `feat/queue-lifecycle-migration-20261025` | draft | 2026-10-26T14:33:05Z |
| [#58](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/58) | Bound queue snapshot archive extraction resources | `fix/queue-snapshot-archive-limits-20261026` | `5a995890fa475ac4d3dd60f2bad9cb18f1531c8c` | `feat/queue-lifecycle-migration-20261025` | draft | 2026-10-26T14:05:34Z |
| [#57](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/57) | Expose archive-tamper restore test in dispatch schema | `fix/dispatch-restore-fault-schema-20261026` | `7961bc6b6edf27c5f1b92a07f3301dd16c01f461` | `main` | draft | 2026-10-26T14:29:37Z |
| [#56](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/56) | Reconcile bounded queue cycle with current lifecycle head | `reconcile/queue-cycle-on-105fbabb` | `53192dfa7f471d42834d126e6b43244e2b745100` | `feat/queue-lifecycle-migration-20261025` | draft | 2026-10-26T14:08:14Z |
| [#55](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/55) | Add bounded single-task queue cycle coordinator | `feat/bounded-queue-cycle-a37-stack` | `6186b62a72a12ecb58bd8866ce4b83d7d5968b25` | `feat/queue-lifecycle-migration-20261025` | draft | 2026-10-26T14:08:21Z |
| [#51](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/51) | Port governed queue lifecycle to main | `feat/queue-lifecycle-migration-20261025` | `04ac1d1ab1fcfc9f762758d385adb27a084a5f45` | `main` | draft | 2026-10-26T14:37:14Z |
| [#49](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/49) | Fix fail-closed scheduled run history validation | `gpt/a13-scheduled-history-fail-closed` | `64b4a45ca1743cd4e79b69237344942c3205c7d0` | `claude/cl-021-scheduled-cycle` | draft | 2026-10-26T11:24:30Z |
| [#48](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/48) | Fail closed on unfiltered paginated restore history | `gpt/a30-46-unfiltered-restore-history` | `ab2c14978d8c6b047ccc7c341099cc2cf1812679` | `claude/cl-021-scheduled-cycle` | draft | 2026-10-24T13:27:03Z |
| [#47](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/47) | Fail closed on newest restore source run | `gpt/a30-38-restore-selector-tests` | `f64fd55f60cd53a6b4ba30d5154805851d40e0ed` | `claude/cl-021-scheduled-cycle` | draft | 2026-10-24T00:32:13Z |
| [#46](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/46) | Fail scheduled cycle workflow on timeout and refusal | `gpt/a30-28-cycle-exit-contract` | `56522385acaba81008f3f16f0bca3ae0323f23b0` | `claude/cl-021-scheduled-cycle` | draft | 2026-10-23T23:56:23Z |
| [#45](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/45) | Integrate task lifecycle, leases, and bounded A10 cycle | `claude/cl-020-a10-cycle` | `ba65d04f7cb4115c58ca2d512ce8a8786864e5d8` | `main` | draft | 2026-10-24T13:30:17Z |
| [#44](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/44) | Capture GitHub pagination from observed Link headers | `gpt/github-pagination-collector-a72` | `04f1db6b088c72c32e8cf4c6d8cb2024a1bc862d` | `claude/cl-020-a10-cycle` | draft | 2026-10-23T23:30:23Z |
| [#43](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/43) | Add strict paginated evidence validation contract | `gpt/paginated-evidence-contract-a71` | `a7bc8dc9a6014efb437dd73c49b93e803f89c594` | `claude/cl-020-a10-cycle` | draft | 2026-10-23T23:32:04Z |
| [#42](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/42) | Fix recovery evaluator workflow and artifact identity | `gpt/recovery-proposal-a64-workflow-identity` | `1f31a04fe42d84ec47f2eca3f80b83671e716fce` | `claude/cl-020-a10-cycle` | draft | 2026-10-23T23:21:01Z |
| [#41](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/41) | Add read-only recovery proposal evaluator | `gpt/recovery-proposal-a59-ci` | `677c609767a8c5eae1934e5ad7a8de4e4fcc6030` | `claude/cl-020-a10-cycle` | draft | 2026-10-23T22:57:59Z |
| [#40](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/40) | Add fail-closed scheduled autonomy cycle (A13) | `claude/cl-021-scheduled-cycle` | `db228806c23689bc49dcb4e79200214fd627fa9e` | `claude/cl-020-a10-cycle` | ready | 2026-10-24T00:39:33Z |
| [#37](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/37) | Add docs/theory: traceable theory base for the core (CL-016) | `claude/project-thread-ofxc12` | `6521ddd55fe1c4c369c65834388d72bd6f240a6c` | `main` | ready | 2026-10-24T16:57:13Z |
| [#36](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/36) | Add task leases and recovery of stuck tasks (A9, CL-013) | `claude/cl-013-task-leases` | `f6cd267e6a663349091cbd3d43b2c00eaa317cc4` | `main` | ready | 2026-10-23T21:39:16Z |
| [#35](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/35) | Add docs/PLAN.md, the standing work plan (CL-014) | `claude/cl-014-plan` | `4e6092b8bf34e8ee49992d091b7af741af3388ec` | `main` | ready | 2026-10-27T01:24:51Z |
| [#34](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/34) | Add deterministic next-task selection (A4, CL-012) | `claude/cl-012-task-selection` | `c581ccbb7c9657fc727fa2d053b0ac7a4cf44f5b` | `main` | ready | 2026-10-23T20:34:43Z |
| [#33](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/pull/33) | Enforce a closed task lifecycle (A3, CL-011) | `claude/cl-011-task-lifecycle` | `48c8fa52e0a0190f89ab6b641524f354cea9ee75` | `main` | ready | 2026-10-27T08:49:44Z |

## Evidence limitations

- This inventory was read from GitHub PR metadata. No source code was changed by this inventory.
- No PR was merged or closed by this action.
- No statement here certifies any PR as safe, independently audited, or ready to merge.
- Before action, re-fetch every exact head SHA and relevant CI/review state; the snapshot can become stale immediately.
