"""Helpers for tests that need a git repository the coordinator can snapshot."""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=test", "-c", "user.email=test@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def make_repository(root):
    """A git repository holding a copy of autopoesis/ in one commit; returns (commit, tree)."""
    shutil.copytree(ROOT / "autopoesis", root / "autopoesis", ignore=shutil.ignore_patterns("__pycache__"))
    git(root, "init", "-q")
    git(root, "add", "autopoesis")
    git(root, "commit", "-q", "-m", "fixture")
    return git(root, "rev-parse", "HEAD"), git(root, "rev-parse", "HEAD^{tree}")
