# E4.7 — Attempt-bound verification implementation

**Implementation branch:** `gpt/e4-attempt-bound-verification-2026-10-27`
**Parent review branch:** `gpt/e4-trust-boundaries-2026-10-27`
**Scope:** Local task queue evidence handling only. This is not runtime isolation or trusted CI provenance.

## Change

- Verification writes bind to the attempt count only when exactly one queue item has the same ID; duplicate matches are rejected.
- Standalone verification tasks and unknown IDs may still write informational evidence with `attempt: null`. Such unbound records cannot authorize a queue task's `DONE` transition.
- Queue-bound verification history events record the task's current integer `attempts` count.
- A transition to `DONE` now requires the latest verification to be `PASS` and its recorded attempt to equal the task's current attempt count.
- Tests cover unknown task IDs and stale PASS reuse after a new attempt begins.

## Security limit

The attempt number is a local consistency guard, not an unforgeable identity. Any verification record without a unique matching queue item is informational only (`attempt: null`) and is not accepted as queue-task completion evidence. Code that can modify the queue or call the helper can still create a PASS for the current attempt. This change does not bind evidence to a source SHA, workflow run, trusted verifier, or independently validated artifact. Those remain unresolved.

## Evidence status

Implementation is on a feature branch and requires CI. No claim of runtime isolation or E4 completion is made. Keep E4 **BLOCKED / NOT PROVEN** until the remaining trust/provenance controls and applicable adversarial runtime tests are demonstrated.
