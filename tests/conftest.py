"""Shared test helpers.

`init_repo`/`commit` build a throwaway git repo with deterministic identity —
the fixture pattern the characterization and honesty-invariant suites both need.
Lifted here (round-2 conftest-helper minor) so test modules call one definition
instead of importing private helpers across files.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True, stdout=subprocess.PIPE
    ).stdout.strip()


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "agent@example.test")
    git(repo, "config", "user.name", "Agent")
    return repo


def commit(repo: Path, name: str, body: str) -> str:
    (repo / name).write_text(body, encoding="utf-8")
    git(repo, "add", name)
    git(repo, "commit", "-m", f"write {name}")
    return git(repo, "rev-parse", "HEAD")
