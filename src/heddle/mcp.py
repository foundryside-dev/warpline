from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from heddle import commands

CORE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "schema": {"type": "string"},
        "ok": {"type": "boolean"},
        "data": {"type": "object"},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "meta": {"type": "object"},
    },
    "required": ["schema", "ok", "data", "warnings", "meta"],
    "additionalProperties": True,
}

TOOLS = [
    {
        "name": "changed",
        "description": "List changed entities for an ingested repo. Read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {"repo": {"type": "string"}, "rev_range": {"type": "string"}},
            "required": ["repo"],
            "additionalProperties": False,
        },
        "outputSchema": CORE_OUTPUT_SCHEMA,
    },
    {
        "name": "timeline",
        "description": "List recorded changes for one entity locator or SEI. Read-only.",
        "inputSchema": {
            "type": "object",
            "properties": {"repo": {"type": "string"}, "entity": {"type": "string"}},
            "required": ["repo", "entity"],
            "additionalProperties": False,
        },
        "outputSchema": CORE_OUTPUT_SCHEMA,
    },
    {
        "name": "blast_radius",
        "description": (
            "Return downstream affected entities from stored dated snapshots. Read-only."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
                "changed_entity_key_ids": {"type": "array", "items": {"type": "integer"}},
                "depth": {"type": "integer", "minimum": 0, "maximum": 5},
            },
            "required": ["repo", "changed_entity_key_ids"],
            "additionalProperties": False,
        },
        "outputSchema": CORE_OUTPUT_SCHEMA,
    },
    {
        "name": "reverify",
        "description": "Render an agent-first re-verification worklist from blast-radius output.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
                "changed_entity_key_ids": {"type": "array", "items": {"type": "integer"}},
                "depth": {"type": "integer", "minimum": 0, "maximum": 5},
            },
            "required": ["repo", "changed_entity_key_ids"],
            "additionalProperties": False,
        },
        "outputSchema": CORE_OUTPUT_SCHEMA,
    },
]


def _schema_for_tool(name: str) -> str:
    return {
        "changed": "heddle.draft.changed.v1",
        "timeline": "heddle.draft.timeline.v1",
        "blast_radius": "heddle.draft.blast_radius.v1",
        "reverify": "heddle.draft.reverify.v1",
    }[name]


def _warnings_for_result(result: dict[str, Any]) -> list[str]:
    completeness = result.get("completeness")
    if completeness == "NO_SNAPSHOT":
        return ["NO_SNAPSHOT: downstream traversal unavailable; changed set only"]
    if completeness == "SKIPPED":
        return ["SKIPPED: graph snapshot was skipped; changed set only"]
    return []


def _mcp_payload(name: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": _schema_for_tool(name),
        "ok": True,
        "data": result,
        "warnings": _warnings_for_result(result),
        "meta": {"producer": {"tool": "heddle", "version": "0.1.0"}},
    }


def _tool_result(id_value: Any, name: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": id_value,
        "result": {
            "content": [
                {"type": "text", "text": json.dumps(_mcp_payload(name, result), sort_keys=True)}
            ]
        },
    }


def _error(id_value: Any, code: int, message: str, details: Any | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"jsonrpc": "2.0", "id": id_value, "error": error}


def _args(params: dict[str, Any]) -> dict[str, Any]:
    args = params.get("arguments") or {}
    if not isinstance(args, dict):
        raise ValueError("arguments must be an object")
    return args


def _repo_arg(args: dict[str, Any]) -> Path:
    repo = args.get("repo")
    if not isinstance(repo, str) or not repo:
        raise ValueError("repo is required and must be a non-empty string")
    return Path(repo)


def _string_arg(args: dict[str, Any], name: str) -> str:
    value = args.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} is required and must be a non-empty string")
    return value


def _changed_entity_key_ids(args: dict[str, Any]) -> list[int]:
    values = args.get("changed_entity_key_ids")
    if not isinstance(values, list):
        raise ValueError("changed_entity_key_ids is required and must be an array")
    try:
        return [int(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise ValueError("changed_entity_key_ids must contain integers") from exc


def _depth_arg(args: dict[str, Any]) -> int:
    try:
        depth = int(args.get("depth", 2))
    except (TypeError, ValueError) as exc:
        raise ValueError("depth must be an integer") from exc
    if depth < 0 or depth > 5:
        raise ValueError("depth must be between 0 and 5")
    return depth


def dispatch(request: dict[str, Any]) -> dict[str, Any]:
    method = request.get("method")
    id_value = request.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": id_value, "result": {"capabilities": {"tools": {}}}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": id_value, "result": {"tools": TOOLS}}
    if method != "tools/call":
        return _error(id_value, -32601, str(method))

    params = request.get("params") or {}
    name = params.get("name")
    try:
        args = _args(params)
        if name == "changed":
            return _tool_result(
                id_value,
                "changed",
                commands.changed(_repo_arg(args), args.get("rev_range")),
            )
        if name == "timeline":
            return _tool_result(
                id_value,
                "timeline",
                commands.timeline(_repo_arg(args), _string_arg(args, "entity")),
            )
        if name == "blast_radius":
            return _tool_result(
                id_value,
                "blast_radius",
                commands.blast_radius(
                    _repo_arg(args),
                    _changed_entity_key_ids(args),
                    _depth_arg(args),
                ),
            )
        if name == "reverify":
            return _tool_result(
                id_value,
                "reverify",
                commands.reverify(
                    _repo_arg(args),
                    _changed_entity_key_ids(args),
                    _depth_arg(args),
                ),
            )
    except ValueError as exc:
        return _error(id_value, -32602, "invalid params", {"reason": str(exc)})
    return _error(id_value, -32601, str(name))


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            print(
                json.dumps(
                    _error(
                        None,
                        -32700,
                        "parse error",
                        {"line": exc.lineno, "column": exc.colno},
                    )
                ),
                flush=True,
            )
            continue
        print(json.dumps(dispatch(request)), flush=True)
    return 0
