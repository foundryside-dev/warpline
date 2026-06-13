from __future__ import annotations

from pathlib import Path

import pytest

from heddle.loomweave import LoomweaveMcpClient, LoomweaveProbe, resolve_sei_for_locator

HEDDLE_REPO = Path("/home/john/heddle")

# Real Python locators in this repo that loomweave has indexed. HX1 requires
# these to resolve to NON-None loomweave:eid: SEIs against the LIVE loomweave —
# the bug was sei=None / fake-only resolution.
_LIVE_LOCATORS = [
    "python:function:src/heddle/store.py::HeddleStore.timeline",
    "python:function:src/heddle/locators.py::python_entity_locators",
    "file:src/heddle/store.py",
]


def _live_client() -> LoomweaveMcpClient:
    probe = LoomweaveProbe(repo=HEDDLE_REPO).probe()
    if probe.get("status") != "available":
        pytest.skip(f"loomweave unavailable for live HX1 probe: {probe}")
    return LoomweaveMcpClient(repo=HEDDLE_REPO)


def test_hx1_resolves_real_locators_to_non_none_seis() -> None:
    client = _live_client()
    resolved = {}
    for locator in _LIVE_LOCATORS:
        sei = resolve_sei_for_locator(client, locator)
        resolved[locator] = sei
    # Every indexed locator must resolve to a real, opaque loomweave SEI.
    for locator, sei in resolved.items():
        assert isinstance(sei, str) and sei.startswith("loomweave:eid:"), (
            f"HX1 regression: {locator} resolved to {sei!r} against the real loomweave"
        )


def test_hx1_unindexed_locator_degrades_to_none_not_error() -> None:
    client = _live_client()
    sei = resolve_sei_for_locator(
        client, "python:function:src/heddle/does_not_exist.py::nope"
    )
    assert sei is None
