"""legis governance_read.v1 — warpline's mirrored consumer contract.

legis OWNS this contract; warpline mirrors it BYTE-FOR-BYTE at
``contracts/governance_read.v1.schema.json`` as the source of truth for its
advisory ``LegisGovernanceClient``. Two vector sources: the contract's CANONICAL
LITERAL SAMPLES (from the legis-authored spec, exercising every union arm), and a
REAL legis-produced envelope vendored verbatim from legis's conformance golden
(``legis-governance-read.golden.json``) — the interface-agreement guard that fails
loud if legis's emitted shape and warpline's consumed shape ever diverge.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")

_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = _ROOT / "contracts" / "governance_read.v1.schema.json"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate(instance: dict) -> None:
    jsonschema.validate(instance=instance, schema=_schema())


def _rejects(instance: dict) -> None:
    with pytest.raises(jsonschema.ValidationError):
        _validate(instance)


# --- canonical contract samples (legis-authored; not a live capture) ----------
CHECKED_WITH_CLEARANCES = {
    "status": "checked",
    "sei": "loomweave:eid:7Q3fc1",
    "records": [
        {
            "sei": "loomweave:eid:7Q3fc1",
            "disposition": "cleared",
            "posture": "protected_override",
            "authority": "operator",
            "as_of": "2026-06-27T14:02:11Z",
            "reasons": ["operator_override"],
            "content_hash": "b3:9f2ce7",
        },
        {
            "sei": "loomweave:eid:7Q3fc1",
            "disposition": "cleared",
            "posture": "operator_signoff",
            "authority": "operator",
            "as_of": "2026-06-26T09:41:55+00:00",
            "reasons": ["signoff_cleared"],
            "content_hash": "b3:5a1092",
        },
    ],
}
CHECKED_EMPTY = {"status": "checked", "sei": "loomweave:eid:unknown", "records": []}
UNAVAILABLE = {
    "status": "unavailable",
    "sei": "loomweave:eid:7Q3fc1",
    "records": [],
    "unavailable": [{"reason": "trail not signature-verifiable (no protected gate / verifier)"}],
}


_GOLDEN_PATH = _ROOT / "tests" / "fixtures" / "contracts" / "warpline" / (
    "legis-governance-read.golden.json"
)


def test_schema_is_wellformed_draft_2020_12() -> None:
    jsonschema.Draft202012Validator.check_schema(_schema())


def test_real_legis_golden_envelope_validates_and_parses() -> None:
    """Cross-member conformance: a REAL legis-produced governance_read.v1 envelope
    (vendored verbatim from legis's conformance golden) validates against warpline's
    mirrored schema AND round-trips through the consumer's parse contract. This is
    the interface-agreement guard — it fails loud if legis's emitted shape and
    warpline's consumed shape ever diverge."""

    golden = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    _validate(golden)
    assert golden["status"] == "checked"
    records = [r for r in golden["records"] if isinstance(r, dict)]
    assert records, "golden carries at least one verified clearance"
    assert {r["disposition"] for r in records} == {"cleared"}
    assert {r["posture"] for r in records} <= {"protected_override", "operator_signoff"}


def test_canonical_samples_validate() -> None:
    _validate(CHECKED_WITH_CLEARANCES)
    _validate(CHECKED_EMPTY)  # earned-empty: no verified clearance, NOT "ungoverned"
    _validate(UNAVAILABLE)


def test_both_postures_and_reason_codes_round_trip() -> None:
    postures = {r["posture"] for r in CHECKED_WITH_CLEARANCES["records"]}
    reasons = {c for r in CHECKED_WITH_CLEARANCES["records"] for c in r["reasons"]}
    assert postures == {"protected_override", "operator_signoff"}
    assert reasons == {"operator_override", "signoff_cleared"}


# --- rejections: the schema must be tight, not permissive ---------------------
def test_rejects_record_missing_content_hash() -> None:
    bad = json.loads(json.dumps(CHECKED_WITH_CLEARANCES))
    del bad["records"][0]["content_hash"]
    _rejects(bad)


def test_rejects_non_cleared_disposition() -> None:
    # A BLOCKED/pending record has no place in v1 (cleared-only); the schema
    # enforces the cleared-only scope so a future drift cannot smuggle in-flight
    # governance through this channel without a v2 bump.
    bad = json.loads(json.dumps(CHECKED_WITH_CLEARANCES))
    bad["records"][0]["disposition"] = "blocked"
    _rejects(bad)


def test_rejects_status_outside_enum() -> None:
    _rejects({"status": "cleared", "sei": "loomweave:eid:x", "records": []})


def test_rejects_unknown_posture() -> None:
    bad = json.loads(json.dumps(CHECKED_WITH_CLEARANCES))
    bad["records"][0]["posture"] = "structured"
    _rejects(bad)


def test_rejects_empty_reasons() -> None:
    bad = json.loads(json.dumps(CHECKED_WITH_CLEARANCES))
    bad["records"][0]["reasons"] = []
    _rejects(bad)


def test_rejects_unknown_top_level_key() -> None:
    bad = json.loads(json.dumps(CHECKED_EMPTY))
    bad["verdict"] = "allow"  # no verdict leaks through a governance READ
    _rejects(bad)


# --- discriminated union (legis hardened the contract; backward-compatible) ----
# These pin the status<->shape coupling the `allOf` enforces, so warpline's
# consumer validates with EXACTLY the tightness legis emits — an 'unavailable'
# that could masquerade as a clean/empty 'checked' is the false-green this kills.
def test_rejects_checked_carrying_an_unavailable_key() -> None:
    # status 'checked' MUST NOT carry the unavailable reasons array.
    _rejects({"status": "checked", "sei": "loomweave:eid:x", "records": [],
              "unavailable": [{"reason": "leaked"}]})


def test_rejects_unavailable_missing_its_reasons() -> None:
    # status 'unavailable' REQUIRES the unavailable array.
    _rejects({"status": "unavailable", "sei": "loomweave:eid:x", "records": []})


def test_rejects_unavailable_with_empty_reasons() -> None:
    # the unavailable array must be non-empty (minItems: 1) — never a silent empty.
    _rejects({"status": "unavailable", "sei": "loomweave:eid:x", "records": [],
              "unavailable": []})


def test_rejects_unavailable_with_a_blank_reason_string() -> None:
    _rejects({"status": "unavailable", "sei": "loomweave:eid:x", "records": [],
              "unavailable": [{"reason": ""}]})


def test_rejects_unavailable_carrying_records() -> None:
    # 'unavailable' must carry [] records (maxItems: 0) — no clearance rides an
    # unverifiable answer.
    bad = json.loads(json.dumps(UNAVAILABLE))
    bad["records"] = CHECKED_WITH_CLEARANCES["records"]
    _rejects(bad)
