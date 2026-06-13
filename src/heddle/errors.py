from __future__ import annotations

from typing import Any

# FROZEN heddle.error.v1 vocabulary (see
# /home/john/weft/pm/2026-06-13-heddle-interface-lock.md "canonical error envelope").
# Both sets are CLOSED — additions are a v2 contract, never a mutation of v1.
RETRYABILITY = frozenset({"retry_safe", "retry_with_changes", "fatal"})
ERROR_CODES = frozenset(
    {
        "missing_required_field",
        "invalid_repo",
        "invalid_rev_range",
        "invalid_entity_ref",
        "invalid_changed_refs",
        "invalid_depth",
        "invalid_filter",
        "invalid_sort",
        "peer_unavailable",
        "snapshot_unavailable",
        "internal_error",
    }
)


class HeddleError(Exception):
    """Base for the FROZEN heddle.error.v1 recoverable-error contract.

    Subclasses pin a vocabulary ``code`` and ``retryability``; the instance
    message becomes ``details.message`` so callers switch on ``error_code``
    (closed set) rather than parsing prose.
    """

    code = "internal_error"
    rejected_field: str | None = None
    retryability = "fatal"
    hint = "Inspect the request and retry after correcting the rejected input."

    def __init__(
        self,
        message: str | None = None,
        *,
        rejected_field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or self.hint)
        if rejected_field is not None:
            self.rejected_field = rejected_field
        self._details = details or {}

    def to_error_data(self) -> dict[str, Any]:
        assert self.code in ERROR_CODES, f"{self.code} not in frozen error_code vocabulary"
        assert self.retryability in RETRYABILITY, f"{self.retryability} not in frozen retryability"
        details = dict(self._details)
        message = str(self)
        if message:
            details.setdefault("message", message)
        data: dict[str, Any] = {
            "schema": "heddle.error.v1",
            "error_code": self.code,
            "retryability": self.retryability,
            "hint": self.hint,
            "details": details,
        }
        if self.rejected_field is not None:
            data["rejected_field"] = self.rejected_field
        return data


class MissingRequiredFieldError(HeddleError):
    code = "missing_required_field"
    retryability = "retry_with_changes"
    hint = "Supply the required argument and retry the same tool."


class InvalidRepoError(HeddleError):
    code = "invalid_repo"
    rejected_field = "repo"
    retryability = "retry_with_changes"
    hint = "Pass an absolute path to a git repository heddle can read."


class BadRevisionError(HeddleError):
    code = "invalid_rev_range"
    rejected_field = "rev_range"
    retryability = "retry_with_changes"
    hint = "Pass a git revision range resolvable from repo, e.g. HEAD~1..HEAD."


class InvalidEntityRefError(HeddleError):
    code = "invalid_entity_ref"
    rejected_field = "entity_ref"
    retryability = "retry_with_changes"
    hint = "Pass an entity_ref with a known kind (auto|locator|sei|path|qualname)."


class InvalidChangedRefsError(HeddleError):
    code = "invalid_changed_refs"
    rejected_field = "changed_refs"
    retryability = "retry_with_changes"
    hint = "Pass changed_refs as a list of {kind, value} objects, SEIs preferred."


class InvalidDepthError(HeddleError):
    code = "invalid_depth"
    rejected_field = "depth"
    retryability = "retry_with_changes"
    hint = "Pass an integer depth between 0 and 5."


class InvalidFilterError(HeddleError):
    code = "invalid_filter"
    rejected_field = "filters"
    retryability = "retry_with_changes"
    hint = "Pass filters as an object of recognised filter keys."


class InvalidSortError(HeddleError):
    code = "invalid_sort"
    retryability = "retry_with_changes"
    hint = "Pass a recognised sort_by/sort_order for this tool."


class PeerUnavailableError(HeddleError):
    code = "peer_unavailable"
    retryability = "retry_safe"
    hint = "A federation peer was unreachable; retry once the peer is available."


class SnapshotUnavailableError(HeddleError):
    code = "snapshot_unavailable"
    retryability = "retry_with_changes"
    hint = "Run heddle_edge_snapshot_capture before requesting graph-enriched output."


class InternalError(HeddleError):
    code = "internal_error"
    retryability = "fatal"
    hint = "Inspect server logs before retrying; this is a heddle defect."
