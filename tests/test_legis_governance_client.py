"""LegisGovernanceClient — warpline's read-only consumer of legis governance_read.v1.

The client invokes ``legis governance-read <SEI> --json`` (mirroring
``WardlineDossierClient`` over ``wardline dossier``) and maps the
``governance_read.v1`` envelope onto the ``LegisClient`` Protocol:

  * status=checked   -> return ``records`` ([] is an earned-empty, returned as-is)
  * status=unavailable / nonzero exit / tampered / unparseable -> raise
    ``LegisGovernanceUnavailable`` (so ``_consult_legis`` reports ``unreachable``,
    never a confident-empty).

It NEVER re-derives the clearance ``content_hash`` against the current body:
governance is an advisory ECHO of a legis fact, not a warpline-asserted verdict.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from warpline.federation import LegisClient, LegisGovernanceClient, LegisGovernanceUnavailable

_SEI = "loomweave:eid:7Q3fc1"
_CHECKED = {
    "status": "checked",
    "sei": _SEI,
    "records": [
        {
            "sei": _SEI,
            "disposition": "cleared",
            "posture": "protected_override",
            "authority": "operator",
            "as_of": "2026-06-27T14:02:11Z",
            "reasons": ["operator_override"],
            "content_hash": "b3:9f2ce7",
        }
    ],
}


class _FakeProc:
    def __init__(self, stdout: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


def _patch(monkeypatch, fake_run) -> None:
    monkeypatch.setattr("warpline.federation.subprocess.run", fake_run)


def _read_run(payload: dict[str, Any]):
    def fake_run(cmd, **kw):
        return _FakeProc(stdout=json.dumps(payload))

    return fake_run


# --- the Protocol is satisfied ------------------------------------------------
def test_client_satisfies_legis_client_protocol() -> None:
    client: LegisClient = LegisGovernanceClient(Path("/repo"))
    assert callable(client.governance_for_sei)


def test_invokes_legis_governance_read_without_json_flag(monkeypatch) -> None:
    # legis's shipped CLI is `legis governance-read <SEI>` with output ALWAYS JSON;
    # a `--json` flag is an argparse error (nonzero exit). Pin the exact argv so the
    # invocation form can never drift back out of sync with legis.
    seen: dict[str, Any] = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return _FakeProc(stdout=json.dumps(_CHECKED))

    _patch(monkeypatch, fake_run)
    LegisGovernanceClient(Path("/repo"), command="legis").governance_for_sei(_SEI)
    assert seen["cmd"] == ["legis", "governance-read", _SEI]
    assert "--json" not in seen["cmd"]


# --- status=checked -----------------------------------------------------------
def test_checked_with_records_returns_them(monkeypatch) -> None:
    _patch(monkeypatch, _read_run(_CHECKED))
    records = LegisGovernanceClient(Path("/repo")).governance_for_sei(_SEI)
    assert len(records) == 1
    assert records[0]["disposition"] == "cleared"
    assert records[0]["posture"] == "protected_override"
    # content_hash is echoed verbatim, never re-derived.
    assert records[0]["content_hash"] == "b3:9f2ce7"


def test_checked_empty_returns_empty_list(monkeypatch) -> None:
    _patch(monkeypatch, _read_run({"status": "checked", "sei": _SEI, "records": []}))
    # earned-empty: no verified clearance. Returned as [], NEVER raised.
    assert LegisGovernanceClient(Path("/repo")).governance_for_sei(_SEI) == []


def test_non_dict_records_are_filtered(monkeypatch) -> None:
    _patch(monkeypatch, _read_run({"status": "checked", "sei": _SEI, "records": ["junk", {}]}))
    out = LegisGovernanceClient(Path("/repo")).governance_for_sei(_SEI)
    assert out == [{}]


# --- status=unavailable / failures -> raise -----------------------------------
def test_unavailable_status_raises_with_reasons(monkeypatch) -> None:
    payload = {
        "status": "unavailable",
        "sei": _SEI,
        "records": [],
        "unavailable": [{"reason": "trail not signature-verifiable"}],
    }
    _patch(monkeypatch, _read_run(payload))
    with pytest.raises(LegisGovernanceUnavailable) as exc:
        LegisGovernanceClient(Path("/repo")).governance_for_sei(_SEI)
    assert exc.value.sei == _SEI
    assert "not signature-verifiable" in repr(exc.value.reasons)


def test_nonzero_exit_raises(monkeypatch) -> None:
    def fake_run(cmd, **kw):
        raise subprocess.CalledProcessError(returncode=2, cmd=cmd, stderr="tampered")

    _patch(monkeypatch, fake_run)
    with pytest.raises(LegisGovernanceUnavailable):
        LegisGovernanceClient(Path("/repo")).governance_for_sei(_SEI)


def test_unparseable_output_raises(monkeypatch) -> None:
    _patch(monkeypatch, lambda *a, **k: _FakeProc(stdout="not json"))
    with pytest.raises(LegisGovernanceUnavailable):
        LegisGovernanceClient(Path("/repo")).governance_for_sei(_SEI)


def test_missing_binary_raises(monkeypatch) -> None:
    def fake_run(cmd, **kw):
        raise FileNotFoundError("legis")

    _patch(monkeypatch, fake_run)
    with pytest.raises(LegisGovernanceUnavailable):
        LegisGovernanceClient(Path("/repo")).governance_for_sei(_SEI)


# --- capability probe (gates the live wiring so an unshipped verb stays disabled)
def test_available_true_when_verb_advertised(monkeypatch) -> None:
    help_text = "usage: legis {serve,governance-read,doctor}"
    _patch(monkeypatch, lambda *a, **k: _FakeProc(stdout=help_text))
    assert LegisGovernanceClient.available(Path("/repo")) is True


def test_available_false_when_verb_absent(monkeypatch) -> None:
    _patch(monkeypatch, lambda *a, **k: _FakeProc(stdout="usage: legis {serve,mcp,doctor}"))
    assert LegisGovernanceClient.available(Path("/repo")) is False


def test_available_false_when_binary_missing(monkeypatch) -> None:
    def fake_run(cmd, **kw):
        raise FileNotFoundError("legis")

    _patch(monkeypatch, fake_run)
    assert LegisGovernanceClient.available(Path("/repo")) is False
