from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from heddle import commands
from heddle.git import backfill
from heddle.loomweave import (
    LoomweaveMcpClient,
    LoomweaveProbe,
    loomweave_entity_id_candidates,
    resolve_sei_for_locator,
)
from heddle.mcp import dispatch
from heddle.snapshot import capture_edge_snapshot
from heddle.store import HeddleStore, default_store_path

DEFAULT_DOGFOOD_RESULTS = Path("/tmp/heddle-dogfood-results.json")
SOLO_THRESHOLD = 8
FEDERATION_THRESHOLD = 8
REAL_MEMBER_REPO = Path("/home/john/lacuna")
REAL_MEMBER_THRESHOLD = 1


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
        target = loomweave_entity_id_candidates(self.case.target_locator)[0]
        consumer = loomweave_entity_id_candidates(self.case.consumer_locator)[0]
        if entity == target:
            return {
                "entity": {"id": target},
                "callees": [{"id": consumer}],
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
    real_member_repo: Path | None = REAL_MEMBER_REPO,
    require_real_member: bool = True,
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

    if real_member_repo is not None and real_member_repo.exists():
        cases.append(_run_real_member_case(root, real_member_repo))
    elif require_real_member:
        cases.append(_missing_real_member_case(real_member_repo))

    solo_parity = sum(
        1 for case in cases if case["lane"] == "solo" and case["parity"] is True
    )
    federation_uplift = sum(
        1
        for case in cases
        if case["lane"] == "federation" and case["uplift"] is True
    )
    real_member_parity = sum(
        1 for case in cases if case["lane"] == "real_member" and case["parity"] is True
    )
    real_loomweave_uplift = sum(
        1 for case in cases if case["lane"] == "real_member" and case["uplift"] is True
    )
    real_baseline_executed = sum(
        1
        for case in cases
        if case["lane"] == "real_member"
        and case.get("baseline_answer", {}).get("baseline_executed") is True
    )
    result = {
        "schema": "heddle.dogfood_results.v1",
        "thresholds": {
            "synthetic_solo_parity": SOLO_THRESHOLD,
            "synthetic_federation_uplift": FEDERATION_THRESHOLD,
            "real_member_parity": REAL_MEMBER_THRESHOLD,
            "real_loomweave_uplift": REAL_MEMBER_THRESHOLD,
            "real_baseline_executed": REAL_MEMBER_THRESHOLD,
        },
        "summary": {
            "solo": {"cases": 10, "parity": solo_parity},
            "federation": {"cases": 10, "uplift": federation_uplift},
            "real_member": {
                "cases": sum(1 for case in cases if case["lane"] == "real_member"),
                "parity": real_member_parity,
                "uplift": real_loomweave_uplift,
                "baseline_executed": real_baseline_executed,
            },
        },
        "ready": (
            real_member_parity >= REAL_MEMBER_THRESHOLD
            and real_loomweave_uplift >= REAL_MEMBER_THRESHOLD
            and real_baseline_executed >= REAL_MEMBER_THRESHOLD
        ),
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
    reverify_args = changed_response["next_actions"]["heddle_reverify_worklist_get"]["arguments"]
    reverify_response = _call_tool("reverify", reverify_args)
    tool_calls += 1
    reverify_data = reverify_response["data"]

    changed_paths = _changed_paths(changed_data)
    changed_key_ids = reverify_args.get("changed_entity_key_ids", [])
    reverify_items = reverify_data.get("items", [])
    parity = (
        tool_calls <= 2
        and case.target_path in changed_paths
        and bool(changed_key_ids)
        and reverify_data.get("completeness") in {"FULL", "DELTA"}
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
            "changed_entity_key_ids": changed_key_ids,
            "changed_paths": sorted(changed_paths),
            "reverify_completeness": reverify_data.get("completeness"),
            "reverify_item_count": len(reverify_items) if isinstance(reverify_items, list) else 0,
        },
        "parity": parity,
        "uplift": uplift,
        "failure_reason": failure_reason,
        "manual_escape_required": False,
        "enrichment_state": {
            "sei": changed_response["enrichment"]["sei"],
            "edges": "present" if lane == "federation" else "absent",
            "completeness": reverify_data.get("completeness"),
        },
    }


def _changed_paths(change_data: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    for item in change_data.get("items", []):
        if isinstance(item, dict):
            entity = item.get("entity")
            if isinstance(entity, dict) and isinstance(entity.get("path"), str):
                paths.add(entity["path"])
    return paths


def _run_real_member_case(root: Path, source_repo: Path) -> dict[str, Any]:
    case_id = "real-lacuna-loomweave"
    repo = root / "real_member" / source_repo.name
    tool_calls = 0
    try:
        _prepare_real_member_repo(source_repo, repo)
        # Full-history backfill stays fast (no per-locator loomweave spawn); HX1
        # SEI resolution is demonstrated targeted to the changed set below.
        sei_client = _real_member_sei_client(repo)
        with HeddleStore.open(default_store_path(repo)) as store:
            backfill(store, repo)

        capture_payload = _call_tool_stdio("capture_snapshot", {"repo": str(repo)})
        tool_calls += 1
        capture_data = capture_payload["data"]
        rev_range, selected = _select_real_member_rev_range(repo)
        baseline = _executed_baseline(repo, rev_range)

        changed_payload = _call_tool_stdio(
            "changed",
            {"repo": str(repo), "rev_range": rev_range},
        )
        tool_calls += 1
        changed_data = changed_payload["data"]
        reverify_args = changed_payload["next_actions"]["heddle_reverify_worklist_get"]["arguments"]
        reverify_payload = _call_tool_stdio("reverify", reverify_args)
        tool_calls += 1
        reverify_data = reverify_payload["data"]

        heddle_paths = _changed_paths(changed_data)
        baseline_paths = set(baseline["changed_paths"])
        reverify_items = reverify_data.get("items", [])
        changed_key_ids = reverify_args.get("changed_entity_key_ids", [])
        # HX1: resolve real loomweave SEIs for the changed set (targeted, fast).
        sei_resolved = 0
        if sei_client is not None:
            for item in changed_data.get("items", []):
                locator = item.get("entity", {}).get("locator") if isinstance(item, dict) else None
                if isinstance(locator, str) and resolve_sei_for_locator(sei_client, locator):
                    sei_resolved += 1
        parity = (
            baseline["baseline_executed"] is True
            and baseline_paths == heddle_paths
            and bool(changed_key_ids)
            and reverify_data.get("completeness") in {"FULL", "DELTA"}
        )
        uplift = (
            parity
            and capture_data.get("source") == "loomweave"
            and int(capture_data.get("edges", 0)) > 0
            and isinstance(reverify_items, list)
            and len(reverify_items) > 0
        )
        failure_reason = None
        if not parity:
            failure_reason = "real member parity criteria not met"
        elif not uplift:
            failure_reason = "real Loomweave enrichment did not produce a worklist"
        return {
            "case_id": case_id,
            "lane": "real_member",
            "repo": str(source_repo),
            "tool_calls": tool_calls,
            "baseline_answer": baseline,
            "heddle_answer": {
                "rev_range": rev_range,
                "selected_by": selected,
                "capture_completeness": capture_data.get("completeness"),
                "capture_edges": capture_data.get("edges"),
                "changed_entity_key_ids": changed_key_ids,
                "changed_paths": sorted(heddle_paths),
                "reverify_completeness": reverify_data.get("completeness"),
                "reverify_item_count": len(reverify_items)
                if isinstance(reverify_items, list)
                else 0,
                "sei_resolved": sei_resolved,
            },
            "parity": parity,
            "uplift": uplift,
            "failure_reason": failure_reason,
            "manual_escape_required": False,
            "enrichment_state": {
                "sei": "present" if sei_resolved else "absent",
                "edges": "present" if int(capture_data.get("edges", 0)) > 0 else "absent",
                "completeness": reverify_data.get("completeness"),
            },
        }
    except Exception as exc:
        return {
            "case_id": case_id,
            "lane": "real_member",
            "repo": str(source_repo),
            "tool_calls": tool_calls,
            "baseline_answer": {
                "baseline_executed": False,
                "commands_executed": [],
                "changed_paths": [],
                "grep_hits": {},
            },
            "heddle_answer": {},
            "parity": False,
            "uplift": False,
            "failure_reason": str(exc),
            "manual_escape_required": True,
            "enrichment_state": {"sei": "unknown", "edges": "unknown", "completeness": "FAILED"},
        }


def _missing_real_member_case(real_member_repo: Path | None) -> dict[str, Any]:
    return {
        "case_id": "real-lacuna-loomweave",
        "lane": "real_member",
        "repo": str(real_member_repo) if real_member_repo is not None else None,
        "tool_calls": 0,
        "baseline_answer": {
            "baseline_executed": False,
            "commands_executed": [],
            "changed_paths": [],
            "grep_hits": {},
        },
        "heddle_answer": {},
        "parity": False,
        "uplift": False,
        "failure_reason": "required real member repo is unavailable",
        "manual_escape_required": True,
        "enrichment_state": {"sei": "unknown", "edges": "unknown", "completeness": "FAILED"},
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


def _prepare_real_member_repo(source_repo: Path, target_repo: Path) -> None:
    if target_repo.exists():
        shutil.rmtree(target_repo)
    target_repo.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--quiet", str(source_repo), str(target_repo)],
        check=True,
        text=True,
        capture_output=True,
    )
    loomweave_source = source_repo / ".weft" / "loomweave"
    if not loomweave_source.exists():
        raise RuntimeError(f"{source_repo} has no .weft/loomweave index")
    loomweave_target = target_repo / ".weft" / "loomweave"
    loomweave_target.parent.mkdir(parents=True, exist_ok=True)
    if loomweave_target.exists():
        shutil.rmtree(loomweave_target)
    shutil.copytree(loomweave_source, loomweave_target)


def _select_real_member_rev_range(repo: Path) -> tuple[str, str]:
    commits = [line for line in _git(repo, ["log", "--format=%H"]).splitlines() if line]
    for sha in commits:
        parent = subprocess.run(
            ["git", "rev-parse", "--verify", f"{sha}^"],
            cwd=repo,
            check=False,
            text=True,
            capture_output=True,
        )
        if parent.returncode != 0:
            continue
        rev_range = f"{sha}^..{sha}"
        changed_env = commands.change_list(repo, rev_range)
        reverify_action = changed_env["next_actions"]["heddle_reverify_worklist_get"]
        changed_entity_key_ids = reverify_action["arguments"].get("changed_entity_key_ids")
        if not isinstance(changed_entity_key_ids, list) or not changed_entity_key_ids:
            continue
        reverify_env = commands.reverify_worklist(
            repo,
            [int(value) for value in changed_entity_key_ids],
            depth=2,
        )
        items = reverify_env["data"].get("items")
        if isinstance(items, list) and items:
            return rev_range, "first historical commit with non-empty reverify worklist"
    raise RuntimeError("no real member commit produced a non-empty reverify worklist")


def _real_member_sei_client(repo: Path) -> LoomweaveMcpClient | None:
    probe = LoomweaveProbe(repo=repo).probe()
    if probe.get("status") != "available":
        return None
    return LoomweaveMcpClient(repo=repo)


def _executed_baseline(repo: Path, rev_range: str) -> dict[str, Any]:
    # HX2: the baseline must execute on a host WITHOUT ripgrep. We use
    # git-grep against the tracked tree (always present where git is) instead of
    # depending on `rg`, so an actually-executed baseline reaches ready=True.
    diff_cmd = ["git", "diff", "--name-only", rev_range]
    diff_output = _git(repo, diff_cmd[1:])
    changed_paths = [line for line in diff_output.splitlines() if line]
    grep_hits: dict[str, dict[str, object]] = {}
    commands_executed = [" ".join(diff_cmd)]
    for pattern in _grep_patterns(changed_paths):
        grep_cmd = ["git", "grep", "-n", "--fixed-strings", "--", pattern]
        proc = subprocess.run(
            grep_cmd,
            cwd=repo,
            check=False,
            text=True,
            capture_output=True,
            timeout=15,
        )
        commands_executed.append(" ".join(grep_cmd))
        # git grep exits 1 when there are no matches; both 0 and 1 are an
        # executed baseline, only other codes are tool failures.
        grep_hits[pattern] = {
            "returncode": proc.returncode,
            "line_count": len([line for line in proc.stdout.splitlines() if line]),
            "executed": proc.returncode in (0, 1),
        }
    baseline_executed = (
        bool(changed_paths)
        and bool(grep_hits)
        and all(hit["executed"] for hit in grep_hits.values())
    )
    return {
        "baseline_executed": baseline_executed,
        "rev_range": rev_range,
        "commands_executed": commands_executed,
        "changed_paths": changed_paths,
        "grep_hits": grep_hits,
    }


def _grep_patterns(changed_paths: list[str]) -> list[str]:
    patterns: list[str] = []
    for path in changed_paths:
        suffix = Path(path).suffix
        if suffix not in {".py", ".rs", ".md", ".toml"}:
            continue
        pattern = Path(path).stem
        if pattern and pattern not in patterns:
            patterns.append(pattern)
        if len(patterns) >= 5:
            break
    return patterns


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


def _call_tool_stdio(name: str, arguments: dict[str, object]) -> dict[str, Any]:
    env = os.environ.copy()
    source_path = str(Path(__file__).resolve().parents[2] / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        source_path
        if not existing_pythonpath
        else f"{source_path}{os.pathsep}{existing_pythonpath}"
    )
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    proc = subprocess.run(
        [sys.executable, "-c", "from heddle.mcp import main; raise SystemExit(main())"],
        input=json.dumps(request) + "\n",
        check=True,
        text=True,
        capture_output=True,
        env=env,
        timeout=90,
    )
    response = json.loads(proc.stdout.splitlines()[-1])
    if "error" in response:
        raise RuntimeError(f"{name} MCP error: {response['error']}")
    result = response["result"]
    if not isinstance(result, dict):
        raise RuntimeError(f"{name} returned non-object MCP result")
    content = result["content"]
    if not isinstance(content, list):
        raise RuntimeError(f"{name} returned non-list MCP content")
    first = content[0]
    if not isinstance(first, dict):
        raise RuntimeError(f"{name} returned invalid MCP content")
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
