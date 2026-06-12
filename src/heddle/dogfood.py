from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from heddle.git import backfill
from heddle.mcp import dispatch
from heddle.snapshot import capture_edge_snapshot
from heddle.store import HeddleStore, default_store_path

DEFAULT_DOGFOOD_RESULTS = Path("/tmp/heddle-dogfood-results.json")
SOLO_THRESHOLD = 8
FEDERATION_THRESHOLD = 8


@dataclass(frozen=True)
class DogfoodCase:
    case_id: str
    index: int

    @property
    def target_path(self) -> str:
        return f"target_{self.index:02d}.py"

    @property
    def consumer_path(self) -> str:
        return f"consumer_{self.index:02d}.py"

    @property
    def target_locator(self) -> str:
        return f"python:function:{self.target_path}::target_{self.index:02d}"

    @property
    def consumer_locator(self) -> str:
        return f"python:function:{self.consumer_path}::consumer_{self.index:02d}"


class FederationSnapshotClient:
    def __init__(self, case: DogfoodCase) -> None:
        self.case = case

    def neighborhood(self, entity: str) -> dict[str, Any]:
        if entity == self.case.target_locator:
            return {
                "entity": {"id": self.case.target_locator},
                "callees": [{"id": self.case.consumer_locator}],
                "truncated": {"callers": False, "callees": False},
            }
        return {
            "entity": {"id": entity},
            "truncated": {"callers": False, "callees": False},
        }


def run_dogfood_evaluator(
    *,
    output_path: Path = DEFAULT_DOGFOOD_RESULTS,
    work_dir: Path | None = None,
) -> dict[str, Any]:
    root = work_dir or Path("/tmp/heddle-dogfood-work")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    cases: list[dict[str, Any]] = []
    for index in range(10):
        spec = DogfoodCase(case_id=f"dogfood-{index:02d}", index=index)
        cases.append(_run_case(root, spec, lane="solo"))
        cases.append(_run_case(root, spec, lane="federation"))

    solo_parity = sum(
        1 for case in cases if case["lane"] == "solo" and case["parity"] is True
    )
    federation_uplift = sum(
        1
        for case in cases
        if case["lane"] == "federation" and case["uplift"] is True
    )
    result = {
        "schema": "heddle.dogfood_results.v1",
        "thresholds": {
            "solo_parity": SOLO_THRESHOLD,
            "federation_uplift": FEDERATION_THRESHOLD,
        },
        "summary": {
            "solo": {"cases": 10, "parity": solo_parity},
            "federation": {"cases": 10, "uplift": federation_uplift},
        },
        "ready": solo_parity >= SOLO_THRESHOLD and federation_uplift >= FEDERATION_THRESHOLD,
        "cases": cases,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _run_case(root: Path, case: DogfoodCase, *, lane: str) -> dict[str, Any]:
    repo = root / lane / case.case_id
    _prepare_repo(repo, case)
    with HeddleStore.open(default_store_path(repo)) as store:
        backfill(store, repo)
        if lane == "federation":
            capture_edge_snapshot(
                store,
                repo,
                commit_sha=_git(repo, ["rev-parse", "HEAD"]).strip(),
                client=FederationSnapshotClient(case),
                source_version="heddle-dogfood-draft-spec",
            )

    tool_calls = 0
    changed_response = _call_tool(
        "changed",
        {"repo": str(repo), "rev_range": "HEAD~1..HEAD"},
    )
    tool_calls += 1
    changed_data = changed_response["data"]
    next_actions = changed_data.get("next_actions", {})
    reverify_action = next_actions.get("reverify", {})
    reverify_args = reverify_action.get("arguments", {})
    reverify_response = _call_tool("reverify", reverify_args)
    tool_calls += 1
    reverify_data = reverify_response["data"]

    changed_paths = {
        row.get("path")
        for row in changed_data.get("changed", [])
        if isinstance(row, dict)
    }
    reverify_items = reverify_data.get("items", [])
    parity = (
        tool_calls <= 2
        and case.target_path in changed_paths
        and bool(changed_data.get("changed_entity_key_ids"))
        and reverify_data.get("completeness") in {"NO_SNAPSHOT", "FULL", "DELTA"}
    )
    uplift = lane == "federation" and parity and reverify_data.get("completeness") == "FULL"
    uplift = uplift and isinstance(reverify_items, list) and len(reverify_items) > 0
    failure_reason = None
    if not parity:
        failure_reason = "solo parity criteria not met"
    elif lane == "federation" and not uplift:
        failure_reason = "federation enrichment did not improve reverify output"

    return {
        "case_id": case.case_id,
        "lane": lane,
        "tool_calls": tool_calls,
        "baseline_answer": {
            "changed_paths": sorted(changed_paths),
            "manual_steps": ["git diff --name-only", "manual dependency inspection"],
        },
        "heddle_answer": {
            "changed_entity_key_ids": changed_data.get("changed_entity_key_ids", []),
            "changed_paths": sorted(changed_paths),
            "reverify_completeness": reverify_data.get("completeness"),
            "reverify_item_count": len(reverify_items) if isinstance(reverify_items, list) else 0,
        },
        "parity": parity,
        "uplift": uplift,
        "failure_reason": failure_reason,
        "manual_escape_required": False,
        "enrichment_state": {
            "sei": "absent",
            "edges": "present" if lane == "federation" else "absent",
            "completeness": reverify_data.get("completeness"),
        },
    }


def _prepare_repo(repo: Path, case: DogfoodCase) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, ["init"])
    _git(repo, ["config", "user.email", "agent@example.test"])
    _git(repo, ["config", "user.name", "Agent"])
    (repo / case.target_path).write_text(
        f"def target_{case.index:02d}():\n    return 1\n",
        encoding="utf-8",
    )
    (repo / case.consumer_path).write_text(
        (
            f"from target_{case.index:02d} import target_{case.index:02d}\n\n"
            f"def consumer_{case.index:02d}():\n"
            f"    return target_{case.index:02d}()\n"
        ),
        encoding="utf-8",
    )
    _git(repo, ["add", "."])
    _git(repo, ["commit", "-m", "initial graph"])
    (repo / case.target_path).write_text(
        f"def target_{case.index:02d}():\n    return 2\n",
        encoding="utf-8",
    )
    _git(repo, ["commit", "-am", "change target"])


def _call_tool(name: str, arguments: dict[str, object]) -> dict[str, Any]:
    response = dispatch(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    result = response["result"]
    assert isinstance(result, dict)
    content = result["content"]
    assert isinstance(content, list)
    first = content[0]
    assert isinstance(first, dict)
    payload = json.loads(str(first["text"]))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{name} returned non-object MCP payload")
    return payload


def _git(repo: Path, args: list[str]) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,
    ).stdout
