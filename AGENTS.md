# AGENTS.md: rules for every agent working on this repository

This is the single policy file for humans and AI agents (Claude, GPT, Copilot, Manus and others). `CLAUDE.md` and `.github/copilot-instructions.md` only point here. Change the policy here, not in copies.

## What this repository is

`autopoiesis-core` restarts the Gnosis core. Its goal is to prove one minimal, closed, bounded self-development loop, stage by stage (A0–A12 in `docs/AUTONOMY_ROADMAP_SPEC.md`, introduced by PR #13). Capabilities from the older Gnosis repositories are added only after the stage that needs them is proven.

Product goal (owner decision, 2026-10-19): the system changes its own state and relations, Ψ=(X,R), within delegated authority. Code changes are one kind of change, not the goal itself. This is a goal, not a proven property.

## Non-negotiable rules

1. **Evidence is not authority.** A passing test, a hash or green CI never by itself authorizes a change to the core, a merge or a release.
2. **Goal ≠ implemented ≠ proven.** Use the evidence ladder for every claim and name the level:
   - `DESIGN`: documented;
   - `IMPLEMENTED`: code exists at an exact SHA;
   - `REACHABLE`: a runner or workflow path can invoke it;
   - `RUNTIME`: an execution was observed;
   - `PERSISTED`: it survives restart or restore;
   - `AUDITED`: negative cases were reviewed;
   - `CI_PROVEN`: relevant CI passed on the exact SHA.
3. **Exact SHAs.** Every claim about state names the commit SHA, plus the CI run id or artifact where relevant. Evidence from one SHA does not carry over to another, or from another repository.
4. **Fail closed.** Missing, malformed, stale, contradictory or unverifiable state or evidence stops the step. It never silently becomes an empty queue, a PASS or progress.
5. **No-op is not progress.** Synthetic fixtures are labelled synthetic. Progress means accepted, independently verified changes.
6. **Keep these distinct:** selection, verification, authorization, execution, commit and merge. One must never be inferred from another.
7. **Trusted core stays small:** Python 3.12 standard library only. No network calls, credentials or LLM calls inside the core. No arbitrary shell, `eval` or `exec` driven by task or queue data. Only the bounded task types in `run_tasks.py`.
8. **Never weaken a check to get green.** Never skip, disable or loosen a test, an invariant or a CI gate to make a run pass. Rejections and failures are kept as history.

## Autonomy levels

Each roadmap stage must state which level its acceptance criteria actually prove, and what remains unproven.

- **L1:** the system finds a problem on its own.
- **L2:** it proposes and checks a fix on its own.
- **L3:** it executes an authorized change on its own, in a bounded environment.
- **L4:** it governs its own development within pre-set authority, remaining verifiable, refusable and reversible.

Proving L1–L2 does not prove L3–L4. The agents' development loop (agents writing PRs) is not evidence of the product's autonomy.

## How to make a change

- Work on a branch and open a PR. `main` is protected by the ruleset `main-protection`: a PR and the `test` check are required, and force-push and deletion are blocked.
- Make one bounded change per PR. Tests come first or together with the change.
- Run the checks locally before pushing:
  ```bash
  python -m unittest discover -s tests -v
  python run_tasks.py
  ```
  Generated `RESULTS.json` and `TASK_QUEUE.json` are run artifacts. Do not commit them.
- Changes to `.github/workflows/`, permissions, secrets or repository settings need the owner's explicit approval for that change.
- Claims, handoffs and takeovers between agents follow `docs/coordination/PROTOCOL.md`.
- Agents do not merge their own PRs. A merge needs green CI on the exact head **and** an independent review, meaning not the author agent.

**Open PR limit (owner decision, 2026-10-23).** This is the only place the limit is set; other documents and prompts point here.
- At most 5 open PRs per agent wait for audit or merge. Every kind counts: code, docs and cleanup. Draft PRs count too.
- At the limit, an agent opens no new PR. It keeps open PRs current (verdicts, labels, rebases after a merge) and may continue the next independent task from the plan on a branch without a PR (owner, SEQ EXIT-MANUAL-MODE, 2026-10-23). Finished branches without a PR wait until a slot frees, oldest first.
- Merge order: the oldest `ready-for-owner` PR first. When a PR becomes `ready-for-owner`, the author agent tells the owner which PR is next, with its exact head SHA.
- The reason is cost: every open PR is rechecked on each tick, rebased after each merge, and needs a new audit after each push. Work queued ahead of the merge goes stale and is redone.

## Review and audit

An audit is an independent review of one exact head SHA. CI does not replace it, and it does not replace CI.

**Verdict format.** An auditor posts a PR comment whose body starts with this block. An `Agent:` line may come first.

```
Verdict: ACCEPTED | REJECTED
pr: <PR number>
head_sha: <40-character SHA of the PR head that was audited>
```

Reasons follow after a blank line. A verdict counts only when all of these hold:
- the block opens the comment;
- `pr` is this PR;
- `head_sha` is the PR's current head;
- GitHub's `performed_via_github_app` has the id and slug of an authorized auditor app (today id `1144995`, slug `chatgpt-codex-connector`, the ChatGPT Codex Connector). The display name is not checked.

The `Agent:` text line identifies the writer, but it is not proof of authorship. A verdict that fails any check is ignored and does not change the PR's state.

**Labels and transitions.** The state is recomputed from all comments on every check. A repeated or late event therefore changes nothing.

| State | Labels | When |
|---|---|---|
| Pending audit | `pending-audit` | no valid verdict for the current head |
| Blocked review | `blocked-review` | the newest valid verdict for the current head is `REJECTED` |
| Ready for owner | `ready-for-owner` | the newest valid verdict for the current head is `ACCEPTED` and CI is green on that head |
| Accepted, CI not green | none of these labels | the newest valid verdict is `ACCEPTED`, but CI on that head is missing or red |
| Audit overdue | `pending-audit`, `audit-overdue` | still pending more than 7 days after the current head was committed |

- A new push changes the head, so every earlier verdict becomes stale: `ready-for-owner` and `blocked-review` are removed and the PR returns to `pending-audit`.
- A rejected PR comes back only as a new head with a new audit. The old verdict stays in the history.
- `ready-for-owner` never authorizes a merge by itself. Only the owner merges.

**Overdue notification.** When `notify_owner` is true, the Claude development loop sends the owner one message in the project thread through `apply_audit_result`. Only after that message is sent does it add `audit-overdue`. The label records that the notification went out, so later checks see it and do not notify again. The label on its own is not a notification. Without the loop, nobody is notified.

The order is deliberate. If the loop stops between sending the message and adding the label, the next check sends the message again. A failure can therefore duplicate a notification but can never lose it. The opposite order (label first) would turn a failed send into a silent miss. Delivery is at least once, not exactly once.

**Enforcement.** `autopoesis/audit_verdict.py` computes the state and the label changes from the PR facts and comments. It makes no network calls. Today the Claude development loop applies the result. Until real GitHub events have been observed end to end, audit state is checked by an agent, not automated by the repository.

**No retroactive verdicts.** Free-text audits posted before this format, for example in Issue #22, are not verdicts. They are never converted, and they authorize nothing.

## Report format

End each unit of work with:
- **BEFORE:** repo, branch, head and base SHA, relevant PRs and runs.
- **ACTION:** exact changes, files, commands and workflows run, and what was deliberately not done.
- **AFTER:** final SHA, diff or PR URL, test output, CI run id with its `head_sha` and conclusion.
- **RESULT:** separately, what is implemented, reachable, executed and persisted.
- **PROVEN / NOT PROVEN:** each claim with its evidence, or the reason evidence is missing.
- **REJECTED DIRECTIONS:** failed approaches and environment limits.
- **NEXT SEQ:** one next step, with acceptance criteria and the permissions it needs.

## Known naming quirk

The package directory is spelled `autopoesis/`, while the repository is `autopoiesis-core`. Renaming it is a separate, pending owner decision. Do not rename it as a side effect of other work.
