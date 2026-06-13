from __future__ import annotations

from pathlib import Path

from heddle.loomweave import (
    loomweave_entity_id_candidates,
    loomweave_resolve_qualnames,
    resolve_sei_for_locator,
)
from heddle.store import HeddleStore


class FakeClient:
    """Mirrors the REAL loomweave entity_resolve: bare dotted qualnames resolve,
    the prefixed/filesystem forms stay unresolved (HX1)."""

    def call_tool(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        assert name == "entity_resolve"
        assert arguments == {"qualnames": ["pkg.mod.fn", "python:function:pkg/mod.py::fn"]}
        return {
            "results": [
                {
                    "qualname": "pkg.mod.fn",
                    "result_kind": "resolved",
                    "candidates": [
                        {
                            "id": "python:function:pkg.mod.fn",
                            "sei": "loomweave:eid:opaque-value",
                        }
                    ],
                },
                {
                    "qualname": "python:function:pkg/mod.py::fn",
                    "result_kind": "unresolved",
                    "candidates": [],
                },
            ]
        }


def test_resolve_qualnames_are_bare_dotted_for_real_loomweave() -> None:
    assert loomweave_resolve_qualnames("python:function:src/heddle/store.py::S.fn") == [
        "heddle.store.S.fn",
        "src.heddle.store.S.fn",
        "python:function:src/heddle/store.py::S.fn",
    ]


def test_resolve_sei_for_locator_returns_opaque_value() -> None:
    assert (
        resolve_sei_for_locator(FakeClient(), "python:function:pkg/mod.py::fn")
        == "loomweave:eid:opaque-value"
    )


def test_loomweave_entity_id_candidates_translate_python_locators() -> None:
    assert loomweave_entity_id_candidates("python:function:pkg/mod.py::Class.fn") == [
        "python:function:pkg.mod.Class.fn",
        "python:function:pkg/mod.py::Class.fn",
    ]


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
