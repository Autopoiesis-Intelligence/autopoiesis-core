# Coordinator comparison — evidence-based preliminary matrix

**Date:** 2026-10-27  
**Status:** Preliminary; no coordinator selected; no merge/closure authorized.  
**main baseline observed:** `4ae19f49f480246a2b42a3e9457190d43f03db6b`  
**Working branch:** `gpt/continuity-stack-2026-10-27`

## Findings from exact PR metadata and sampled patches

| Candidate / concern | Exact head | Base | Observed evidence | Preliminary disposition |
|---|---|---|---|---|
| Claude integration #45 | `ba65d04f7cb4115c58ca2d512ce8a8786864e5d8` | main `4ae19f4...` | Integrates lifecycle, leases, A10; 15 files, +2013/-55. CI run cited in history skipped restore steps on that path. | Candidate, but current runtime restore proof incomplete. |
| Claude scheduled cycle #40 | `db228806c23689bc49dcb4e79200214fd627fa9e` | #45 head `ba65d04...` | Scheduled workflow adds six-hour schedule, main-only gate, read-only GitHub token permissions, emergency-stop check. | Dependent layer; must not be assessed as standalone or enabled before full runtime and policy review. |
| GPT queue lifecycle migration #51 | `04ac1d1ab1fcfc9f762758d385adb27a084a5f45` | main `4ae19f4...` | 15 files, +2203/-87. Broad lifecycle migration and restore pagination/fault validation. Historical runtime comments cite older head `c0422b16...`; they do not prove current head. | Candidate, but re-run current-head restore tests before selection. |
| GPT coordinator #55 | `6186b62a72a12ecb58bd8866ce4b83d7d5968b25` | queue migration ancestor `8837f1eb...` | Adds `queue_cycle.py`, 283 lines, bounded one-task cycle. | Candidate patch, but it is not based directly on main. |
| GPT coordinator #56 | `53192dfa7f471d42834d126e6b43244e2b745100` | queue migration ancestor `bfbcf9ba...` | Same 2-file, +772/-0 diff as #55 in the sampled patch; branch/base differs. | Duplicate-patch candidate; do not merge both. |
| GPT coordinator #59 | `a9b263e8ea31b164a17eecbc6a4fd1383e2d73bd` | queue migration head `04ac1d1...` | Same coordinator patch shape and 2-file, +772/-0 diff as #55/#56 in sampled result; rebased on the current migration head. | Strongest integration candidate for comparison, not automatically accepted. |
| Archive limits #58 | exact head not recorded in this summary | queue migration line | Adds archive/member/uncompressed-size/compression-ratio limits in restore verification. | Security-relevant independent change; test and integrate only once. |
| Integration #60 | `8339dc6792ae66c86a7f300c89fab1c36a5647b1` | queue migration head `04ac1d1...` | Combines queue cycle and archive limits, 7 files, +1315/-49. | Integration candidate; compare against #58 and #59 for duplicated or missing changes. |
| Snapshot-bound DONE #62 | `8d3f42df50337b86828e64066bdcc1018aa17b5a` | queue migration head `04ac1d1...` | 8 files, +1407/-53; binds DONE evidence to tested source snapshot and includes archive fault handling. | Likely overlapping integration work; diff/test comparison required. |
| Restored history revision #63 | `6d00f8ad0eb5fc5a9c143b18a4cbdfa3968b8876` | queue migration head `04ac1d1...` | 9 files, +1444/-57; overlaps archive restore fault handling and binds restored DONE history to PASS revision. | Likely overlapping integration work; diff/test comparison required. |

## What the evidence supports

1. The competing coordinator lines are not merely theoretical: #45/#40 form one dependency chain, while #51 is a separate migration line.
2. The queue-cycle implementation appears as repeated near-identical patches (#55, #56, #59). Only one copy should survive integration, after tests establish which base has the correct lifecycle contracts.
3. Restore/security changes are also repeated or combined across #58, #60, #62 and #63. They must be consolidated by behavior and tests, not merged PR-by-PR.
4. Mergeability metadata is not correctness evidence. A PR marked mergeable may still be stale, duplicate, unsafe or semantically incompatible.
5. No claim of end-to-end autonomous evolution follows from these patch diffs.

## Required acceptance matrix before selection

Run the same tests against exact candidate SHAs for:
- valid and invalid lifecycle transitions; DONE requires a matching PASS;
- evidence bound to task ID, attempt, source digest and exact candidate snapshot;
- deterministic selection and no duplicate claim;
- lease expiration/recovery without stuck tasks or false success;
- corrupted JSON, schema mismatch, archive tampering, path traversal, oversized member, compression bomb and digest mismatch;
- restore of a valid prior run and refusal of missing/stale/failed prior run;
- emergency stop and scheduled workflow gate, including verifying no execution on non-main refs;
- interrupted execution, output/time/resource caps, and exact observable final status;
- compatibility between queue schema, executor, verifier, restore and coordinator.

Each test record must include candidate SHA, workflow run ID, job outcome, test case, and whether it is unit, synthetic integration, or real runtime evidence.

## Recommendation at this stage

Do not select a winner yet. First compare #45 and #51 on the shared acceptance matrix. Treat #59 as the current-base copy of the coordinator patch for comparison; do not accept #55/#56 in addition. Then consolidate archive and snapshot-binding behavior once across #58/#60/#62/#63. Preserve #35/#37 as documentation/theory proposals until their claims and links are reconciled with the chosen implementation. Keep #64–#66 as a separate E4 safety track; do not let that track's synthetic CI probes be presented as proof of hostile-code isolation.

No PR was merged or closed by this work. No main, workflow, permission, secret, or repository setting was changed.


## Current-head CI check (observed 2026-10-27)

These are checks attached to the exact PR heads, not claims of runtime production execution.

| PR | Exact head | Check evidence | Interpretation |
|---|---|---|---|
| #45 | `ba65d04f7cb4115c58ca2d512ce8a8786864e5d8` | CI run `40040883201` success | Unit/CI pass; does not by itself establish a real restore cycle. |
| #51 | `04ac1d1ab1fcfc9f762758d385adb27a084a5f45` | CI run `40341136653` success; negative-fault run `40340951044` failed under title `Negative restore fault: tamper_archive` | Normal CI is green. The negative run is designed to fail, but the title alone does not prove the intended gate was reached; inspect gate-labelled output before treating it as evidence. |
| #59 | `a9b263e8ea31b164a17eecbc6a4fd1383e2d73bd` | CI run `40337565727` success | Unit/CI pass for the coordinator patch on this base; not runtime proof. |
| #60 | `8339dc6792ae66c86a7f300c89fab1c36a5647b1` | Normal CI run `40424820253` success; several earlier negative-fault dispatches failed | The current head has a green CI run, but the failed negative dispatches require gate-output interpretation. |
| #62 | `8d3f42df50337b86828e64066bdcc1018aa17b5a` | PR CI run `40426758539` success | Green CI for this earlier overlapping integration head. |
| #63 | `6d00f8ad0eb5fc5a9c143b18a4cbdfa3968b8876` | PR CI run `40431109654` success; dispatch CI run `40432310161` success; negative-fault run `40432281472` failed with title `Negative restore fault: tamper_archive` | Best observed candidate for further review because it combines the queue-cycle patch, archive limits, fault-gate checks, and restored PASS-revision binding. This is a review priority, not an approval or proof of real unattended operation. |

The failed runs named `Negative restore fault: tamper_archive` are intentionally negative dispatches. A failed workflow is not sufficient evidence that the expected validation gate rejected the tampered archive; the run must report the matching gate label and fail for the intended reason. The successful normal CI runs are useful but remain CI evidence, not proof of the full scheduled cycle in a real runtime.

## Updated next action

Prioritize one code-level audit of #63 at `6d00f8ad0eb5fc5a9c143b18a4cbdfa3968b8876`, then compare its complete diff and tests with #60 and #62. Verify the exact negative-fault gate output for run `40432281472`. Do not merge or close any PR. Revisit #45 versus #51 only after recording whether their distinct coordinator models can share the same acceptance tests without incompatible state semantics.
