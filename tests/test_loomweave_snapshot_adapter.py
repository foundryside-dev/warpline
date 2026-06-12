from __future__ import annotations

from heddle.snapshot import edges_from_neighborhood


def test_edges_from_neighborhood_reads_callers_and_callees() -> None:
    neighborhood = {
        "entity": {"id": "python:function:pkg.target", "sei": "loomweave:eid:t"},
        "callers": [{"id": "python:function:pkg.caller", "sei": "loomweave:eid:c"}],
        "callees": [{"id": "python:function:pkg.child", "sei": "loomweave:eid:x"}],
        "truncated": {"callers": False, "callees": False},
    }
    edges = edges_from_neighborhood(neighborhood)
    assert ("python:function:pkg.caller", "python:function:pkg.target", "calls") in edges
    assert ("python:function:pkg.target", "python:function:pkg.child", "calls") in edges
