# E4.7 — Attempt-bound verification implementation

**Implementation branch:** `gpt/e4-attempt-bound-verification-2026-10-27`
**Parent review branch:** `gpt/e4-trust-boundaries-2026-10-27`
**Scope:** Local task queue evidence handling only. This is not runtime isolation or trusted CI provenance.

## Change

- Verification writes now require exactly one existing queue item with the specified task ID.
- Each verification history event records the task's current integer `attempts` count.
- A transition to `DONE` now requires the latest verification to be `PASS` and its recorded attempt to equal the task's current attempt count.
- Tests cover unknown task IDs and stale PASS reuse after a new attempt begins.

## Security limit

The attempt number is a local consistency guard, not an unforgeable identity. Code that can modify the queue or call the helper can still create a PASS for the current attempt. This change does not bind evidence to a source SHA, workflow run, trusted verifier, or independently validated artifact. Those remain unresolved.

## Evidence status

Implementation is on a feature branch and requires CI. No claim of runtime isolation or E4 completion is made. Keep E4 **BLOCKED / NOT PROVEN** until the remaining trust/provenance controls and applicable adversarial runtime tests are demonstrated.
