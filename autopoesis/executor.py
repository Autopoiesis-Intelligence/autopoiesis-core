"""Replaceable, bounded code-writing adapters that emit reviewable patch artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .core import canonical_json


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


@dataclass(frozen=True)
class PatchFile:
    path: str
    content: str
    sha256: str


@dataclass(frozen=True)
class WriterResult:
    status: str
    writer_id: str
    task_id: str
    files: tuple[PatchFile, ...]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "writer_id": self.writer_id,
            "task_id": self.task_id,
            "files": [
                {"path": item.path, "content": item.content, "sha256": item.sha256}
                for item in self.files
            ],
            "rationale": self.rationale,
        }


class CodeWriter(Protocol):
    """Provider-neutral contract: produce a patch artifact, never execute it."""

    writer_id: str

    def prepare(self, task: dict[str, Any], repository_root: Path) -> WriterResult:
        """Return proposed files without modifying the repository."""


class BoundedTestScaffoldWriter:
    """Generate a minimal import-smoke-test patch for one supported Python module."""

    writer_id = "bounded-test-scaffold-v1"

    def prepare(self, task: dict[str, Any], repository_root: Path) -> WriterResult:
        task_id = task.get("id")
        source_value = task.get("source")
        if not isinstance(task_id, str) or not _SAFE_ID.fullmatch(task_id):
            raise ValueError("Task id contains unsupported characters")
        if not isinstance(source_value, str) or not source_value.endswith(".py"):
            raise ValueError("Task source must be a Python file path")

        source_path = Path(source_value)
        if source_path.is_absolute() or ".." in source_path.parts:
            raise ValueError("Task source must stay inside the repository")
        if not source_value.startswith("autopoesis/") or source_path.name == "__init__.py":
            raise ValueError("Writer only supports non-package Python modules under autopoesis/")
        resolved_root = repository_root.resolve()
        resolved_source = (resolved_root / source_path).resolve()
        if resolved_root not in resolved_source.parents or not resolved_source.is_file():
            raise ValueError("Task source does not resolve to an existing repository file")

        test_path = Path("tests") / f"test_{source_path.stem}.py"
        resolved_test = (resolved_root / test_path).resolve()
        if resolved_root not in resolved_test.parents:
            raise ValueError("Generated test path escapes the repository")
        if resolved_test.exists():
            raise ValueError(f"Refusing to overwrite existing test file: {test_path.as_posix()}")

        module_name = ".".join(source_path.with_suffix("").parts)
        test_content = (
            f'"""Generated import smoke test for {module_name}."""\n\n'
            "import importlib\n"
            "import unittest\n\n\n"
            "class GeneratedImportSmokeTest(unittest.TestCase):\n"
            "    def test_module_imports(self):\n"
            f"        module = importlib.import_module({module_name!r})\n"
            "        self.assertIsNotNone(module)\n\n\n"
            'if __name__ == "__main__":\n'
            "    unittest.main()\n"
        )
        digest = hashlib.sha256(test_content.encode("utf-8")).hexdigest()
        return WriterResult(
            status="PATCH_PREPARED",
            writer_id=self.writer_id,
            task_id=task_id,
            files=(PatchFile(path=test_path.as_posix(), content=test_content, sha256=digest),),
            rationale=(
                "Generated one deterministic import-smoke-test file for an existing module. "
                "The source tree was not modified; review and verification are still required."
            ),
        )



def validate_patch_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    """Validate hashes, generated-file scope, and Python syntax without executing code."""
    if not isinstance(artifact, dict):
        raise ValueError("Patch artifact must be an object")
    claimed_artifact_hash = artifact.get("artifact_sha256")
    if not isinstance(claimed_artifact_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", claimed_artifact_hash):
        raise ValueError("Patch artifact has no valid artifact_sha256")

    unsigned_payload = dict(artifact)
    unsigned_payload.pop("artifact_sha256", None)
    unsigned_payload.pop("validation", None)
    actual_artifact_hash = hashlib.sha256(canonical_json(unsigned_payload).encode("utf-8")).hexdigest()
    if actual_artifact_hash != claimed_artifact_hash:
        raise ValueError("Patch artifact checksum mismatch")

    files = artifact.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("Patch artifact must contain at least one file")

    seen_paths: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("Each patch file must be an object")
        path_value = item.get("path")
        content = item.get("content")
        claimed_hash = item.get("sha256")
        if not isinstance(path_value, str) or not isinstance(content, str):
            raise ValueError("Patch file path and content must be strings")
        path = Path(path_value)
        if path.is_absolute() or ".." in path.parts or path.as_posix() != path_value:
            raise ValueError("Patch file path must be normalized and repository-relative")
        if len(path.parts) != 2 or path.parts[0] != "tests" or not path.name.startswith("test_") or path.suffix != ".py":
            raise ValueError("Patch writer may only propose tests/test_*.py files")
        if path_value in seen_paths:
            raise ValueError("Patch artifact contains duplicate file paths")
        seen_paths.add(path_value)
        actual_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if claimed_hash != actual_hash:
            raise ValueError(f"Patch file checksum mismatch: {path_value}")
        try:
            # Compile the bytes that will be written, so a coding declaration is honoured here too.
            compile(content.encode("utf-8"), path_value, "exec")
        except SyntaxError as exc:
            raise ValueError(f"Generated Python has invalid syntax: {path_value}: {exc.msg}") from exc
        except (MemoryError, RecursionError) as exc:
            raise ValueError(f"Generated Python is too complex to parse: {path_value}") from exc

    return {
        "status": "VALID",
        "files_checked": len(files),
        "artifact_sha256": actual_artifact_hash,
        "checks": ["artifact_sha256", "file_sha256", "allowed_path", "unique_paths", "python_syntax"],
        "execution_performed": False,
    }


def apply_patch_to_sandbox(artifact: dict[str, Any], sandbox_root: Path) -> dict[str, Any]:
    """Apply a validated patch only inside an explicit disposable workspace; never overwrite."""
    validation = validate_patch_artifact(artifact)
    root = sandbox_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not root.is_dir():
        raise ValueError("Sandbox root must be a directory")

    targets: list[tuple[Path, str, str]] = []
    for item in artifact["files"]:
        relative = Path(item["path"])
        target = root / relative
        if relative.parts[0] != "tests" or target.parent.is_symlink():
            raise ValueError("Sandbox target directory must not be a symlink")
        resolved_target = target.resolve()
        if root not in resolved_target.parents:
            raise ValueError("Patch target escapes sandbox root")
        if target.exists():
            raise ValueError(f"Refusing to overwrite sandbox file: {relative.as_posix()}")
        targets.append((target, item["content"], relative.as_posix()))

    created: list[Path] = []
    try:
        for target, content, _relative in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf-8", newline="") as stream:
                stream.write(content)
            created.append(target)
    except Exception:
        for path in reversed(created):
            try:
                path.unlink()
            except OSError:
                pass
        raise

    return {
        "status": "APPLIED_TO_SANDBOX",
        "files_written": [relative for _target, _content, relative in targets],
        "artifact_sha256": validation["artifact_sha256"],
        "repository_modified": False,
        "generated_code_executed": False,
    }

def source_tree_digest(package: Path) -> str:
    """SHA-256 over the relative paths and contents of a package's files, ignoring bytecode caches."""
    digest = hashlib.sha256()
    files = sorted(
        path for path in package.rglob("*")
        if path.is_file() and "__pycache__" not in path.relative_to(package).parts
    )
    for path in files:
        digest.update(path.relative_to(package).as_posix().encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii") + b"\n")
    return digest.hexdigest()


def verify_test_patch_in_sandbox(
    task: dict[str, Any],
    repository_root: Path,
    timeout_seconds: int = 10,
) -> dict[str, Any]:
    """Execute only the generated import test in a disposable copy of the package."""
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 30:
        raise ValueError("Sandbox test timeout must be between 1 and 30 seconds")

    root = repository_root.resolve()
    source_package = root / "autopoesis"
    if source_package.is_symlink():
        raise ValueError("Refusing to copy a symlinked source package")
    if not source_package.is_dir():
        raise ValueError("Required autopoesis package is missing")
    resolved_package = source_package.resolve()
    if root not in resolved_package.parents:
        raise ValueError("Source package must resolve inside the repository root")
    for path in source_package.rglob("*"):
        if path.is_symlink():
            raise ValueError("Refusing to copy a source package containing symlinks")

    artifact = prepare_patch_artifact(task, root)
    with tempfile.TemporaryDirectory(prefix="autopoesis-verify-") as directory:
        workspace = Path(directory)
        shutil.copytree(source_package, workspace / "autopoesis", symlinks=True)
        tested_revision = source_tree_digest(workspace / "autopoesis")
        (workspace / "tests").mkdir()
        application = apply_patch_to_sandbox(artifact, workspace)
        generated_path = artifact["files"][0]["path"]
        child_env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(workspace),
        }
        common_result = {
            "generated_test": generated_path,
            "timeout_seconds": timeout_seconds,
            "artifact_sha256": artifact["artifact_sha256"],
            "source_tree_sha256": tested_revision,
            "sandbox_application": application,
            "source_package_copied": True,
            "repository_modified": False,
            "generated_code_executed": True,
            "execution_boundary": "only the bounded generated import test in a temporary copied package",
            "child_environment": "minimal allowlist; parent environment and credentials are not inherited",
            "sandbox_lifetime": "temporary; removed after the task",
        }
        try:
            completed = subprocess.run(
                [
                    sys.executable, "-m", "unittest", "discover",
                    "-s", "tests", "-p", Path(generated_path).name, "-v",
                ],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                env=child_env,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            return {
                **common_result,
                "verification_status": "FAIL",
                "failure_reason": "TIMEOUT",
                "return_code": None,
                "stdout": stdout[-4000:],
                "stderr": stderr[-4000:],
            }

        passed = completed.returncode == 0
        return {
            **common_result,
            "verification_status": "PASS" if passed else "FAIL",
            "failure_reason": None if passed else "TEST_FAILURE",
            "return_code": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }


def prepare_patch_artifact(
    task: dict[str, Any],
    repository_root: Path,
    writer: CodeWriter | None = None,
) -> dict[str, Any]:
    """Create a deterministic JSON patch artifact; do not apply or execute it."""
    selected_writer = writer or BoundedTestScaffoldWriter()
    result = selected_writer.prepare(task, repository_root)
    payload = result.to_dict()
    payload["artifact_sha256"] = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    payload["validation"] = validate_patch_artifact(payload)
    return payload
