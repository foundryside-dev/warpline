from __future__ import annotations

from typing import Any

from heddle.errors import InvalidChangedRefsError, InvalidEntityRefError

# Accepted entity_ref kinds (FROZEN input ref shape).
REF_KINDS = frozenset(
    {"auto", "locator", "sei", "path", "qualname", "heddle_entity_key_id"}
)


def parse_entity_ref(value: Any) -> dict[str, str]:
    """Normalise a frozen entity_ref ({kind, value}) or a bare string.

    A bare string is treated as ``kind: auto``. Raises InvalidEntityRefError on
    an unrecognised shape.
    """

    if isinstance(value, str) and value:
        return {"kind": "auto", "value": value}
    if isinstance(value, dict):
        kind = value.get("kind", "auto")
        raw = value.get("value")
        if kind in REF_KINDS and isinstance(raw, (str, int)) and str(raw):
            return {"kind": str(kind), "value": str(raw)}
    raise InvalidEntityRefError(f"unrecognised entity_ref: {value!r}")


def parse_changed_refs(value: Any) -> list[dict[str, str]]:
    """Normalise a list of frozen changed_refs ({kind, value} objects)."""

    if value is None:
        return []
    if not isinstance(value, list):
        raise InvalidChangedRefsError("changed_refs must be a list of {kind, value} objects")
    refs: list[dict[str, str]] = []
    for item in value:
        try:
            refs.append(parse_entity_ref(item))
        except InvalidEntityRefError as exc:
            raise InvalidChangedRefsError(str(exc)) from exc
    return refs


def entity_view(
    row: dict[str, Any] | None,
    *,
    include_key_id: bool = False,
    path: str | None = None,
) -> dict[str, Any]:
    """Build the FROZEN per-entity view carrying BOTH locator and sei.

    Every heddle-outbound entity carries ``locator`` and ``sei`` (``sei: null``
    when heddle has not resolved one). ``heddle_entity_key_id`` is internal and
    only echoed for compatibility — never a federation key.
    """

    row = row or {}
    sei = row.get("sei")
    view: dict[str, Any] = {
        "locator": row.get("locator"),
        "sei": sei if isinstance(sei, str) and sei else None,
    }
    if include_key_id:
        view["heddle_entity_key_id"] = row.get("id") or row.get("entity_key_id")
    if path is not None:
        view["path"] = path
    return view


def changed_ref_for_row(row: dict[str, Any]) -> dict[str, str]:
    """A changed_ref preferring sei, falling back to locator (never key id)."""

    sei = row.get("sei")
    if isinstance(sei, str) and sei:
        return {"kind": "sei", "value": sei}
    return {"kind": "locator", "value": str(row.get("locator"))}
