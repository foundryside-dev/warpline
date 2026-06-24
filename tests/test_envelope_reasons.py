from __future__ import annotations

import pytest

from warpline.envelope import build_envelope, enrichment_state
from warpline.listing import reason


def _minimal_env(**kw):
    return build_envelope(
        "warpline.test.v1",
        query={"tool": "t"},
        data={"items": []},
        enrichment=enrichment_state(),
        **kw,
    )


def test_envelope_defaults_enrichment_reasons_to_empty_map() -> None:
    env = _minimal_env()
    # requirements is seeded reserved-but-honest on every envelope; nothing else.
    assert set(env["enrichment_reasons"]) == {"requirements"}
    assert env["enrichment_reasons"]["requirements"]["reason_class"] == "disabled"


def test_envelope_carries_a_reason_triple_alongside_the_scalar() -> None:
    env = _minimal_env(
        enrichment_reasons={
            "sei": reason(
                "unresolved_input",
                cause="locator never resolved to an SEI",
                fix="run loomweave analyze, then re-query",
            )
        }
    )
    # the scalar vocab is untouched; the triple rides in the sibling map
    assert env["enrichment"]["sei"] == "absent"
    assert env["enrichment_reasons"]["sei"]["reason_class"] == "unresolved_input"
    assert env["enrichment_reasons"]["sei"]["cause"]
    assert env["enrichment_reasons"]["sei"]["fix"]


def test_envelope_rejects_reason_for_unknown_dimension() -> None:
    with pytest.raises(ValueError, match="enrichment_reasons.bogus"):
        _minimal_env(enrichment_reasons={"bogus": reason("clean")})


def test_envelope_rejects_reason_value_without_reason_class() -> None:
    with pytest.raises(ValueError, match="enrichment_reasons.sei"):
        _minimal_env(enrichment_reasons={"sei": {"not": "a reason"}})


def test_clean_reason_needs_no_cause_or_fix() -> None:
    env = _minimal_env(enrichment_reasons={"sei": reason("clean")})
    assert env["enrichment_reasons"]["sei"] == {"reason_class": "clean"}
