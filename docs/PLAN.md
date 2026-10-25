# Work plan

The standing, ordered plan for autopoiesis-core. The owner sets priorities. GPT adds strategy and acceptance criteria. Claude takes the first unblocked `READY` task without waiting for a "next" command, records evidence here and in Issue #22, and marks contradictions instead of silently working around them. Only the owner merges; nothing here authorizes auto-merge or changes to `main`, workflows, permissions or settings.

## How to use

- **Statuses:** `READY` (can start), `BLOCKED` (names its blocker), `IN_REVIEW` (PR open, waiting for audit or merge), `DONE` (merged, with merge SHA and CI run).
- **Every task has:** goal, acceptance criteria, dependencies, and the evidence that will count. A task without acceptance criteria is not `READY`.
- **Dependencies:** a task may start on a branch built on an unmerged PR only if that is listed under *Depends on*. If the base PR changes after audit, the dependent PR is rebuilt on the new base and audited again.
- **Limit:** at most 5 own PRs waiting at once (owner decision, 2026-10-23).
- **Evidence:** a verdict counts only per `AGENTS.md` ("Review and audit"): an issue comment through the Codex app that names the PR and the exact head SHA. Green CI, a bot reaction or a chat message is not approval.
- **Editing:** GPT and the owner edit priorities and add tasks; Claude updates statuses and evidence. Disagreements go to Issue #22, not into silent edits.

## Integration freshness (snapshot 2026-10-24 17:00 UTC, not a live count)

- Live `main` is `4ae19f49f480246a2b42a3e9457190d43f03db6b`. Push CI run 39990133096 on that exact SHA succeeded; its artifact `autopoesis-core-results` (3290 bytes) is present and not expired. Artifact contents not inspected.
- Open PRs: 15 in total. On `claude/` branches: #33, #34, #35, #36, #37, #40, #45 (7). On `gpt/` branches: #41–#44 and #46–#49 (8). The shared account means the branch prefix, not the GitHub author, marks the owner.
- The owner-approved limit (5 own PRs waiting) is exceeded: 7 `claude/` PRs are open. #40 and #45 were opened for the A13/A10 stack. No new PR opens until the owner merges or reconciles the count.
- Exact heads, CI and verdicts per PR: /mnt/project-files/reviews/AUDIT_PACK_2026-10-24.md (N9). #37 has moved since to `6521ddd` (CI 40102627023).

## Current blockers

| Blocker | Unblocks | Who |
|---|---|---|
| Codex verdict on #33 at `48c8fa52e0a0190f89ab6b641524f354cea9ee75` (CI 39997237027 success) | merge of #33 | GPT/Codex, then owner |
| Codex verdict on #34 at `c581ccbb7c9657fc727fa2d053b0ac7a4cf44f5b` (CI 39997237221 success) | merge of #34 | GPT/Codex, then owner |
| Codex verdict on #36 at `f6cd267e6a663349091cbd3d43b2c00eaa317cc4` (CI 39999531556 success) | merge of #36 | GPT/Codex, then owner |
| Codex verdict on #37 at `6521ddd55fe1c4c369c65834388d72bd6f240a6c` (CI 40102627023 success) | merge of #37 | GPT/Codex, then owner |
| No Codex receipt is bound to any of these heads (snapshot 2026-10-24 17:00 UTC); older receipts refer to older commits. CI success is not a verdict | all four rows above | GPT/Codex; verify receipts by exact SHA |
| Seven `claude/` PRs open (limit 5) | opening any new PR | owner merges or reconciles the count |

## NIGHT QUEUE

Owner-approved protocol (yarik, 2026-10-24 12:03 UTC). Claude's tick takes the top task whose status is TODO and whose dependencies are DONE. It marks the task IN_PROGRESS before starting and records DONE (with SHA, CI run and evidence) or BLOCKED (with the reason and what unblocks it). GPT may reorder or replace the TODO items at any time. No merge, no main, no production cycle run.

| ID | Task | Branch / PR | Depends on | Done criterion | Status |
|---|---|---|---|---|---|
| N1 | A30.58: the ci.yml restore harness can run a clean restore after an expected negative-fault run, without weakening the newest-run rule for real failures | #48 `gpt/a30-46-unfiltered-restore-history` | — | On one SHA, in sequence: seed → restore → fault → clean restore all behave as specified. A test proves that a newer real failure still refuses restore | DONE (Claude, 2026-10-24): `ab2c149`, PR CI 40095732798 success; dispatch chain on that SHA: seed 40095771383 success, restore 40095809449 success, fault `tamper_bytes` 40095848301 failure as expected (title "Negative restore fault: tamper_bytes"), clean restore 40098063122 success with the DONE probe intact. A newer real failure still refuses (`test_expected_negative_fault_failure_does_not_block_clean_restore`). Not audited |
| N2 | Integrate #46, #48 and #49 into A13 on a branch without a PR, to check the combined result | `claude/a13-integration` from A13 head | N1 | Merges without conflicts, full tests pass, ci.yml dispatch CI is green on the exact SHA, and a seed → restore pair succeeds on that SHA | DONE (Claude, 2026-10-24): `71271c7` = A13 `db22880` + #46 `5652238` + #48 `ab2c149` + #49 `81504a8`, no conflicts, 278 tests OK; dispatch seed 40098262350 success, restore latest 40098303951 success. No PR. Not audited |
| N3 | Design only: an owner-only way to acknowledge a failed production cycle run so the cycle can continue | `docs/` file on `claude/a13-integration` | — | Design document with a threat analysis and the tests it would need. No code until the owner decides | DONE as design (Claude, 2026-10-24): `docs/design/failed-run-acknowledgement.md` at `b2a2f5d` on `claude/a13-integration`. Waits for audit and the owner decision; no code |
| N4 | Refresh the #45 description with current exact-head CI and the merge order | #45 | — | The description lists exact SHAs and CI runs for #45, #40 and #46–#49 | DONE (Claude, 2026-10-24 13:50 UTC): #45 head `ba65d04` (CI 40040883201) unchanged; a "Current state" section was appended to the #45 description, with exact heads and CI for #45, #40, #46, #48 and #49, the integration check and the merge order |
| N5 | Verify the A13 integration branch: full HEAD SHA, which PR heads it contains, the full diff against #40, that `main` is untouched, and CI on that exact HEAD, including whether CI skips any restore step | `claude/a13-integration` | N2 | Published: full SHA, test and CI results, the list of included changes and the remaining blockers. No PR. Blocked if a PR head moved and the base is not agreed | DONE (Claude, 2026-10-24 14:15 UTC): HEAD `920627f` (code unchanged since `b2a2f5d`) contains #40 `db22880`, #46 `5652238`, #48 `ab2c149`, #49 `81504a8`; changed files equal the union of those PR diffs plus the N3/N8 doc; main `4ae19f4` untouched; CI dispatch 40099834376 success. PR and push CI skip every restore step (they run only on dispatch with restore_run_id), so restore is proven only by dispatch runs (N7). Remaining blockers: audit, owner merge |
| N6 | Check the hourly queue: schedule config, next-task selection, skipping BLOCKED, persistence between ticks, no repeat of DONE tasks, no duplicate changes. Handle timeout, cancel, the disabled cycle and a CI error, using tests and isolated branches only | trigger config, PLAN.md history, tests | — | Verifiable evidence for each case, and the schedule config confirmed. A cron entry alone is not proof | DONE (Claude, 2026-10-24 14:15 UTC; partial): `c30facd` adds tests/test_night_queue.py (CI 40099623539): IN_PROGRESS must name owner and date, no start before dependencies are DONE, DONE needs SHA and run ID, BLOCKED needs a reason, no duplicate IDs. It caught N4 DONE without a SHA (fixed). Trigger config read: cron `47 0-8,12,16,20-23 * * *`, enabled, one persistent session, last tick 12:47 succeeded. NOT PROVEN: a night of ticks under this protocol; timeout, cancel and CI-error handling are prompt rules, not tested code |
| N7 | Restore regression on the exact current SHA: seed → restore → tamper refusal → clean restore; restore uses the expected source run and artifact; refusals on bad history, source mismatch, re-run and incomplete artifact | `claude/a13-integration` | N5 | Every negative case refuses as expected and the clean restore passes. Run IDs and the SHA are recorded. No protection is weakened | DONE (Claude, 2026-10-24 14:10 UTC): on `b2a2f5d`: seed 40099523995, restore 40099551464, 6 fault runs 40099593978–40099706205 all refused at "Validate and install prior queue snapshot", fault without restore 40099720954 refused, clean restore after 7 fault runs 40099735638 success, explicit old seed 40099774937 refused, restore after a real failure 40099790468 refused. Re-run refusal is covered only by unit tests. Exact current HEAD `920627f` (after GPT's note on #35): seed 40100065949, restore 40100103580, bad_history 40100145969 refused, clean restore 40100171045 success |
| N8 | Finish the failed-run acknowledgement spec: exact format (run ID, workflow, SHA, reason, link to the restore that follows); reuse, stale SHA, ID substitution, several failures; the single-account limit | `docs/design/failed-run-acknowledgement.md` | N3 | Complete spec, test cases and one explicit question for the owner. No implementation and no `main` change before the owner decides | DONE as design (Claude, 2026-10-24 14:15 UTC): `docs/design/failed-run-acknowledgement.md` at `920627f`: format, exact matching on run/attempt/workflow/SHA/conclusion, required fallback run, reuse and staleness, single-account limit, 9 test cases and one owner question. No code |
| N9 | Prepare the independent audit: exact SHAs, diffs, tests and CI; check that earlier verdicts apply to current SHAs; PR dependency map and safe integration order | PRs #33–#49 | N5, N7 | Either an audit bound to the SHA exists, or its absence is recorded as a blocker. Own re-testing is not reported as audit. No merges | BLOCKED (Claude, 2026-10-24 14:15 UTC): no independent verdict on any current head (Codex usage limit; the only formal verdict, on #35, is for old `0b16c3f`). Audit pack with exact heads, CI, dependency map and order: /mnt/project-files/reviews/AUDIT_PACK_2026-10-24.md. Unblocked by a Codex or GPT verdict bound to the SHAs |
| N10 | Proposed by Claude: runtime proof that a re-run (run_attempt 2) of the newest dispatch run blocks the next restore; so far only unit tests cover it. Afterwards, re-seed the branch | `claude/a13-integration` | N7 | On `920627f`: a re-run of the newest successful run, then restore latest refuses with a run_attempt message; a new seed and restore succeed | DONE (Claude, 2026-10-24 17:00 UTC): on `920627f`: run 40100171045 re-run to attempt 2 (success); restore latest 40113357200 refused with "newest workflow_dispatch snapshot run 40100171045 must have run_attempt=1; got 2"; new seed 40113373506 and restore 40113420032 succeeded, so the branch is restorable again |
| N11 | Proposed by Claude: the emergency stop deadlocks the cycle. `autopoiesis-cycle.yml` stops a disabled run with a failing step (not a job-level skip), and #49's newest-run rule then refuses every later run after re-enabling. #49's skipped-run exemption rested on a wrong premise (Claude's error). Fix: mark disabled runs by run-name and let the selector skip only those that failed on attempt 1 | `claude/a13-disable-recovery` from `claude/a13-integration` | N10 | A test that fails before the fix: success → disabled failure → next run selects the success; a real failure still refuses; a "disabled" run that succeeded or was re-run refuses. CI on the exact SHA. Production behaviour needs main and stays NOT PROVEN | DONE (Claude, 2026-10-24 21:05 UTC): `03ed91d` on `claude/a13-disable-recovery` (no PR, limit); CI dispatch 40131596403 success, 280 tests. The deadlock was shown on the old selector (success → failure refuses both restore and bootstrap). Residual: if the owner flips the variable between run creation and the guard step, the title and the guard disagree and the run refuses fail-closed (needs the N8 acknowledgement). Production behaviour NOT PROVEN (main only). Not audited |
| N12 | Issue #50 E2E acceptance, one full cycle on a real task: land the N11 emergency-stop deadlock fix on PR #49 (whose skipped-run premise it corrects), because the open-PR limit forbids a new PR. Expected: a disabled run no longer blocks restore or bootstrap after re-enabling; real failures, re-runs and malformed history still refuse. Risk: run-name/guard race (fail-closed) | #49 `gpt/a13-scheduled-history-fail-closed` | N11 | Exact-head PR CI green; tests include the negative paths; an independent GPT/Codex verdict on the exact final head. Without that verdict the status stays PENDING_AUDIT | BLOCKED (Claude, 2026-10-25 00:40 UTC): PENDING_AUDIT. Implemented and tested at #49 head `0b6da38` (cherry-pick of `03ed91d`, base A13 `db22880`); PR CI 40146453034 success, 262 tests; negative paths covered. Audit requested on #49 (comment 6391373961, `@codex review` = today's single probe). Codex answered at 00:23 UTC with review status "failed" for `0b6da38` and "You have reached your Codex usage limits for code reviews" (comments 6391375877, 6391376264): no verdict. Unblocked by a GPT/Codex verdict on exact head `0b6da38` |

## Tasks

### P0 — A3 closed task lifecycle — `IN_REVIEW` (PR #33)
- **Goal:** only legal transitions; DONE only after a PASS for the item's own source since its latest IN_PROGRESS; no unchecked status writer.
- **Evidence so far:** at `8952df5`: PR CI 39931369279, seed 39931361330, restore 39931975513. Codex findings fixed since `74c3126`: stale verifier (attempt binding), PASS bound to the tested code revision, history edges replayed against the table on load, attempt counter checked against history, attempt type.
- **Remaining:** a Codex verdict on current HEAD `48c8fa52e0a0190f89ab6b641524f354cea9ee75`; owner merge; CI on the merge commit.

### P0 — A4 deterministic next-task selection — `IN_REVIEW` (PR #34)
- **Depends on:** #33.
- **Evidence so far:** at `480533b` (contains #33 `8952df5`): PR CI 39932079992. Codex found no major issues on `79e4692`; its P2 on `88e6671` (malformed priority) is fixed in `d9151ef`.
- **Remaining:** a Codex verdict on current HEAD `c581ccbb7c9657fc727fa2d053b0ac7a4cf44f5b`; after #33 merges, update the branch onto `main`, re-run CI, and get a verdict on the new head; owner merge.

### P1 — A9 task leases and recovery of stuck tasks — `IN_REVIEW` (PR #36, chained)
- **Depends on:** #34 (and therefore #33). Built on the #34 branch; if #33/#34 change, A9 is rebuilt.
- **Evidence so far:** at `4787a13` (contains #34 `480533b`): PR CI 39932167542, seed 39932159904, restore 39932194829. Codex P1s fixed: two live leases rejected on load; replayed PASS needs a revision and a lease token.
- **Additional change:** the runner now exposes a `renew_lease` task handler so an external supervisor can renew a live lease using its current token. This is a renewal entry point, not an automatic heartbeat; unattended renewal while work runs remains unproven.
- **Remaining:** CI on current HEAD `f6cd267e6a663349091cbd3d43b2c00eaa317cc4`; a Codex verdict on that exact SHA; owner confirmation of the `ci.yml` probe lines; merge after #34.
- **Design and test scenarios:** `/mnt/project-files/reviews/autonomous-stack/A9_LEASE_PLAN_2026-10-23.md`, summarized here.
- **Acceptance:**
  1. The lease owner, token and expiry are persisted, validated by `load_queue`, and survive restore.
  2. Acquire, renew, advance, verification and recovery run under the one queue lock.
  3. Two executors never hold unexpired leases at the same time.
  4. After expiry the old owner cannot renew, record evidence or write DONE with its stale token, even before recovery runs.
  5. Recovery returns expired items to OPEN with a `LEASE_EXPIRED` history event. With nothing expired, recovery leaves the file byte-identical.
  6. DONE still requires a fresh PASS for the item's source, recorded under the current lease.
  7. One test kills an executor process mid-task, lets the lease expire, starts a new executor, and shows the old one is refused.
- **Not proven by A9:** an unattended loop (A10/A11).

### P2 — Count Codex bot reviews as verdicts — `READY` (branch prepared, PR not opened)
- **Observed (2026-10-23):** PRs #20–#34 have no review from a Codex bot account. Every Codex post so far is an issue comment by the shared account with `performed_via_github_app = chatgpt-codex-connector`. Reviews are not read by `audit_verdict`.
- **Observed (2026-10-23 08:35 UTC):** commenting `@codex review` triggers a Codex review by `chatgpt-codex-connector[bot]` on the exact head (summary comment with `codex-review-state`, inline findings, 👍 when clean). First seen on #33 comment 6360909547. At 09:30 UTC it stopped with "You have reached your Codex usage limits for code reviews".
- **Independent of #33/#34/#36:** it touches only `autopoesis/audit_verdict.py`, its tests and `AGENTS.md`, branched from `main` `685c5a0`.
- **Acceptance:**
  1. A summary comment counts only from the bot account (`chatgpt-codex-connector[bot]`, id `199175422`, type `Bot`) through the auditor app.
  2. It counts only for `status: completed` and a `commit_sha` equal to the current head; an older head is `STALE_SHA`.
  3. Findings → `REJECTED`; no findings and nothing unresolved → `ACCEPTED`; anything else is no verdict.
  4. A human or the shared account pasting the marker counts for nothing; a running or failed review (usage limit) counts for nothing.
  5. The bot's verdict dates from the comment's last edit when compared with GPT verdicts.
- **Evidence:** branch `claude/cl-015-codex-review-verdict` at `f27cc15`, CI 39970453578 (workflow_dispatch) green; 8 new tests fail on `main`. On live #33/#34/#36 comments it returns `PENDING_AUDIT` (all bot reviews there are `failed`).
- **Blocked on opening the PR:** five own PRs are already waiting (limit 5). It changes the review rules in `AGENTS.md`, so it needs the owner's approval before merge.

### P3 — Coordination protocol and claim checker — `IN_REVIEW` (PR #32)
- **Evidence:** GPT ACCEPTED at `ce55344c091d7eb7b5b6e7ffb688918c630807e9` (comment 6302030182); CI 39501106634.
- **Remaining:** owner merge; then the scheduled loop reads the protocol from `main`.

### Backlog (not READY until acceptance criteria are written)
- **A10 status (CL-020, Claude):** started on branch `claude/cl-020-a10-cycle` at `762e87729c3734ea166e89c507a9538aeaeb88cb` (built on #36), per the owner's SEQ EXIT-MANUAL-MODE. No PR yet because of the open PR limit. Done: criteria 1–7 and 10 in `autopoesis/orchestrator.py` with tests in `tests/test_orchestrator.py`. Proven only by tests: locally and by CI `workflow_dispatch` runs on the branch (the latest is listed in Issue #22). No unattended run has happened. The budget is enforced by killing a stalled handler process. Not done: criterion 9 (artifact/restore of a cycle run) and 11 (periodic trigger), which need a workflow change and so the owner's permission; criterion 12 applies once a real run exists.
- A10 bounded orchestration: one scheduled run recovers, selects, executes, verifies and records one task, with budgets and a disable switch. **Depends on:** #33, #34, #36. These are proposed acceptance criteria, added by GPT for owner confirmation; A10 is not READY until the dependencies are integrated and the exact criteria are approved:
  1. The real runner performs one bounded cycle in order: recover expired leases → select one eligible task → transition it to IN_PROGRESS → execute only an explicitly supported handler → verify → persist PASS and DONE, or record failure and return the task to OPEN/REJECTED according to the retry policy. State changes and outcomes are recoverable from persisted history.
  2. The disable switch is checked before any queue mutation. A disabled run exits cleanly, reports the reason, and leaves the queue byte-identical.
  3. Budgets are enforced: at most one task per run and a fixed wall-clock limit. Timeout/interruption must not leave an unowned active task; recovery or release is idempotent and records why.
  4. Empty/no-eligible queue reports `no work`, exits successfully, and leaves the queue byte-identical.
  5. Executor/handler exceptions are persisted as failures, do not falsely record PASS/DONE, and do not prevent clean shutdown. Retry count and terminal rejection obey `MAX_ATTEMPTS`.
  6. Lease/token/attempt binding is preserved end-to-end. An expired or stale worker cannot verify, renew, or complete a task after recovery and reassignment; a duplicate/replayed run cannot apply a second completion.
  7. Two overlapping runs cannot both execute a task. A concurrency test starts two actual runner processes and proves only one obtains the lease and executes.
  8. CI exercises the actual runner cycle (not only a synthetic seed probe): full cycle, empty queue, handler failure, expired lease recovery, stale worker, duplicate/replay, timeout/bounded exit, and clean shutdown.
  9. Run output and queue history are persisted as artifacts and survive the existing restore path. Artifact persistence is evidence of storage only, not proof that an unattended schedule is firing.
  10. No network access, credentials, LLM calls, or arbitrary task-provided shell execution inside the core. Only allowlisted task handlers may execute.
  11. Add a periodic trigger only after the runner path passes the above tests; the trigger must be disableable, bounded, non-overlapping, and must not auto-merge or write to `main`.
  12. A fresh run must report exact source SHA, CI run ID, runtime outcome and artifact/restore evidence. Synthetic probes must be labelled synthetic and cannot be reported as production task execution.
- A Copilot test proposal for `autopoesis/task_queue.py` (run 39523564470) still awaits GPT's content audit.
