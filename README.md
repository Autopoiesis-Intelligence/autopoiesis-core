# autopoesis-core

Autopoiesis is intended to become a universal, bounded self-evolving system whose domain model is the state and relations Ψ=(X,R). Software development is the first experimental domain, not the product boundary.

**Important:** the repository currently implements an early, file-driven software-development slice. It does not yet implement or prove the full target architecture, general-domain operation, self-directed evolution, sustained autonomy or federation.

## Architecture

- [Target architecture](docs/architecture/TARGET_ARCHITECTURE.md)
- [Repository restructuring plan](docs/architecture/REPOSITORY_RESTRUCTURE.md)
- [Architecture decision register](docs/architecture/DECISION_REGISTER.md)
- [Autonomy roadmap and acceptance gates](docs/AUTONOMY_ROADMAP_SPEC.md)

The trusted core is intended to remain deterministic and small. Network access, credentials, LLM/provider calls, GitHub, CI, scheduling and external execution belong behind replaceable adapters. Proposals, selection, verification, authorization, execution, commit and merge remain separate. See AGENTS.md for binding repository policy.

## Current implementation

- Deterministic JSON state digest using SHA-256 for content identity.
- A small state transition operation that accepts a meaningful change and rejects a no-op.
- Explicit bounded task types rather than arbitrary shell or Python execution from task data.
- Machine-readable task results.
- Static discovery of TODO/FIXME/HACK markers and source modules without conventional tests.
- A JSON task queue with stable candidate IDs, duplicate suppression, lifecycle statuses, attempt counts, status history and persisted verification-evidence records.
- Queue updates use a same-directory temporary file and atomic replacement.
- A replaceable CodeWriter interface and a bounded built-in writer that prepares a deterministic import-test patch artifact for an eligible Python module.
- Standard-library-only tests and CI.

These capabilities are components of an early implementation. They do not by themselves constitute the complete evolution engine or prove autonomy.

## Operating model

1. Put bounded tasks in TASKS.json.
2. Run python run_tasks.py.
3. Inspect task outcomes in RESULTS.json.

The core has no user accounts, internal authorization framework, network service, external dependencies or required API credentials.

## CI and result files

Every push to main and every pull request runs tests and the task runner on Python 3.12. The workflow uploads generated RESULTS.json and TASK_QUEUE.json as the autopoesis-core-results artifact.

To inspect a run, open [GitHub Actions](https://github.com/Autopoiesis-Intelligence/autopoiesis-core/actions), select the run, and download the artifact from its Artifacts section. Generated execution files are artifacts, not committed source files. When running locally, TASK_QUEUE.json remains on disk between runs. Each GitHub Actions run starts from a clean checkout.

To restore a prior snapshot in CI, manually start the CI workflow with restore_run_id set to the numeric ID of a prior successful run from this repository's .github/workflows/ci.yml workflow. Before downloading its artifact, the workflow verifies that the source run concluded successfully and belongs to the expected repository/workflow. It requires exactly one unexpired autopoesis-core-results artifact bound to that run and records the artifact ID, archive digest, size and creation time in QUEUE_RESTORE_PROVENANCE.json.

Each uploaded artifact also contains QUEUE_SNAPSHOT_MANIFEST.json, which binds the queue file's SHA-256 and size to the producing run ID, repository and commit SHA. During restore, the workflow checks the manifest's run ID and commit SHA against the verified source run, recomputes the queue file SHA-256, validates it using the queue loader and only then installs it for the task runner. These checks establish run binding and internal consistency, not a cryptographic signature: the queue and its manifest are members of the same artifact, so a party able to replace both can recompute the manifest. The artifact archive digest is recorded from GitHub metadata but is not independently recomputed by this workflow. If the source run was unsuccessful, the artifact or queue file is missing, or the queue is invalid, the restore run fails instead of silently starting with an empty queue. Runs without restore_run_id retain clean-checkout behavior.

For an explicit two-run persistence check, start the first run with seed_done_probe=true; then start a second run with that first run's numeric ID as restore_run_id. Any restore run requires both the synthetic DONE status/history and a synthetic verification-evidence record. Ordinary CI runs skip these cross-run probes. A normal PR CI run that skips seed and restore does not prove cross-run persistence.

## Important execution boundary

This runner executes only task types implemented in run_tasks.py. A task description alone cannot cause the program to invent and write new code. The prepare_test_patch task generates a reviewable patch artifact for one narrow case: adding an import-smoke test for an existing module under autopoesis/. It does not modify source files, apply patches or run generated code.

apply_test_patch_sandbox writes a validated patch only into an explicit disposable sandbox and does not execute it. verify_test_patch_sandbox copies the package into a temporary workspace and executes only the generated import-smoke test with a bounded timeout. Importing the package can execute its top-level Python code, so this is a bounded temporary workspace, not a hardened security sandbox. The task reports verification evidence separately and does not automatically mark the queued task DONE. Generated patches are not applied to repository source files automatically.

A future external or local model can implement the same CodeWriter interface without changing the core task contract.

## Run and test

\`\`\`bash
python run_tasks.py
python -m unittest discover -s tests -v
\`\`\`

Edit TASKS.json to configure work. queue_discovered_tasks merges newly discovered candidates into TASK_QUEUE.json without duplicating existing IDs or overwriting statuses. update_task_status persists a lifecycle change. The default CORE-005 task prepares a patch artifact for autopoesis/task_queue.py; CORE-006 applies the patch in a disposable temporary sandbox. Additional prepare_test_patch tasks can target eligible modules by specifying an id and source path. The runner replaces RESULTS.json on each run so it represents the latest run. Use python run_tasks.py --queue path/to/TASK_QUEUE.json to choose a queue file.
