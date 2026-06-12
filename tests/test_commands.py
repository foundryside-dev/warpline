from __future__ import annotations

import json
from pathlib import Path

import pytest

from heddle import cli


def test_cli_changed_outputs_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert cli.main(["changed", "--repo", str(repo), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query"] == "changed"
    assert "changed" in payload
    assert "changed_entity_key_ids" in payload


def test_cli_timeline_outputs_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert cli.main(["timeline", "--repo", str(repo), "--entity", "file:a.py", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["query"] == "timeline"
    assert payload["entity"] == "file:a.py"
