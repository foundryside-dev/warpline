from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from heddle import commands

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
    },
]


def _tool_result(id_value: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": id_value,
        "result": {"content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}]},
    }


def dispatch(request: dict[str, Any]) -> dict[str, Any]:
    method = request.get("method")
    id_value = request.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": id_value, "result": {"capabilities": {"tools": {}}}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": id_value, "result": {"tools": TOOLS}}
    if method != "tools/call":
        return {"jsonrpc": "2.0", "id": id_value, "error": {"code": -32601, "message": str(method)}}

    params = request.get("params") or {}
    name = params.get("name")
    args = params.get("arguments") or {}
    if name == "changed":
        return _tool_result(id_value, commands.changed(Path(args["repo"]), args.get("rev_range")))
    if name == "timeline":
        return _tool_result(id_value, commands.timeline(Path(args["repo"]), args["entity"]))
    if name == "blast_radius":
        return _tool_result(
            id_value,
            commands.blast_radius(
                Path(args["repo"]),
                [int(value) for value in args["changed_entity_key_ids"]],
                int(args.get("depth", 2)),
            ),
        )
    return {"jsonrpc": "2.0", "id": id_value, "error": {"code": -32601, "message": str(name)}}


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        print(json.dumps(dispatch(json.loads(line))), flush=True)
    return 0
