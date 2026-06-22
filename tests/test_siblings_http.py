"""FiligreeWorkClient consumes filigree's HTTP entity-association + issue surface.

GAP A fix (weft federation seam 2 inbound): filigree's ADR-029 SEI reverse-lookup
(``entity_association_list_by_entity``) and ``issue_get`` exist ONLY on filigree's
MCP/HTTP surface — there is no ``filigree`` CLI verb for either (the prior CLI
implementation called phantom ``entity-associations`` / ``get`` verbs). warpline
therefore reads them over filigree's HTTP API.

Enrich-only honesty (PDR-0023): an HTTP 200 with no bindings is earned-empty
(``[]``), never an error; a genuine transport failure (dashboard unreachable,
timeout, non-200) RAISES so reverify's federation consult surfaces filigree as
``unreachable`` instead of a confident-empty.
"""

from __future__ import annotations

import json
import urllib.error
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from warpline import siblings
from warpline.siblings import FiligreeWorkClient, work_enrichment_for_sei


class _FakeResponse:
    """Minimal stand-in for the urlopen context-manager response."""

    def __init__(self, payload: Any, status: int = 200) -> None:
        self._body = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _patch_urlopen(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[Any], Any]
) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def fake_urlopen(req: Any, timeout: Any = None) -> Any:
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        return handler(req)

    monkeypatch.setattr(siblings.urllib.request, "urlopen", fake_urlopen)
    return captured


def test_associations_parses_http_200_associations_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FiligreeWorkClient(Path("/repo"), base_url="http://localhost:8724")
    cap = _patch_urlopen(
        monkeypatch,
        lambda req: _FakeResponse(
            {
                "associations": [
                    {
                        "issue_id": "weft-1",
                        "entity_kind": "function",
                        "content_hash_at_attach": "h",
                    }
                ]
            }
        ),
    )
    rows = client.associations("loomweave:eid:X")
    assert rows == [
        {"issue_id": "weft-1", "entity_kind": "function", "content_hash_at_attach": "h"}
    ]
    # keyed on the SEI as the opaque entity_id, against the ADR-029 HTTP route
    assert cap["url"].startswith("http://localhost:8724/api/entity-associations")
    assert "entity_id=loomweave%3Aeid%3AX" in cap["url"]


def test_associations_bare_list_payload_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FiligreeWorkClient(Path("/repo"))
    _patch_urlopen(
        monkeypatch, lambda req: _FakeResponse([{"issue_id": "weft-9"}])
    )
    assert client.associations("loomweave:eid:Y") == [{"issue_id": "weft-9"}]


def test_associations_earned_empty_is_not_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FiligreeWorkClient(Path("/repo"))
    _patch_urlopen(monkeypatch, lambda req: _FakeResponse({"associations": []}))
    # peer present, no binding -> [], NOT a raise (earned-empty)
    assert client.associations("loomweave:eid:none") == []


def test_transport_failure_raises_so_consult_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FiligreeWorkClient(Path("/repo"))

    def boom(req: Any) -> Any:
        raise urllib.error.URLError("connection refused")

    _patch_urlopen(monkeypatch, boom)
    # A genuine transport failure must propagate (federation._consult_filigree
    # turns this into reason_class 'unreachable', never a confident-empty).
    with pytest.raises(urllib.error.URLError):
        client.associations("loomweave:eid:X")


def test_issue_get_hits_issue_route(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FiligreeWorkClient(Path("/repo"), base_url="http://h:1/")
    cap = _patch_urlopen(
        monkeypatch,
        lambda req: _FakeResponse(
            {"id": "weft-1", "status": "open", "priority": 1, "claim_state": "unclaimed"}
        ),
    )
    issue = client.issue("weft-1")
    assert issue["status"] == "open"
    assert issue["priority"] == 1
    # trailing slash on base_url is normalized; issue id is path-quoted
    assert cap["url"] == "http://h:1/api/issue/weft-1"


def test_issue_get_unwraps_issue_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FiligreeWorkClient(Path("/repo"))
    _patch_urlopen(
        monkeypatch,
        lambda req: _FakeResponse({"issue": {"id": "weft-2", "status": "closed"}}),
    )
    assert client.issue("weft-2") == {"id": "weft-2", "status": "closed"}


def test_base_url_resolves_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FILIGREE_API_URL", "http://example:9999/")
    client = FiligreeWorkClient(Path("/repo"))
    assert client.base_url == "http://example:9999"


def test_base_url_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FILIGREE_API_URL", raising=False)
    client = FiligreeWorkClient(Path("/repo"))
    assert client.base_url == "http://localhost:8724"


def test_work_enrichment_derives_claim_state_from_live_issue_assignee() -> None:
    class LiveShape:
        def associations(self, sei: str) -> list[dict[str, Any]]:
            return [{"issue_id": "weft-1", "entity_kind": "function"}]

        def issue(self, issue_id: str) -> dict[str, Any]:
            return {"id": issue_id, "status": "in_progress", "priority": 2, "assignee": "Codex"}

    work = work_enrichment_for_sei(LiveShape(), "loomweave:eid:x")

    assert work[0]["issue_id"] == "weft-1"
    assert work[0]["issue_status"] == "in_progress"
    assert work[0]["claim_state"] == "claimed"
