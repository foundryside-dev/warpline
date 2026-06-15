from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from warpline.errors import InvalidFilterError, InvalidSortError

# ---------------------------------------------------------------------------
# weft-reason output contract (G1, pm/2026-06-15-weft-reason-contract-G1.md)
# ---------------------------------------------------------------------------
# The canonical 11 reason classes. A degraded warpline list-ergonomics result
# (a cursor that points past the end, an overflow that spilled to a file) carries
# {reason_class, cause, fix} so the empty/partial is never byte-indistinguishable
# from an earned true-negative. ``clean`` omits cause/fix — the empty is earned.
REASON_CLASSES = frozenset(
    {
        "clean",
        "disabled",
        "unresolved_input",
        "rejected",
        "dead_path",
        "unreachable",
        "misrouted",
        "error",
        "scheme_mismatch",
        "stale",
        "partial",
    }
)


def reason(
    reason_class: str, *, cause: str | None = None, fix: str | None = None
) -> dict[str, Any]:
    """Build a weft-reason carrier. ``clean`` omits cause/fix; every other class
    MUST carry both (fix recruits the caller toward what they wanted)."""

    assert reason_class in REASON_CLASSES, f"{reason_class!r} not in the canonical 11"
    if reason_class == "clean":
        return {"reason_class": "clean"}
    assert cause and fix, f"non-clean reason {reason_class!r} requires both cause and fix"
    return {"reason_class": reason_class, "cause": cause, "fix": fix}


# ---------------------------------------------------------------------------
# Overflow affordance (new owner convention, piloted here)
# ---------------------------------------------------------------------------
# Any list-returning read offers a standardised lead-summary AND, when the result
# is oversized, emits a WARNING + dumps the FULL list to a file at project root
# for the agent to parse manually — instead of silently truncating OR flooding
# the caller's context. The dumped list is the complete, post-filter/sort set;
# the in-band response carries only the bounded lead window.
OVERFLOW_THRESHOLD = 200
_OVERFLOW_DIR = ".weft/warpline/overflow"


def _overflow_path(repo: Path, tool: str) -> Path:
    safe = tool.replace("/", "_")
    return repo.resolve() / _OVERFLOW_DIR / f"{safe}.json"


def apply_overflow(
    items: list[dict[str, Any]],
    *,
    repo: Path,
    tool: str,
    schema: str,
    threshold: int = OVERFLOW_THRESHOLD,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    """Bound an oversized list: keep a lead window in-band, spill the full set.

    Returns ``(lead_items, warnings, overflow_meta)``. When ``items`` fits under
    ``threshold`` the full list rides in-band, no file is written, and
    ``overflow_meta`` reports ``reason_class: clean``. When it overflows, the FULL
    list is dumped to a file at project root, only the first ``threshold`` items
    ride in-band, and the carrier reports ``partial`` with the dump path as the
    ``fix`` — the agent parses the file to get the rest.
    """

    total = len(items)
    if total <= threshold:
        return (
            items,
            [],
            {
                "total": total,
                "returned": total,
                "dumped_to": None,
                **reason("clean"),
            },
        )

    path = _overflow_path(repo, tool)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema": schema, "tool": tool, "total": total, "items": items}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    lead = items[:threshold]
    warnings = [
        f"OVERFLOW: {total} items exceed the {threshold}-item in-band cap; the lead {threshold} "
        f"ride in-band and the FULL list was written to {path} — parse that file for the rest"
    ]
    return (
        lead,
        warnings,
        {
            "total": total,
            "returned": threshold,
            "dumped_to": str(path),
            **reason(
                "partial",
                cause=f"{total} items exceeded the {threshold}-item in-band cap",
                fix=f"read the full list from {path}, or narrow with filters/window",
            ),
        },
    )


# ---------------------------------------------------------------------------
# Filtering — per-tool recognised keys with typed accessors
# ---------------------------------------------------------------------------
# A filter key the tool does not recognise is REJECTED loudly (invalid_filter) —
# never advertise-and-ignore. Each accessor pulls the comparable scalar from a
# list item (item shapes differ per tool, so accessors are tool-local closures).
def _entity_of(item: dict[str, Any]) -> dict[str, Any]:
    ent = item.get("entity")
    return ent if isinstance(ent, dict) else {}


def _path_from_locator(locator: Any) -> str | None:
    """Recover the file path a warpline locator embeds.

    Backfill mints ``file:<path>`` and ``python:<kind>:<path>::<qualname>``
    locators (``locators.py``/``git.py``), so the file path is recoverable from
    the locator for an entity carried without an explicit ``path`` field (the
    impact/reverify worklist entities). This is what makes ``group_by: file`` and
    a ``path_prefix`` filter meaningful on those tools."""

    if not isinstance(locator, str) or not locator:
        return None
    if locator.startswith("file:"):
        return locator[len("file:") :]
    if locator.startswith("python:"):
        rest = locator.split(":", 2)
        if len(rest) == 3:
            return rest[2].split("::", 1)[0]
    return None


def _path_of(item: dict[str, Any]) -> str | None:
    # change_list nests path in entity; timeline carries it flat; the impact /
    # reverify worklist entities carry only a locator → recover the path from it.
    flat = item.get("path")
    if isinstance(flat, str):
        return flat
    entity = _entity_of(item)
    nested = entity.get("path")
    if isinstance(nested, str):
        return nested
    return _path_from_locator(entity.get("locator"))


# Accessor → the scalar a filter/sort key reads from one item, per tool. Keeping
# these declarative makes "what does sort_by=path read?" auditable in one place.
_ACCESSORS: dict[str, dict[str, Callable[[dict[str, Any]], Any]]] = {
    "warpline_change_list": {
        "path": _path_of,
        "actor": lambda i: i.get("actor"),
        "change_kind": lambda i: i.get("change_kind"),
        "commit": lambda i: i.get("commit"),
        "changed_at": lambda i: i.get("changed_at"),
        "has_sei": lambda i: _entity_of(i).get("sei") is not None,
        "sei": lambda i: _entity_of(i).get("sei"),
    },
    "warpline_entity_timeline_get": {
        "path": _path_of,
        "actor": lambda i: i.get("actor"),
        "change_kind": lambda i: i.get("change_kind"),
        "commit": lambda i: i.get("commit"),
        "changed_at": lambda i: i.get("changed_at"),
    },
    "warpline_impact_radius_get": {
        "path": _path_of,
        "depth": lambda i: i.get("depth"),
        "confidence": lambda i: _min_edge_field(i, "confidence"),
        "edge_kind": lambda i: _min_edge_field(i, "kind"),
    },
    "warpline_reverify_worklist_get": {
        "path": _path_of,
        "depth": lambda i: i.get("depth"),
        "priority": lambda i: i.get("priority"),
        "reason": lambda i: i.get("reason"),
        "has_sei": lambda i: _entity_of(i).get("sei") is not None,
    },
}


def _none_accessor(_item: dict[str, Any]) -> Any:
    return None


def _false_accessor(_item: dict[str, Any]) -> Any:
    return False


def _min_edge_field(item: dict[str, Any], field: str) -> Any:
    edges = item.get("via_edges")
    if not isinstance(edges, list):
        return None
    vals = [
        str(e.get(field)) for e in edges if isinstance(e, dict) and e.get(field) is not None
    ]
    return min(vals) if vals else None


# Recognised filter keys per tool. ``path_prefix`` matches the start of the path;
# the rest are exact-equality on the accessor scalar. ``has_sei`` is a bool gate.
_FILTER_KEYS: dict[str, frozenset[str]] = {
    "warpline_change_list": frozenset(
        {"path_prefix", "change_kind", "actor", "commit", "since", "until", "has_sei"}
    ),
    "warpline_entity_timeline_get": frozenset(
        {"change_kind", "actor", "commit", "since", "until"}
    ),
    "warpline_impact_radius_get": frozenset({"path_prefix", "edge_kind", "confidence"}),
    "warpline_reverify_worklist_get": frozenset({"path_prefix", "priority", "reason", "has_sei"}),
}


def apply_filters(
    items: list[dict[str, Any]], *, tool: str, filters: Any
) -> list[dict[str, Any]]:
    """Keep only items matching every supplied filter. Unknown keys reject
    loudly (invalid_filter) — an advertised filter object the handler silently
    dropped would be the exact dead-input defect PDR-0023 kills."""

    if filters is None:
        return items
    if not isinstance(filters, dict):
        raise InvalidFilterError("filters must be an object of recognised filter keys")
    active = {k: v for k, v in filters.items() if v is not None}
    if not active:
        return items
    recognised = _FILTER_KEYS.get(tool, frozenset())
    unknown = set(active) - recognised
    if unknown:
        raise InvalidFilterError(
            f"unrecognised filter key(s) {sorted(unknown)} for {tool}; "
            f"recognised: {sorted(recognised)}"
        )
    accessors = _ACCESSORS.get(tool, {})

    def keep(item: dict[str, Any]) -> bool:
        for key, want in active.items():
            if key == "path_prefix":
                path = _path_of(item)
                if not (isinstance(path, str) and path.startswith(str(want))):
                    return False
            elif key == "since":
                got = accessors.get("changed_at", _none_accessor)(item)
                if not (isinstance(got, str) and got >= str(want)):
                    return False
            elif key == "until":
                got = accessors.get("changed_at", _none_accessor)(item)
                if not (isinstance(got, str) and got <= str(want)):
                    return False
            elif key == "has_sei":
                got = accessors.get("has_sei", _false_accessor)(item)
                if bool(got) != bool(want):
                    return False
            else:
                got = accessors.get(key, _none_accessor)(item)
                if got != want:
                    return False
        return True

    return [item for item in items if keep(item)]


# ---------------------------------------------------------------------------
# Sorting — per-tool recognised sort keys
# ---------------------------------------------------------------------------
_SORT_KEYS: dict[str, frozenset[str]] = {
    "warpline_change_list": frozenset({"changed_at", "path", "actor", "change_kind"}),
    "warpline_entity_timeline_get": frozenset({"changed_at", "commit"}),
    "warpline_entity_churn_count_get": frozenset({"churn_count", "sei"}),
    "warpline_impact_radius_get": frozenset({"depth", "confidence", "path"}),
    "warpline_reverify_worklist_get": frozenset({"priority", "depth", "changed_at"}),
}

# Priority is a categorical rank, not a string sort: P1 < P2 < P3 < unknown.
_PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4, "unknown": 99}


def apply_sort(
    items: list[dict[str, Any]], *, tool: str, sort_by: str | None, sort_order: str | None
) -> list[dict[str, Any]]:
    """Stable-sort the items by a recognised key. An unrecognised sort_by or
    sort_order rejects loudly (invalid_sort) rather than silently no-op'ing."""

    if sort_by is None:
        return items
    recognised = _SORT_KEYS.get(tool, frozenset())
    if sort_by not in recognised:
        raise InvalidSortError(
            f"unrecognised sort_by {sort_by!r} for {tool}; recognised: {sorted(recognised)}"
        )
    order = sort_order if sort_order is not None else "asc"
    if order not in {"asc", "desc"}:
        raise InvalidSortError(f"sort_order must be 'asc' or 'desc', got {order!r}")
    accessors = _ACCESSORS.get(tool, {})

    def _dict_get(item: dict[str, Any]) -> Any:
        return item.get(sort_by)

    accessor = accessors.get(sort_by, _dict_get)

    def keyfn(item: dict[str, Any]) -> Any:
        if sort_by == "priority":
            return _PRIORITY_RANK.get(str(item.get("priority")), 99)
        if sort_by == "depth":
            value = item.get("depth")
            return value if isinstance(value, int) else 0
        value = accessor(item)
        # None sorts last on asc / first on desc — never crashes a mixed column.
        return (value is None, value or "")

    return sorted(items, key=keyfn, reverse=(order == "desc"))


# ---------------------------------------------------------------------------
# Cursor pagination — opaque offset cursor over the post-filter/sort list
# ---------------------------------------------------------------------------
# The cursor is an opaque, self-describing offset token. A caller pages by
# echoing back ``page.next_cursor`` until ``has_more`` is false. A malformed
# cursor rejects loudly; a cursor past the end is an honest empty page carrying a
# weft-reason ``partial`` carrier, never a silent clean-empty.
_CURSOR_PREFIX = "warpline:cursor:"


def encode_cursor(offset: int) -> str:
    return f"{_CURSOR_PREFIX}{offset}"


def decode_cursor(cursor: Any) -> int:
    if cursor is None:
        return 0
    if not isinstance(cursor, str) or not cursor.startswith(_CURSOR_PREFIX):
        raise InvalidSortError(
            f"cursor must be an opaque {_CURSOR_PREFIX}<n> token from a prior page.next_cursor"
        )
    try:
        offset = int(cursor[len(_CURSOR_PREFIX) :])
    except ValueError as exc:
        raise InvalidSortError("malformed cursor offset") from exc
    if offset < 0:
        raise InvalidSortError("cursor offset must be non-negative")
    return offset


def apply_page(
    items: list[dict[str, Any]], *, limit: int, cursor: Any
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Slice ``[offset, offset+limit)`` and build the page descriptor.

    Returns ``(page_items, page)``. ``page`` carries ``limit``, ``next_cursor``
    (or null at the end), ``has_more``, and a weft-reason carrier: ``clean`` for
    a normal page, ``partial`` when a cursor lands at or past the end (an honest
    empty page, never a silent clean-empty)."""

    offset = decode_cursor(cursor)
    total = len(items)
    window = items[offset : offset + limit]
    next_offset = offset + len(window)
    has_more = next_offset < total
    page: dict[str, Any] = {
        "limit": limit,
        "next_cursor": encode_cursor(next_offset) if has_more else None,
        "has_more": has_more,
    }
    if offset >= total and total > 0:
        page.update(
            reason(
                "partial",
                cause=f"cursor offset {offset} is at/past the end of {total} item(s)",
                fix="page from the start (omit cursor) or re-query; nothing remains at this offset",
            )
        )
    else:
        page.update(reason("clean"))
    return window, page


# ---------------------------------------------------------------------------
# group_by — bucket the (filtered, sorted) items, preserving order within bucket
# ---------------------------------------------------------------------------
_GROUP_KEYS: dict[str, frozenset[str]] = {
    "warpline_reverify_worklist_get": frozenset({"entity", "file", "reason", "none"}),
}


def _group_accessor(tool: str, group_by: str) -> Callable[[dict[str, Any]], str]:
    if group_by == "entity":
        return lambda i: str(_entity_of(i).get("sei") or _entity_of(i).get("locator") or "unknown")
    if group_by == "file":
        return lambda i: str(_path_of(i) or "unknown")
    if group_by == "reason":
        return lambda i: str(i.get("reason") or "unknown")
    return lambda _i: "all"


def apply_group_by(
    items: list[dict[str, Any]], *, tool: str, group_by: str | None
) -> dict[str, list[dict[str, Any]]] | None:
    """Bucket items by a recognised group key, or None when no grouping was asked.

    ``group_by: "none"`` is an explicit no-grouping request and returns None
    (the flat list rides as usual). An unrecognised key rejects loudly."""

    if group_by is None or group_by == "none":
        return None
    recognised = _GROUP_KEYS.get(tool, frozenset())
    if group_by not in recognised:
        raise InvalidSortError(
            f"unrecognised group_by {group_by!r} for {tool}; recognised: {sorted(recognised)}"
        )
    accessor = _group_accessor(tool, group_by)
    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        buckets.setdefault(accessor(item), []).append(item)
    return buckets
