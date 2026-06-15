from __future__ import annotations

import subprocess
from pathlib import Path

from warpline.store import WarplineStore, default_store_path


def test_default_store_path_uses_weft_member_runtime_tree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    path = default_store_path(repo)
    assert path == repo / ".weft" / "warpline" / "warpline.db"


def test_default_store_path_honors_explicit_store_dir(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    path = default_store_path(repo, base_dir=tmp_path / "state" / "warpline")
    assert path == tmp_path / "state" / "warpline" / "warpline.db"


def test_store_initializes_schema(tmp_path: Path) -> None:
    db = tmp_path / "warpline.db"
    with WarplineStore.open(db) as store:
        assert store.schema_version() == 3


def test_store_writes_nested_gitignore_that_ignores_runtime_db(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, text=True, capture_output=True)

    with WarplineStore.open(default_store_path(repo)) as store:
        assert store.schema_version() == 3

    gitignore = repo / ".weft" / "warpline" / ".gitignore"
    assert gitignore.exists()
    assert "warpline.db" in gitignore.read_text(encoding="utf-8")
    ignored = subprocess.run(
        ["git", "check-ignore", ".weft/warpline/warpline.db"],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    )
    assert ignored.stdout.strip() == ".weft/warpline/warpline.db"
