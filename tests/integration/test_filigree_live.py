from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from warpline import commands
from warpline.siblings import DEFAULT_FILIGREE_API_URL, FiligreeWorkClient
from warpline.store import WarplineStore, default_store_path

WARPLINE_REPO = Path(__file__).resolve().parents[2]
LIVE_SEI_ENV = "WARPLINE_LIVE_FILIGREE_SEI"
LIVE_ISSUE_ENV = "WARPLINE_LIVE_FILIGREE_ISSUE_ID"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True, stdout=subprocess.PIPE
    ).stdout.strip()


def _filigree_base_url() -> str:
    return os.environ.get("FILIGREE_API_URL", DEFAULT_FILIGREE_API_URL).rstrip("/")


def _require_live_binding() -> tuple[str, str, str]:
    base_url = _filigree_base_url()
    sei = os.environ.get(LIVE_SEI_ENV)
    issue_id = os.environ.get(LIVE_ISSUE_ENV)
    if not sei or not issue_id:
        pytest.skip(
            f"set {LIVE_SEI_ENV} and {LIVE_ISSUE_ENV} for live filigree work-state proof"
        )
    try:
        with urllib.request.urlopen(f"{base_url}/api/health", timeout=2) as response:
            if response.status != 200:
                pytest.skip(f"filigree dashboard unhealthy: HTTP {response.status}")
    except (OSError, urllib.error.URLError) as exc:
        pytest.skip(f"filigree dashboard unavailable at {base_url}: {exc}")
    return base_url, sei, issue_id


def test_live_filigree_work_state_enriches_reverify_worklist(tmp_path: Path) -> None:
    base_url, sei, issue_id = _require_live_binding()

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "agent@example.test")
    _git(repo, "config", "user.name", "Agent")
    (repo / "a.py").write_text("a = 1\n", encoding="utf-8")
    _git(repo, "add", "a.py")
    _git(repo, "commit", "-m", "init")
    head = _git(repo, "rev-parse", "HEAD")

    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        key = store.ensure_entity_key(
            repo_id,
            locator="python:function:a.py::a",
            sei=sei,
            commit_sha=head,
        )

    env = commands.reverify_worklist(
        repo,
        [key],
        depth=2,
        include_federation=True,
        work_client=FiligreeWorkClient(repo, base_url=base_url),
    )

    member = env["data"]["federation"]["members"]["filigree"]
    assert member["weft_reason"]["reason_class"] == "clean"
    assert env["enrichment"]["work"] == "present"
    assert env["data"]["next_actions"]["filigree"][0]["issue_id"] == issue_id
    item = env["data"]["items"][0]
    work = item["enrichment"]["work"][0]
    assert work["issue_id"] == issue_id
    assert work["issue_status"]
    assert work["claim_state"] is not None
    # The association is served by the dashboard HTTP route, not a fixture.
    with urllib.request.urlopen(
        f"{base_url}/api/entity-associations?entity_id={sei}", timeout=2
    ) as response:
        payload = json.loads(response.read().decode("utf-8"))
    assert any(row.get("issue_id") == issue_id for row in payload["associations"])
