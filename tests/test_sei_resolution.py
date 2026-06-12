from __future__ import annotations

from pathlib import Path

from heddle.loomweave import resolve_sei_for_locator
from heddle.store import HeddleStore


class FakeClient:
    def call_tool(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        assert name == "entity_resolve"
        assert arguments == {"qualnames": ["python:function:pkg.mod::fn"]}
        return {
            "results": [
                {
                    "qualname": "python:function:pkg.mod::fn",
                    "result_kind": "resolved",
                    "candidates": [
                        {
                            "id": "python:function:pkg.mod::fn",
                            "sei": "loomweave:eid:opaque-value",
                        }
                    ],
                }
            ]
        }


def test_resolve_sei_for_locator_returns_opaque_value() -> None:
    assert (
        resolve_sei_for_locator(FakeClient(), "python:function:pkg.mod::fn")
        == "loomweave:eid:opaque-value"
    )


def test_resolve_sei_for_locator_degrades_when_absent() -> None:
    class MissingClient:
        def call_tool(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
            return {
                "results": [
                    {
                        "qualname": "python:function:pkg.mod::fn",
                        "result_kind": "unresolved",
                        "candidates": [],
                    }
                ]
            }

    assert resolve_sei_for_locator(MissingClient(), "python:function:pkg.mod::fn") is None


def test_resolve_sei_for_locator_accepts_legacy_entity_payload() -> None:
    class LegacyClient:
        def call_tool(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
            return {
                "entity": {
                    "id": "python:function:pkg.mod::fn",
                    "sei": "loomweave:eid:legacy-value",
                }
            }

    assert (
        resolve_sei_for_locator(LegacyClient(), "python:function:pkg.mod::fn")
        == "loomweave:eid:legacy-value"
    )


def test_store_persists_sei_without_parsing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with HeddleStore.open(tmp_path / "heddle.db") as store:
        repo_id = store.ensure_repo(repo)
        key_id = store.ensure_entity_key(
            repo_id,
            locator="python:function:pkg.mod::fn",
            sei="loomweave:eid:opaque-value",
            commit_sha="c1",
        )
        events = store.list_entity_keys(repo)
    assert events[0]["id"] == key_id
    assert events[0]["sei"] == "loomweave:eid:opaque-value"
