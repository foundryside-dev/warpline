"""Temporal Change-Oriented Posture (COP) internals — Rung 2 Track D.

The COP read surface answers "for THIS change frame, what is the cross-member
posture, and which members did we actually consult?". It is composed of two
read-time, never-gating, no-mirror steps:

  * :func:`resolve_frame` turns a *frame spec* (``rev_range`` / ``time_window`` /
    ``sei`` / ``branch_sha`` / ``edit``) into the warpline-local change items the
    frame selects, plus an echo of how the frame resolved and any honest
    degradation warning. It reads ONLY existing store methods + git; it mints no
    identifier and writes nothing.
  * :func:`compose_temporal_cop` consults the federation (reusing the three
    ``_consult_*`` from :mod:`warpline.federation` VERBATIM) and wraps the result
    in a coverage block. ``coverage.dark_sectors`` is the load-bearing honesty
    surface: a member we could not consult is named as a dark sector with its own
    reason class, NEVER silently dropped to look like an earned-clean empty.

R9: this module imports the consults from :mod:`warpline.federation`;
``federation.py`` NEVER imports ``cop.py`` (the edge is one-way).

The honesty invariant (PDR-0023) governs the degradation path: every COP/frame
output carries a ``weft_reason_class`` drawn from the canonical reason vocab
(:data:`warpline.listing.REASON_CLASSES`). ``clean`` means the frame resolved the
change set it was asked for; any other class means the frame honestly degraded
(e.g. a ``rev_range`` whose SHAs no longer exist after a squash-merge collapsed
and the feature branch was deleted) and the ``frame`` echo carries the cause/fix.

This module is INTERNAL. The PUBLIC MCP/CLI COP tool surface is interface-pending
(it is NOT one of the six frozen v1 tools); the non-frozen internal ``warpline
cop`` CLI verb exists only to run the end-to-end reconstruction demo.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from warpline._blast import rev_range_commits
from warpline.errors import BadRevisionError
from warpline.federation import (
    FEDERATION_MEMBERS,
    LegisClient,
    RiskClient,
    _consult_filigree,
    _consult_legis,
    _consult_wardline,
)
from warpline.listing import reason
from warpline.refs import entity_view
from warpline.siblings import WorkClient
from warpline.store import WarplineStore

# Frame kinds this module resolves. ``branch_sha`` is the squash-merge / rewritten
# history case: until ``detected_branch`` (Rung 1b) is populated and an episode
# boundary is ratified, it falls back to a rev-range resolution WITH a warning.
FRAME_KINDS = ("rev_range", "time_window", "sei", "branch_sha", "edit")


def _item_from_event(event: dict[str, Any]) -> dict[str, Any]:
    """Shape a stored change event as a COP item.

    The ``entity`` sub-dict matches the federation consult contract
    (``entity.locator`` / ``entity.sei``) so the three ``_consult_*`` can read it
    verbatim. The anchor columns (Rung 1b) ride along when present.
    """

    path = event.get("path")
    view = entity_view(event, include_key_id=True, path=str(path) if path else None)
    return {
        "change_id": f"warpline:change:{event.get('change_event_id')}",
        "entity": view,
        "change_kind": event.get("change_kind"),
        "actor": event.get("actor"),
        "commit": event.get("commit_sha"),
        "changed_at": event.get("changed_at"),
        "detected_branch": event.get("detected_branch"),
        "detected_head_sha": event.get("detected_head_sha"),
    }


def _safe_rev_range_commits(
    repo: Path, rev_range: str | None
) -> tuple[set[str] | None, str | None]:
    """Resolve a rev-range fail-soft for COP.

    A frame may name a rev-range whose commits were rewritten away (squash-merge
    collapse, branch deletion, GC) — git then exits non-zero and
    :func:`rev_range_commits` raises ``BadRevisionError``. For a READ-time COP
    that is not an error; it is honest degradation. Returns ``(commit_shas,
    bad_detail)``: on a bad range, ``(set(), <detail>)`` so the caller resolves to
    an empty change set with an ``unresolved_input`` reason, never a crash.
    """

    try:
        return rev_range_commits(repo, rev_range), None
    except BadRevisionError as exc:
        return set(), str(exc)


def _git_diff_paths(repo: Path, rev: str) -> list[str]:
    """Tracked paths changed in the working tree relative to ``rev``.

    ``edit`` frame support (M4): ``git diff --name-only <rev>`` reports the
    uncommitted edit set. Fail-soft — a git error yields an empty path list (the
    caller degrades honestly), never an exception out of a read.
    """

    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", rev],
            cwd=repo,
            check=True,
            text=True,
            capture_output=True,
        ).stdout
    except (subprocess.CalledProcessError, OSError):
        return []
    return [line for line in out.splitlines() if line]


def resolve_frame(
    store: WarplineStore, repo: Path, frame_spec: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    """Resolve a COP frame spec to its change items, a frame echo, and warnings.

    ``frame_spec`` is ``{"kind": <FRAME_KINDS>, ...kind-specific keys}``:

      * ``rev_range``  — ``{"rev_range": "A..B"}``; events whose commit is in the
        range. Unknown / vanished SHAs resolve to an empty commit set → honest
        ``unresolved_input`` (the squash-merge reversal clause's failure path).
      * ``time_window`` — ``{"since": iso, "until": iso}``; events by author-time.
      * ``sei`` — ``{"sei": "..."}`` (or ``{"value": ...}``); the entity timeline.
      * ``edit`` — ``{"rev": "HEAD"}``; events on paths in ``git diff <rev>``.
      * ``branch_sha`` — ``{"branch": ..., "sha": ...}``; FALLS BACK to a
        rev-range resolution WITH a warning (``detected_branch`` not yet wired
        into a frozen read path; episode boundary unratified). This is the honest
        squash-merge degradation: branch + boundary, never a false-precise set.

    The frame echo always carries ``weft_reason_class``:
      * ``clean``           — the frame resolved a non-degraded change set;
      * ``unresolved_input``— the inputs named no resolvable change events;
      * ``partial``         — a fallback resolution (branch_sha) stood in.
    Returns ``(items, frame_echo, warnings)``. Reads only; mints nothing.
    """

    kind = frame_spec.get("kind")
    warnings: list[str] = []

    if kind == "rev_range":
        rev_range = frame_spec.get("rev_range")
        commit_shas, bad_detail = _safe_rev_range_commits(
            repo, rev_range if isinstance(rev_range, str) else None
        )
        events = store.list_change_events(repo, commit_shas=commit_shas)
        items = [_item_from_event(e) for e in events]
        if not items:
            detail = f" (git: {bad_detail})" if bad_detail else ""
            why = reason(
                "unresolved_input",
                cause=(
                    f"rev_range {rev_range!r} resolved to no recorded change events "
                    "(the range may be empty, or its commits were rewritten away — "
                    f"e.g. collapsed by a squash-merge and the source branch deleted){detail}"
                ),
                fix=(
                    "re-run against a branch name + episode boundary (a branch_sha frame), "
                    "or backfill/ingest the new mainline commit so warpline records its events"
                ),
            )
        else:
            why = reason("clean")
        echo = {
            "kind": "rev_range",
            "rev_range": rev_range,
            "weft_reason_class": why["reason_class"],
            "weft_reason": why,
        }
        return items, echo, warnings

    if kind == "time_window":
        since = frame_spec.get("since")
        until = frame_spec.get("until")
        events = store.list_change_events(
            repo,
            since=since if isinstance(since, str) else None,
            until=until if isinstance(until, str) else None,
        )
        items = [_item_from_event(e) for e in events]
        why = reason("clean") if items else reason(
            "unresolved_input",
            cause=f"time_window [{since!r}, {until!r}] matched no recorded change events",
            fix="widen the window, or ingest/backfill commits whose author-time falls in it",
        )
        echo = {
            "kind": "time_window",
            "since": since,
            "until": until,
            "weft_reason_class": why["reason_class"],
            "weft_reason": why,
        }
        return items, echo, warnings

    if kind == "sei":
        value = frame_spec.get("sei", frame_spec.get("value"))
        rows = store.timeline(repo, str(value)) if value is not None else []
        items = [_item_from_event(r) for r in rows]
        why = reason("clean") if items else reason(
            "unresolved_input",
            cause=f"sei {value!r} matched no recorded change events",
            fix="confirm the SEI/locator is one warpline has ingested, or backfill the repo",
        )
        echo = {
            "kind": "sei",
            "sei": value,
            "weft_reason_class": why["reason_class"],
            "weft_reason": why,
        }
        return items, echo, warnings

    if kind == "edit":
        rev = frame_spec.get("rev", "HEAD")
        paths = _git_diff_paths(repo, str(rev))
        events = store.list_change_events(repo)
        path_set = set(paths)
        items = [_item_from_event(e) for e in events if e.get("path") in path_set]
        if not paths:
            why = reason(
                "unresolved_input",
                cause=f"git diff {rev!r} reported no changed tracked paths (clean work tree)",
                fix="make (or stage) an edit, then re-run the edit frame against HEAD",
            )
        elif not items:
            why = reason(
                "partial",
                cause=(
                    f"git diff {rev!r} changed {len(paths)} path(s), but warpline has no "
                    "recorded change events for them yet"
                ),
                fix="ingest/backfill the repo so the edited paths' entities are recorded",
            )
        else:
            why = reason("clean")
        echo = {
            "kind": "edit",
            "rev": rev,
            "diff_paths": paths,
            "weft_reason_class": why["reason_class"],
            "weft_reason": why,
        }
        return items, echo, warnings

    if kind == "branch_sha":
        # Squash-merge / rewritten-history fallback (M4): until detected_branch is
        # surfaced on a frozen read path and the work-session episode boundary is
        # ratified, a branch_sha frame resolves through the rev-range built from
        # its sha (or branch ref) WITH an honest fallback warning — branch +
        # episode-boundary, never a false-precise commit set.
        branch = frame_spec.get("branch")
        sha = frame_spec.get("sha")
        fallback_range = frame_spec.get("rev_range")
        if not isinstance(fallback_range, str):
            fallback_range = f"{sha}~1..{sha}" if isinstance(sha, str) and sha else None
        warnings.append(
            "branch_sha frame fell back to a rev-range resolution: detected_branch is not yet "
            "surfaced on a frozen read path and the work-session episode boundary is unratified"
        )
        commit_shas, bad_detail = _safe_rev_range_commits(repo, fallback_range)
        events = store.list_change_events(repo, commit_shas=commit_shas)
        items = [_item_from_event(e) for e in events]
        git_note = f"; git: {bad_detail}" if bad_detail else ""
        why = reason(
            "partial",
            cause=(
                f"branch_sha frame (branch={branch!r}, sha={sha!r}) resolved via a "
                f"rev-range fallback ({fallback_range!r}); episode-boundary keying is "
                f"pending{git_note}"
            ),
            fix=(
                "ratify the work-session episode boundary and wire detected_branch onto a "
                "frozen read path so branch_sha can resolve to a precise episode"
            ),
        )
        echo = {
            "kind": "branch_sha",
            "branch": branch,
            "sha": sha,
            "fallback_rev_range": fallback_range,
            "weft_reason_class": why["reason_class"],
            "weft_reason": why,
        }
        return items, echo, warnings

    # Unknown frame kind — honest rejection, never a silent empty.
    why = reason(
        "rejected",
        cause=f"unknown COP frame kind {kind!r}",
        fix=f"use one of {', '.join(FRAME_KINDS)}",
    )
    echo = {
        "kind": kind,
        "weft_reason_class": why["reason_class"],
        "weft_reason": why,
    }
    return [], echo, warnings


def compose_temporal_cop(
    items: list[dict[str, Any]],
    frame: dict[str, Any],
    *,
    work_client: WorkClient | None = None,
    risk_client: RiskClient | None = None,
    legis_client: LegisClient | None = None,
) -> dict[str, Any]:
    """Compose the temporal COP for a resolved frame's ``items``.

    Reuses the three federation consults VERBATIM (R9) and wraps them in a
    coverage block. Returns
    ``{"members", "entities", "coverage", "frame"}`` where:

      * ``members`` — every member in :data:`FEDERATION_MEMBERS` with its own
        weft-reason and entity count (NEVER omitted);
      * ``entities`` — per-locator facts a member actually returned;
      * ``coverage`` — ``{members_consulted, members_total, dark_sectors}``; a
        ``dark_sector`` is any member whose reason class is NOT ``clean``
        (``disabled`` = no transport, ``unreachable`` = transport raised). This is
        the load-bearing coverage-honesty surface: an unmonitored domain is named,
        never read as a clean empty.
      * ``frame`` — the frame echo from :func:`resolve_frame` (carries
        ``weft_reason_class``).

    ``consult_federation`` is NOT modified; this composes the same three consults
    and adds coverage. Read-time, never-gating, no-mirror — writes nothing.
    """

    work_by, work_reason = _consult_filigree(items, work_client)
    risk_by, risk_reason = _consult_wardline(items, risk_client)
    gov_by, gov_reason = _consult_legis(items, legis_client)

    member_reasons = {
        "filigree": (work_reason, work_by),
        "wardline": (risk_reason, risk_by),
        "legis": (gov_reason, gov_by),
    }
    members: dict[str, Any] = {}
    dark_sectors: list[dict[str, Any]] = []
    consulted = 0
    for name in FEDERATION_MEMBERS:
        member_reason, by_locator = member_reasons[name]
        members[name] = {"weft_reason": member_reason, "entity_count": len(by_locator)}
        if member_reason.get("reason_class") == "clean":
            consulted += 1
        else:
            dark_sectors.append(
                {
                    "member": name,
                    "reason_class": member_reason.get("reason_class"),
                    "cause": member_reason.get("cause"),
                    "fix": member_reason.get("fix"),
                }
            )

    entities: list[dict[str, Any]] = []
    for item in items:
        entity = item.get("entity", {})
        locator = entity.get("locator")
        if not isinstance(locator, str) or not locator:
            continue
        work = work_by.get(locator, [])
        risk = risk_by.get(locator, [])
        gov = gov_by.get(locator, [])
        if not (work or risk or gov):
            continue
        entities.append(
            {
                "locator": locator,
                "sei": entity.get("sei"),
                "work": work,
                "risk": risk,
                "governance": gov,
            }
        )

    coverage = {
        "members_consulted": consulted,
        "members_total": len(FEDERATION_MEMBERS),
        "dark_sectors": dark_sectors,
    }
    return {
        "members": members,
        "entities": entities,
        "coverage": coverage,
        "frame": frame,
    }
