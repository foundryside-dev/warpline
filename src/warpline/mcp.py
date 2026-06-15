from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from warpline import __version__, commands
from warpline.errors import (
    InternalError,
    InvalidChangedRefsError,
    InvalidDepthError,
    MissingRequiredFieldError,
    WarplineError,
)

CORE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "schema": {"type": "string"},
        "ok": {"type": "boolean"},
        "query": {"type": "object"},
        "data": {"type": "object"},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "next_actions": {"type": "object"},
        "enrichment": {"type": "object"},
        "meta": {"type": "object"},
    },
    "required": ["schema", "ok", "query", "data", "warnings", "next_actions", "enrichment", "meta"],
    "additionalProperties": True,
}

SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26")


def _metadata(
    *,
    read_only: bool,
    writes_local_state: bool,
    idempotent: bool,
    mutates_paths: list[str],
    federation_dependencies: list[str] | None = None,
) -> dict[str, object]:
    return {
        "read_only": read_only,
        "writes_local_state": writes_local_state,
        "idempotent": idempotent,
        "mutates_paths": mutates_paths,
        "requires_repo": True,
        "federation_dependencies": federation_dependencies or [],
        "concurrency": "safe; serialized by SQLite writer locks for local store writes",
        "local_only": True,
        "peer_side_effects": [],
    }


# canonical (contract) name → (endorsed name, shim, schema, description, inputSchema, metadata)
_REPO_PROP = {"repo": {"type": "string"}}


def _tool_spec(
    *,
    endorsed: str,
    shim: str,
    schema: str,
    description: str,
    input_properties: dict[str, Any],
    required: list[str],
    metadata: dict[str, object],
) -> dict[str, Any]:
    return {
        "endorsed": endorsed,
        "shim": shim,
        "schema": schema,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": {**_REPO_PROP, **input_properties},
            "required": required,
            "additionalProperties": False,
        },
        "metadata": metadata,
    }


_READ_META = _metadata(
    read_only=True, writes_local_state=True, idempotent=True, mutates_paths=[".weft/warpline/"]
)
_READ_META_LW = _metadata(
    read_only=True,
    writes_local_state=True,
    idempotent=True,
    mutates_paths=[".weft/warpline/"],
    federation_dependencies=["loomweave snapshot optional"],
)

_FILTERS = {"type": "object"}
_REF = {"type": "object", "properties": {"kind": {"type": "string"}, "value": {}}}

TOOL_SPECS = [
    _tool_spec(
        endorsed="warpline_change_list",
        shim="changed",
        schema=commands.SCHEMA_CHANGE_LIST,
        description=(
            "List changed entities for an ingested repo and get the ready-to-call "
            "reverify/impact next actions. Local-only; may initialize .weft/warpline state."
        ),
        input_properties={
            "rev_range": {"type": "string"},
            "base_ref": {"type": "string"},
            "head_ref": {"type": "string"},
            "filters": _FILTERS,
            "sort_by": {"type": "string"},
            "sort_order": {"type": "string"},
            "limit": {"type": "integer"},
            "cursor": {"type": ["string", "null"]},
            "include_next_actions": {"type": "boolean"},
        },
        required=["repo"],
        metadata=_READ_META,
    ),
    _tool_spec(
        endorsed="warpline_entity_timeline_get",
        shim="timeline",
        schema=commands.SCHEMA_ENTITY_TIMELINE,
        description=(
            "Ordered change history for one entity ref. warpline reports only whether it "
            "resolved a SEI (sei_resolution); it never claims lineage."
        ),
        input_properties={
            "entity_ref": _REF,
            "entity": {"type": "string"},
            "filters": _FILTERS,
            "sort_by": {"type": "string"},
            "sort_order": {"type": "string"},
            "limit": {"type": "integer"},
            "cursor": {"type": ["string", "null"]},
        },
        required=["repo"],
        metadata=_READ_META,
    ),
    _tool_spec(
        endorsed="warpline_entity_churn_count_get",
        shim="churn",
        schema=commands.SCHEMA_ENTITY_CHURN_COUNT,
        description=(
            "Per-entity change-event count over an optional window (SEIs preferred). A "
            "never-observed entity returns churn_count 0, not an error."
        ),
        input_properties={
            "entity_refs": {"type": "array", "items": _REF},
            "window": {"type": "object"},
            "sort_by": {"type": "string"},
            "sort_order": {"type": "string"},
            "limit": {"type": "integer"},
            "cursor": {"type": ["string", "null"]},
        },
        required=["repo", "entity_refs"],
        metadata=_READ_META,
    ),
    _tool_spec(
        endorsed="warpline_impact_radius_get",
        shim="blast_radius",
        schema=commands.SCHEMA_IMPACT_RADIUS,
        description=(
            "Downstream affected entities from stored dated snapshots, with mandatory "
            "completeness+staleness. NO_SNAPSHOT is an honest changed-set-only answer."
        ),
        input_properties={
            "rev_range": {"type": "string"},
            "changed_refs": {"type": "array", "items": _REF},
            "changed_entity_key_ids": {"type": "array", "items": {"type": "integer"}},
            "depth": {"type": "integer", "minimum": 0, "maximum": 5},
            "filters": _FILTERS,
            "sort_by": {"type": "string"},
            "sort_order": {"type": "string"},
            "limit": {"type": "integer"},
            "cursor": {"type": ["string", "null"]},
        },
        required=["repo"],
        metadata=_READ_META_LW,
    ),
    _tool_spec(
        endorsed="warpline_reverify_worklist_get",
        shim="reverify",
        schema=commands.SCHEMA_REVERIFY_WORKLIST,
        description=(
            "Render the agent worklist to recheck before claiming completion. Sibling "
            "enrichment is advisory and never gates; absence is explicit, never clean."
        ),
        input_properties={
            "rev_range": {"type": "string"},
            "changed_refs": {"type": "array", "items": _REF},
            "changed_entity_key_ids": {"type": "array", "items": {"type": "integer"}},
            "depth": {"type": "integer", "minimum": 0, "maximum": 5},
            "filters": _FILTERS,
            "sort_by": {"type": "string"},
            "sort_order": {"type": "string"},
            "group_by": {"type": "string"},
            "limit": {"type": "integer"},
            "cursor": {"type": ["string", "null"]},
            # include_federation REMOVED (G2): it is a cross-member SEAM affordance
            # (it would make warpline consult OTHER members). Under the
            # hub-blesses-every-seam ruling it is NOT wired in an intra-member
            # strike, and an advertised-but-dead field is forbidden, so the
            # advertisement is withdrawn until the hub authors+blesses that seam.
        },
        required=["repo"],
        metadata=_READ_META_LW,
    ),
    _tool_spec(
        endorsed="warpline_edge_snapshot_capture",
        shim="capture_snapshot",
        schema=commands.SCHEMA_EDGE_SNAPSHOT,
        description=(
            "Capture dated loomweave edges into warpline's local store. Mutates ONLY "
            ".weft/warpline state; never a sibling repo. loomweave command is server config."
        ),
        input_properties={
            "commit": {"type": "string"},
            "mode": {"type": "string", "enum": ["full", "changed_only"]},
            "changed_refs": {"type": "array", "items": _REF},
            "if_stale_after": {"type": ["string", "null"]},
            "max_entities": {"type": "integer"},
            "dry_run": {"type": "boolean"},
            "idempotency_key": {"type": ["string", "null"]},
        },
        required=["repo"],
        metadata=_metadata(
            read_only=False,
            writes_local_state=True,
            idempotent=True,
            mutates_paths=[".weft/warpline/"],
            federation_dependencies=["loomweave"],
        ),
    ),
]


def _build_tools() -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for spec in TOOL_SPECS:
        for name in (spec["endorsed"], spec["shim"]):
            tools.append(
                {
                    "name": name,
                    "description": spec["description"],
                    "inputSchema": spec["inputSchema"],
                    "outputSchema": CORE_OUTPUT_SCHEMA,
                    "metadata": spec["metadata"],
                }
            )
    return tools


TOOLS = _build_tools()


# --------------------------------------------------------------------------- args
def _args(params: dict[str, Any]) -> dict[str, Any]:
    args = params.get("arguments") or {}
    if not isinstance(args, dict):
        raise MissingRequiredFieldError("arguments must be an object", rejected_field="arguments")
    return args


def _repo_arg(args: dict[str, Any]) -> Path:
    repo = args.get("repo")
    if not isinstance(repo, str) or not repo:
        raise MissingRequiredFieldError(
            "repo is required and must be a non-empty string", rejected_field="repo"
        )
    path = Path(repo)
    return path


def _entity_ref_arg(args: dict[str, Any]) -> Any:
    if "entity_ref" in args and args["entity_ref"] is not None:
        return args["entity_ref"]
    entity = args.get("entity")
    if isinstance(entity, str) and entity:
        return entity
    raise MissingRequiredFieldError(
        "entity_ref is required", rejected_field="entity_ref"
    )


def _depth_arg(args: dict[str, Any]) -> int:
    try:
        depth = int(args.get("depth", 2))
    except (TypeError, ValueError) as exc:
        raise InvalidDepthError("depth must be an integer") from exc
    if depth < 0 or depth > 5:
        raise InvalidDepthError("depth must be between 0 and 5")
    return depth


def _key_ids_arg(args: dict[str, Any]) -> list[int]:
    values = args.get("changed_entity_key_ids")
    if values is None:
        return []
    if not isinstance(values, list):
        raise InvalidChangedRefsError(
            "changed_entity_key_ids must be an array of integers",
            rejected_field="changed_entity_key_ids",
        )
    try:
        return [int(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise InvalidChangedRefsError(
            "changed_entity_key_ids must contain integers",
            rejected_field="changed_entity_key_ids",
        ) from exc


def _limit_arg(args: dict[str, Any], default: int) -> int:
    value = args.get("limit", default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------- handlers
def _opt_str(args: dict[str, Any], key: str) -> str | None:
    value = args.get(key)
    return value if isinstance(value, str) else None


def _h_change_list(args: dict[str, Any]) -> dict[str, Any]:
    return commands.change_list(
        _repo_arg(args),
        args.get("rev_range"),
        base_ref=_opt_str(args, "base_ref"),
        head_ref=_opt_str(args, "head_ref"),
        filters=args.get("filters"),
        sort_by=_opt_str(args, "sort_by"),
        sort_order=_opt_str(args, "sort_order"),
        cursor=args.get("cursor"),
        include_next_actions=bool(args.get("include_next_actions", True)),
        limit=_limit_arg(args, 50),
    )


def _h_timeline(args: dict[str, Any]) -> dict[str, Any]:
    return commands.entity_timeline(
        _repo_arg(args),
        _entity_ref_arg(args),
        filters=args.get("filters"),
        sort_by=_opt_str(args, "sort_by"),
        sort_order=_opt_str(args, "sort_order"),
        cursor=args.get("cursor"),
        limit=_limit_arg(args, 50),
    )


def _h_churn(args: dict[str, Any]) -> dict[str, Any]:
    if "entity_refs" not in args:
        raise MissingRequiredFieldError(
            "entity_refs is required", rejected_field="entity_refs"
        )
    return commands.entity_churn_count(
        _repo_arg(args),
        args.get("entity_refs"),
        window=args.get("window"),
        sort_by=str(args.get("sort_by", "churn_count")),
        sort_order=str(args.get("sort_order", "desc")),
        cursor=args.get("cursor"),
        limit=_limit_arg(args, 100),
    )


def _h_impact(args: dict[str, Any]) -> dict[str, Any]:
    return commands.impact_radius(
        _repo_arg(args),
        _key_ids_arg(args),
        _depth_arg(args),
        rev_range=args.get("rev_range"),
        changed_refs=args.get("changed_refs"),
        filters=args.get("filters"),
        sort_by=_opt_str(args, "sort_by"),
        sort_order=_opt_str(args, "sort_order"),
        cursor=args.get("cursor"),
        limit=_limit_arg(args, 100),
    )


def _h_reverify(args: dict[str, Any]) -> dict[str, Any]:
    return commands.reverify_worklist(
        _repo_arg(args),
        _key_ids_arg(args),
        _depth_arg(args),
        rev_range=args.get("rev_range"),
        changed_refs=args.get("changed_refs"),
        filters=args.get("filters"),
        sort_by=_opt_str(args, "sort_by"),
        sort_order=_opt_str(args, "sort_order"),
        group_by=_opt_str(args, "group_by"),
        cursor=args.get("cursor"),
        limit=_limit_arg(args, 100),
    )


def _h_capture(args: dict[str, Any]) -> dict[str, Any]:
    return commands.capture_snapshot(
        _repo_arg(args),
        commit=args.get("commit"),
        mode=str(args.get("mode", "full")),
        dry_run=bool(args.get("dry_run", False)),
        changed_refs=args.get("changed_refs"),
        if_stale_after=args.get("if_stale_after"),
        max_entities=args.get("max_entities"),
        idempotency_key=args.get("idempotency_key"),
    )


_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}
for _spec, _handler in zip(
    TOOL_SPECS,
    [_h_change_list, _h_timeline, _h_churn, _h_impact, _h_reverify, _h_capture],
    strict=True,
):
    _HANDLERS[_spec["endorsed"]] = _handler
    _HANDLERS[_spec["shim"]] = _handler


# Honesty invariant (PDR-0023): an inputSchema field that no handler consumes is
# DEAD INPUT — the schema advertises a knob, the caller turns it, and nothing
# happens, byte-indistinguishable from honoring it. Each tool declares EXACTLY
# the schema fields its handler reads (honoring them, or rejecting them loudly).
# The startup assertion below fails closed if any advertised field is neither
# consumed nor explicitly tracked as a named fast-follow, so a NEW
# advertise-and-ignore field can never silently ship.
# Every advertised list-ergonomics knob is now wired (G2): filters / sort_by /
# sort_order / cursor / group_by are honored by the handler (or loudly rejected
# on a bad value) for every read tool that advertises them. base_ref/head_ref
# (an explicit two-ended rev range) and include_next_actions are likewise wired.
_HANDLER_CONSUMES: dict[str, frozenset[str]] = {
    "warpline_change_list": frozenset(
        {
            "repo",
            "rev_range",
            "base_ref",
            "head_ref",
            "filters",
            "sort_by",
            "sort_order",
            "cursor",
            "include_next_actions",
            "limit",
        }
    ),
    "warpline_entity_timeline_get": frozenset(
        {"repo", "entity_ref", "entity", "filters", "sort_by", "sort_order", "cursor", "limit"}
    ),
    "warpline_entity_churn_count_get": frozenset(
        {"repo", "entity_refs", "window", "sort_by", "sort_order", "cursor", "limit"}
    ),
    "warpline_impact_radius_get": frozenset(
        {
            "repo",
            "rev_range",
            "changed_refs",
            "changed_entity_key_ids",
            "depth",
            "filters",
            "sort_by",
            "sort_order",
            "cursor",
            "limit",
        }
    ),
    "warpline_reverify_worklist_get": frozenset(
        {
            "repo",
            "rev_range",
            "changed_refs",
            "changed_entity_key_ids",
            "depth",
            "filters",
            "sort_by",
            "sort_order",
            "group_by",
            "cursor",
            "limit",
        }
    ),
    # capture honors or loudly rejects EVERY advertised field: no fast-follow
    # placeholders remain on this tool.
    "warpline_edge_snapshot_capture": frozenset(
        {
            "repo",
            "commit",
            "mode",
            "changed_refs",
            "if_stale_after",
            "max_entities",
            "dry_run",
            "idempotency_key",
        }
    ),
}

# The fast-follow placeholder set has shrunk to EMPTY for every tool (G2): there
# is no advertised-but-dead field left in warpline. The cross-member seam knob
# include_federation was REMOVED from the schema (not parked here as dead) and
# returns only when the hub authors+blesses that seam. The assertion below still
# catches any NEW advertise-and-ignore field — the structural guarantee, not a
# tolerance list.
_KNOWN_FASTFOLLOW_DEAD: dict[str, frozenset[str]] = {
    "warpline_change_list": frozenset(),
    "warpline_entity_timeline_get": frozenset(),
    "warpline_entity_churn_count_get": frozenset(),
    "warpline_impact_radius_get": frozenset(),
    "warpline_reverify_worklist_get": frozenset(),
    "warpline_edge_snapshot_capture": frozenset(),
}


def assert_inputschema_consumed() -> None:
    """Fail closed if any advertised inputSchema field is unaccounted-for.

    Every advertised field must be EITHER consumed by the handler (honored or
    loudly rejected — declared in ``_HANDLER_CONSUMES``) OR a named fast-follow
    placeholder (``_KNOWN_FASTFOLLOW_DEAD``). A field in neither set is silent
    dead input — the exact defect PDR-0023 kills — and halts startup. A declared
    field absent from the schema is stale handler/schema drift and also halts.
    Run at import time and re-asserted by the contract test.
    """

    for spec in TOOL_SPECS:
        endorsed = spec["endorsed"]
        advertised = frozenset(spec["inputSchema"]["properties"].keys())
        consumed = _HANDLER_CONSUMES.get(endorsed)
        assert consumed is not None, f"no consumed-field declaration for tool {endorsed!r}"
        known_dead = _KNOWN_FASTFOLLOW_DEAD.get(endorsed, frozenset())
        accounted = consumed | known_dead
        for name in (endorsed, spec["shim"]):
            unaccounted = advertised - accounted
            assert not unaccounted, (
                f"{name}: inputSchema advertises field(s) {sorted(unaccounted)} that the handler "
                "neither honors, rejects, nor tracks as a named fast-follow — silent DEAD INPUT "
                "(PDR-0023 honesty invariant)"
            )
            ghost = consumed - advertised
            assert not ghost, (
                f"{name}: handler declares consumed field(s) {sorted(ghost)} not in the "
                "frozen inputSchema — stale handler/schema drift"
            )


# Fail closed at module import (server startup) — never ship advertise-and-ignore.
assert_inputschema_consumed()


def _tool_result(id_value: Any, envelope: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": id_value,
        "result": {
            "structuredContent": envelope,
            "content": [{"type": "text", "text": json.dumps(envelope, sort_keys=True)}],
        },
    }


def _error(id_value: Any, code: int, message: str, data: Any | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": id_value, "error": error}


def _initialize_result(params: dict[str, Any]) -> dict[str, Any]:
    requested = params.get("protocolVersion")
    protocol = (
        requested if requested in SUPPORTED_PROTOCOL_VERSIONS else SUPPORTED_PROTOCOL_VERSIONS[-1]
    )
    return {
        "protocolVersion": protocol,
        "serverInfo": {"name": "warpline", "version": __version__},
        "capabilities": {"tools": {}},
        "instructions": (
            "Use tools/list, then tools/call. Endorsed names and short shims return "
            "identical schema+data. Tool errors are structured in JSON-RPC error.data "
            "with schema warpline.error.v1 and a closed error_code/retryability vocab."
        ),
    }


def dispatch(request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request, dict):
        return _error(
            None,
            -32600,
            "invalid request",
            MissingRequiredFieldError("request must be an object").to_error_data(),
        )
    method = request.get("method")
    id_value = request.get("id")
    params = request.get("params") or {}
    if not isinstance(params, dict):
        return _error(
            id_value,
            -32602,
            "invalid params",
            MissingRequiredFieldError(
                "params must be an object", rejected_field="params"
            ).to_error_data(),
        )
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": id_value, "result": _initialize_result(params)}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": id_value, "result": {"tools": TOOLS}}
    if method != "tools/call":
        return _error(
            id_value,
            -32601,
            str(method),
            MissingRequiredFieldError("unknown method", rejected_field="method").to_error_data(),
        )

    name = params.get("name")
    handler = _HANDLERS.get(name) if isinstance(name, str) else None
    if handler is None:
        return _error(
            id_value,
            -32601,
            str(name),
            MissingRequiredFieldError("unknown tool", rejected_field="name").to_error_data(),
        )
    try:
        args = _args(params)
        return _tool_result(id_value, handler(args))
    except WarplineError as exc:
        return _error(id_value, -32602, "invalid params", exc.to_error_data())
    except Exception as exc:
        return _error(id_value, -32603, "internal error", InternalError().to_error_data() | {
            "details": {"exception_type": type(exc).__name__}
        })


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            print(
                json.dumps(
                    _error(None, -32700, "parse error", {"line": exc.lineno, "column": exc.colno})
                ),
                flush=True,
            )
            continue
        print(json.dumps(dispatch(request)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
