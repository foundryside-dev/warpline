from __future__ import annotations

from heddle.reverify import render_reverify_worklist


def test_reverify_worklist_is_machine_first() -> None:
    items, work_seen, candidates = render_reverify_worklist(
        changed=[{"entity": {"locator": "python:function:a", "sei": None}}],
        affected=[
            {
                "entity": {"locator": "python:function:b", "sei": None},
                "depth": 1,
                "via_edges": [{"from": "1", "to": "2", "kind": "calls", "confidence": "resolved"}],
            }
        ],
        completeness="FULL",
        staleness={"snapshot_commit": "c1", "commits_behind": None},
    )
    changed_item = next(item for item in items if item["reason"] == "changed")
    assert changed_item["entity"]["locator"] == "python:function:a"
    downstream = next(item for item in items if item["reason"] == "downstream")
    assert downstream["entity"]["locator"] == "python:function:b"
    assert downstream["why"][0]["kind"] == "calls"
    assert downstream["depth"] == 1
    assert downstream["enrichment"] == {
        "work": [],
        "risk": [],
        "governance": [],
        "requirements": [],
    }
    assert work_seen is False
    assert candidates == []
