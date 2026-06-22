# Honesty Completeness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Make every enrichment absence read as *explained* absence by attaching the `cause + reason_class + fix` weft-reason triple to the `sei`, `governance`, and (reserved) `requirements` dimensions across all emitting tools, without touching the frozen closed scalar `enrichment` vocab.

**Architecture:** The frozen success envelope's `enrichment` block is a CLOSED SCALAR dict validated value-by-value in `build_envelope` (`envelope.py:72-74`), so a triple (a dict) cannot ride inside it. This plan introduces ONE additive top-level carrier — `enrichment_reasons: dict[str, dict[str, Any]]` — threaded through `build_envelope` as a new optional keyword. Each dimension maps to a `listing.reason()` triple. New pure helpers `sei_reason()` and `requirements_reason()` live in `_enrichment.py` (the no-I/O module the spec names as the pattern), `governance`'s triple is emitted inline in `entity_timeline`, and all reason classes reuse the existing canonical 11 (no contract-affecting vocab change).

**Tech Stack:** Python 3.12, ruff (lint), pyright (types), pytest (tests). Real-git fixtures via `tests/conftest.py` (`init_repo`/`commit`) and direct `WarplineStore` seeding.

## Global Constraints
Python repo. Tooling: ruff (lint), pyright (types), pytest (tests). TDD throughout.
Sequencing is VECTORS-FIRST: each plan opens by writing the failing golden vector / test that expresses the invariant, THEN the implementation makes it green.
WS1 capture changes are OUTPUT-SHAPE-PRESERVING: the response envelope stays byte-identical; only edge-visibility timing and row lifecycle change.
Enrichment vocab is a CLOSED, FROZEN contract in src/warpline/envelope.py (keys: sei, edges, work, risk, governance, requirements). Do NOT add or remove keys. The `requirements` key stays (resolved as reserved-but-honest).
The weft-reason triple is `cause + reason_class + fix`, built ONLY via src/warpline/listing.py `reason()` factory (non-"clean" reason_class requires both cause and fix).
Every response MUST keep `meta.local_only: true` and `meta.peer_side_effects: []`. Never break the frozen golden vectors or the success/error envelope schema.
Gates that must stay green: `warpline dogfood-eval`, `warpline mcp-smoke`, ruff, pyright, pytest, and the member-diff guard.
Authority boundary: all work is reversible and repo-local. The hub handover document is a DRAFT package — it creates no hub/sibling work and freezes nothing.
Commit messages end with the trailer: Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>

---

## Design decisions (read once, then follow verbatim)

These resolve the three open decisions the reground map flagged. Do NOT re-litigate them mid-implementation; the test assertions below encode them.

1. **Carrier = a new top-level `enrichment_reasons` key**, additive to the frozen envelope, threaded through `build_envelope` as a new optional keyword `enrichment_reasons: dict[str, dict[str, Any]] | None = None`. It sits as a sibling of `enrichment` (NOT nested inside it — that would trip the closed-vocab wall at `envelope.py:72-74`). Each key is an enrichment dimension name (`sei`, `governance`, `requirements`); each value is a `listing.reason()` triple. Dimensions WITHOUT a reason simply do not appear in the map — absence of a key means "no explanatory triple attached", never a faked-clean.

2. **No new reason_class.** Reuse the canonical 11 in `listing.py:17`. This avoids touching the frozen contract and the canonical-11 guard at `tests/test_list_ergonomics.py:457`. Mapping:
   - `sei` never-resolved (peer present, locator never resolved to an SEI) → `unresolved_input`
   - `sei` Loomweave-unreachable (capture: peer down) → `unreachable`
   - `governance` no rename-feed transport on `entity_timeline` → `disabled`
   - `requirements` reserved-but-inert → `disabled` with reserved-flavored cause/fix
   - `sei`/`governance` present (peer answered, fact exists) → `clean` (omits cause/fix)

3. **`requirements` scope = envelope-level only.** The envelope-level scalar (`envelope.py:27`) gets the reserved triple via `enrichment_reasons`. The per-item `reverify.py:16` empty-list scaffold is OUT OF SCOPE for this plan (it is a per-item structure, not the envelope scalar the spec targets); leave it untouched. The reserved triple is emitted on EVERY envelope from the shared default (Task 2), so all six tools carry it consistently.

---

## Task 1 — Add the `enrichment_reasons` carrier to the frozen envelope (additive)

Introduce the transport. No tool emits a reason yet; this task only proves the carrier exists, defaults to an empty map, validates its values are real `reason()` triples, and never collides with the scalar vocab.

**Files:**
- Modify `src/warpline/envelope.py` (signature at line 59-68; body at 71-84)
- Modify `tests/test_envelope_reasons.py` (Create)

**Interfaces:**
- Consumes: `listing.reason(reason_class, *, cause, fix) -> dict[str, Any]` (`listing.py:34`)
- Produces: `build_envelope(..., enrichment_reasons: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]` — the returned envelope gains a top-level key `enrichment_reasons` (defaults to `{}`). Validation: every key MUST be a member of `ENRICHMENT_VOCAB`; every value MUST be a dict carrying a `reason_class` in `REASON_CLASSES`.

**Steps:**

- [ ] Write the failing test. Create `tests/test_envelope_reasons.py`:
```python
from __future__ import annotations

import pytest

from warpline.envelope import build_envelope, enrichment_state
from warpline.listing import reason


def _minimal_env(**kw):
    return build_envelope(
        "warpline.test.v1",
        query={"tool": "t"},
        data={"items": []},
        enrichment=enrichment_state(),
        **kw,
    )


def test_envelope_defaults_enrichment_reasons_to_empty_map() -> None:
    env = _minimal_env()
    assert env["enrichment_reasons"] == {}


def test_envelope_carries_a_reason_triple_alongside_the_scalar() -> None:
    env = _minimal_env(
        enrichment_reasons={
            "sei": reason(
                "unresolved_input",
                cause="locator never resolved to an SEI",
                fix="run loomweave analyze, then re-query",
            )
        }
    )
    # the scalar vocab is untouched; the triple rides in the sibling map
    assert env["enrichment"]["sei"] == "absent"
    assert env["enrichment_reasons"]["sei"]["reason_class"] == "unresolved_input"
    assert env["enrichment_reasons"]["sei"]["cause"]
    assert env["enrichment_reasons"]["sei"]["fix"]


def test_envelope_rejects_reason_for_unknown_dimension() -> None:
    with pytest.raises(ValueError, match="enrichment_reasons.bogus"):
        _minimal_env(enrichment_reasons={"bogus": reason("clean")})


def test_envelope_rejects_reason_value_without_reason_class() -> None:
    with pytest.raises(ValueError, match="enrichment_reasons.sei"):
        _minimal_env(enrichment_reasons={"sei": {"not": "a reason"}})


def test_clean_reason_needs_no_cause_or_fix() -> None:
    env = _minimal_env(enrichment_reasons={"sei": reason("clean")})
    assert env["enrichment_reasons"]["sei"] == {"reason_class": "clean"}
```

- [ ] Run it and watch it fail (the keyword does not exist yet):
```bash
cd /home/john/warpline && python -m pytest tests/test_envelope_reasons.py -q
```
Expected failure: `TypeError: build_envelope() got an unexpected keyword argument 'enrichment_reasons'`.

- [ ] Add the import at the top of `src/warpline/envelope.py`. After line 3 (`from typing import Any`) insert:
```python
from warpline.listing import REASON_CLASSES
```
(Place it after the `from warpline import __version__` line at `envelope.py:5` to keep the warpline-internal imports grouped: insert a new line after line 5 reading `from warpline.listing import REASON_CLASSES`.)

- [ ] Extend the `build_envelope` signature. In `src/warpline/envelope.py`, change the signature block (currently lines 59-68) to add the new keyword after `enrichment`:
```python
def build_envelope(
    schema: str,
    *,
    query: dict[str, Any],
    data: dict[str, Any],
    enrichment: dict[str, str] | None = None,
    enrichment_reasons: dict[str, dict[str, Any]] | None = None,
    next_actions: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    peer_side_effects: list[Any] | None = None,
) -> dict[str, Any]:
```

- [ ] Add validation + emit the key. In `src/warpline/envelope.py`, replace the body (currently lines 71-84, from `enrich = ...` through the `return {...}` block) with:
```python
    enrich = enrichment if enrichment is not None else enrichment_state()
    for key, value in enrich.items():
        if key not in ENRICHMENT_VOCAB or value not in ENRICHMENT_VOCAB[key]:
            raise ValueError(f"enrichment.{key}={value!r} violates the closed vocabulary")
    reasons = enrichment_reasons or {}
    for dim, carrier in reasons.items():
        if dim not in ENRICHMENT_VOCAB:
            raise ValueError(
                f"enrichment_reasons.{dim} names a dimension outside the closed vocabulary"
            )
        if not isinstance(carrier, dict) or carrier.get("reason_class") not in REASON_CLASSES:
            raise ValueError(
                f"enrichment_reasons.{dim} must be a listing.reason() triple "
                f"(a dict carrying a canonical reason_class)"
            )
    return {
        "schema": schema,
        "ok": True,
        "query": query,
        "data": data,
        "warnings": warnings or [],
        "next_actions": next_actions or {},
        "enrichment": enrich,
        "enrichment_reasons": reasons,
        "meta": local_only_meta(peer_side_effects),
    }
```

- [ ] Run the test and watch it pass:
```bash
cd /home/john/warpline && python -m pytest tests/test_envelope_reasons.py -q
```
Expected: `5 passed`.

- [ ] Confirm the frozen golden vectors and full envelope-shape suite still pass (the new key is additive, default `{}`):
```bash
cd /home/john/warpline && python -m pytest tests/contracts/test_golden_vectors.py tests/test_honesty_invariant.py -q
```
Expected: all pass (no assertion in those files inspects `enrichment_reasons` yet).

- [ ] Lint + type-check the changed file:
```bash
cd /home/john/warpline && ruff check src/warpline/envelope.py tests/test_envelope_reasons.py && pyright src/warpline/envelope.py
```
Expected: `All checks passed!` from ruff; `0 errors` from pyright. NOTE: `envelope.py` now imports `listing`. Confirm no import cycle was introduced:
```bash
cd /home/john/warpline && python -c "import warpline.envelope; import warpline.listing; print('no cycle')"
```
Expected: `no cycle`. (`listing.py` imports only `warpline.errors`, never `envelope`, so the new edge `envelope -> listing` is one-way.)

- [ ] Commit:
```bash
cd /home/john/warpline && git checkout -b harden/honesty-completeness && git add src/warpline/envelope.py tests/test_envelope_reasons.py && git commit -m "feat(envelope): add additive enrichment_reasons carrier for weft-reason triples

The closed scalar enrichment vocab cannot hold a triple (dict) without
tripping build_envelope validation, so the cause+reason_class+fix triple
rides in a new sibling top-level enrichment_reasons map. Additive to the
frozen envelope; defaults to {}; values validated as listing.reason()
triples keyed on a real enrichment dimension.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 — `requirements` reserved-but-honest: shared default reason on every envelope

The `requirements` dimension rides as the scalar `unavailable` on every envelope (`_DEFAULT_ENRICHMENT`, `envelope.py:27`) with no explanation. Resolve it as reserved-but-honest: emit a STABLE `disabled` triple declaring "reserved, not yet wired" from a shared default so all six tools carry it identically. The key is NOT removed (frozen envelope).

**Files:**
- Modify `src/warpline/_enrichment.py` (add helper after line 76)
- Modify `src/warpline/envelope.py` (default the `requirements` reason in `build_envelope`)
- Modify `tests/test_honesty_invariant.py` (add test)

**Interfaces:**
- Produces: `requirements_reason() -> dict[str, Any]` in `_enrichment.py` — returns a fixed `reason("disabled", cause=..., fix=...)` triple. Pure, no args, no I/O.
- Consumes: `listing.reason` (`listing.py:34`).
- Effect: every envelope's `enrichment_reasons["requirements"]` is the reserved triple unless a caller explicitly overrides it.

**Steps:**

- [ ] Write the failing test. In `tests/test_honesty_invariant.py`, append at end of file:
```python
# --------------------------------------------------------------------------- (d)
def test_requirements_is_reserved_but_honest_on_every_tool(tmp_path: Path) -> None:
    """The reserved-but-inert ``requirements`` dimension must explain itself.

    ``requirements`` rides as scalar ``unavailable`` on every envelope but has no
    transport wired. Rather than a bare, unexplained scalar, it carries a stable
    ``disabled`` triple naming WHY (reserved, not yet wired) and the fix (the work
    that would wire it). The scalar value is unchanged — only the triple is added.
    """

    repo = _init_repo(tmp_path)
    _commit(repo, "a.py", "a = 1\n")
    env = commands.change_list(repo)

    assert env["enrichment"]["requirements"] == "unavailable"  # scalar untouched
    triple = env["enrichment_reasons"]["requirements"]
    assert triple["reason_class"] == "disabled"
    assert "reserved" in triple["cause"].lower()
    assert triple["fix"]
```

- [ ] Run it and watch it fail:
```bash
cd /home/john/warpline && python -m pytest tests/test_honesty_invariant.py::test_requirements_is_reserved_but_honest_on_every_tool -q
```
Expected failure: `KeyError: 'requirements'` (the `enrichment_reasons` map is empty `{}` until `build_envelope` defaults it).

- [ ] Add the helper. In `src/warpline/_enrichment.py`, first add the import. After line 11 (`from typing import Any`) insert:
```python
from warpline.listing import reason
```
Then UPDATE the module docstring (lines 1-7), which currently attests the enrich-only-doctrine via its import list. That attestation is load-bearing and would become FALSE the moment this import lands, so it must be corrected in the same step. In the docstring, replace `imports nothing from warpline` with `imports only from ``warpline.listing`` (no store, no git, no I/O — enrich-only doctrine preserved)` and replace `only ``typing.Any``` with `only ``typing.Any`` and ``warpline.listing.reason```. The corrected docstring reads:
```python
"""Pure staleness/completeness enrichment helpers (internal API).

Extracted from ``commands.py`` (Rung 0). Dependency is strictly one-way:
``commands.py -> _enrichment``; this module imports only from ``warpline.listing``
(no store, no git, no I/O — enrich-only doctrine preserved) and is structurally
incapable of gating (enrich-only doctrine, verified by its import list: only
``typing.Any`` and ``warpline.listing.reason``). No store, no git, no I/O.
"""
```
Then append after line 76 (end of `completeness_warnings`):
```python


def requirements_reason() -> dict[str, Any]:
    """The stable reserved-but-honest triple for the ``requirements`` dimension.

    ``requirements`` is in the FROZEN enrichment vocab but no requirements-trace
    transport is wired today. It defaults to scalar ``unavailable``; this triple
    makes that absence EXPLAINED (reserved, not yet wired) rather than a bare,
    unexplained scalar. Reuses the canonical ``disabled`` class (no transport) —
    no new reason_class, so the frozen canonical-11 contract is untouched.
    """

    return reason(
        "disabled",
        cause=(
            "the requirements dimension is reserved in the frozen enrichment vocab but no "
            "requirements-trace transport is wired in warpline yet"
        ),
        fix=(
            "wire a requirements-trace consumer (e.g. a legis/requirements read keyed on the "
            "SEI) and populate enrichment.requirements; until then it is honestly reserved, "
            "not an earned-empty"
        ),
    )
```

- [ ] Confirm `_enrichment.py` still has no cycle (it now imports `listing`, which imports only `errors`):
```bash
cd /home/john/warpline && python -c "import warpline._enrichment; print('ok')"
```
Expected: `ok`.

- [ ] Default the reserved triple in `build_envelope`. In `src/warpline/envelope.py`, add the import after the `from warpline.listing import REASON_CLASSES` line added in Task 1:
```python
from warpline._enrichment import requirements_reason
```
Then in the `build_envelope` body, replace the line `    reasons = enrichment_reasons or {}` (added in Task 1) with:
```python
    reasons = {"requirements": requirements_reason(), **(enrichment_reasons or {})}
```
This seeds the reserved triple but lets any caller override `requirements` explicitly.

- [ ] Guard against an import cycle. `_enrichment.py` now imports `listing`; `envelope.py` now imports `_enrichment` AND `listing`. None of `listing`/`_enrichment` import `envelope`, so this is acyclic. Verify:
```bash
cd /home/john/warpline && python -c "import warpline.envelope; print('no cycle')"
```
Expected: `no cycle`.

- [ ] Run the new test and watch it pass:
```bash
cd /home/john/warpline && python -m pytest tests/test_honesty_invariant.py::test_requirements_is_reserved_but_honest_on_every_tool -q
```
Expected: `1 passed`.

- [ ] Confirm the frozen golden vectors still pass (the reserved triple is additive; no vector asserts on `enrichment_reasons` content):
```bash
cd /home/john/warpline && python -m pytest tests/contracts/test_golden_vectors.py tests/test_envelope_reasons.py -q
```
Expected: GV vectors pass; test_envelope_reasons.py has 1 failure (test_envelope_defaults_enrichment_reasons_to_empty_map) — fixed in the next step. (That Task-1 test calls `build_envelope` with no `enrichment_reasons`, asserting `== {}`; it now gets `{"requirements": ...}`, NOT `{}`. FIX REQUIRED: see next step.)

- [ ] Fix the Task-1 default-empty assertion now that `requirements` is always seeded. In `tests/test_envelope_reasons.py`, change `test_envelope_defaults_enrichment_reasons_to_empty_map` body from:
```python
    env = _minimal_env()
    assert env["enrichment_reasons"] == {}
```
to:
```python
    env = _minimal_env()
    # requirements is seeded reserved-but-honest on every envelope; nothing else.
    assert set(env["enrichment_reasons"]) == {"requirements"}
    assert env["enrichment_reasons"]["requirements"]["reason_class"] == "disabled"
```
Re-run and confirm:
```bash
cd /home/john/warpline && python -m pytest tests/test_envelope_reasons.py -q
```
Expected: `5 passed`.

- [ ] Lint + type-check:
```bash
cd /home/john/warpline && ruff check src/warpline/_enrichment.py src/warpline/envelope.py && pyright src/warpline/_enrichment.py src/warpline/envelope.py
```
Expected: ruff `All checks passed!`; pyright `0 errors`.

- [ ] Commit:
```bash
cd /home/john/warpline && git add src/warpline/_enrichment.py src/warpline/envelope.py tests/test_honesty_invariant.py tests/test_envelope_reasons.py && git commit -m "feat(enrichment): requirements reserved-but-honest via stable disabled triple

requirements rides as scalar unavailable on every envelope with no
transport wired. Rather than a bare unexplained scalar, build_envelope now
seeds a stable disabled triple (reserved, not yet wired) into
enrichment_reasons on every envelope. Scalar value unchanged; key not
removed (frozen envelope). Reuses the canonical disabled class — no new
reason_class.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 — `sei_reason()` pure helper (never-resolved vs unreachable)

Add the pure helper that maps a sei posture to its triple, mirroring the `completeness_warnings()` pattern (a pure state→carrier mapper in `_enrichment.py`). This task adds the helper + its unit test only; wiring into tools is Tasks 4-6.

**Files:**
- Modify `src/warpline/_enrichment.py` (add helper after `requirements_reason`)
- Modify `tests/test_enrichment_helpers.py` (Create)

**Interfaces:**
- Produces: `sei_reason(sei_state: str) -> dict[str, Any] | None` in `_enrichment.py`.
  - `"present"` → `reason("clean")`
  - `"absent"` → `reason("unresolved_input", cause=..., fix=...)` (peer present, locator never resolved to an SEI)
  - `"unavailable"` → `reason("unreachable", cause=..., fix=...)` (Loomweave peer down)
  - any other value → `None` (no triple)
- Consumes: `listing.reason` (already imported into `_enrichment.py` in Task 2).

**Steps:**

- [ ] Write the failing test. Create `tests/test_enrichment_helpers.py`:
```python
from __future__ import annotations

from warpline._enrichment import requirements_reason, sei_reason


def test_sei_present_is_clean() -> None:
    assert sei_reason("present") == {"reason_class": "clean"}


def test_sei_absent_is_unresolved_input_with_cause_and_fix() -> None:
    triple = sei_reason("absent")
    assert triple is not None
    assert triple["reason_class"] == "unresolved_input"
    assert "resolv" in triple["cause"].lower()
    assert triple["fix"]


def test_sei_unavailable_is_unreachable_with_cause_and_fix() -> None:
    triple = sei_reason("unavailable")
    assert triple is not None
    assert triple["reason_class"] == "unreachable"
    assert "loomweave" in triple["cause"].lower()
    assert triple["fix"]


def test_sei_unknown_state_yields_no_triple() -> None:
    assert sei_reason("bogus") is None


def test_requirements_reason_is_stable_disabled() -> None:
    assert requirements_reason()["reason_class"] == "disabled"
```

- [ ] Run it and watch it fail:
```bash
cd /home/john/warpline && python -m pytest tests/test_enrichment_helpers.py -q
```
Expected failure: `ImportError: cannot import name 'sei_reason' from 'warpline._enrichment'`.

- [ ] Add the helper. In `src/warpline/_enrichment.py`, append after the `requirements_reason` function added in Task 2:
```python


def sei_reason(sei_state: str) -> dict[str, Any] | None:
    """Map a closed ``enrichment.sei`` scalar to its explanatory weft-reason triple.

    ``present`` is an earned ``clean``; ``absent`` (peer present, the changed
    locator never resolved to an SEI) is ``unresolved_input``; ``unavailable``
    (the Loomweave SEI authority was unreachable, e.g. mid-capture) is
    ``unreachable``. Returns ``None`` for any value outside the closed vocab so a
    caller never attaches a triple it cannot explain. Reuses the canonical 11 —
    no new reason_class.
    """

    if sei_state == "present":
        return reason("clean")
    if sei_state == "absent":
        return reason(
            "unresolved_input",
            cause=(
                "the changed entity's locator never resolved to a Loomweave SEI "
                "(peer present, no stable-entity-identity for this locator yet)"
            ),
            fix=(
                "run `loomweave analyze <repo>` so the locator gets a stable SEI, then re-query; "
                "until then sei is honestly absent, not an earned-empty"
            ),
        )
    if sei_state == "unavailable":
        return reason(
            "unreachable",
            cause=(
                "the Loomweave SEI authority was unreachable, so SEI resolution could not be "
                "attempted (peer down — never an implied clean/resolved state)"
            ),
            fix=(
                "confirm `loomweave serve` is reachable (or the loomweave CLI is on PATH), then "
                "recapture/re-query so SEIs can be resolved"
            ),
        )
    return None
```

- [ ] Run the test and watch it pass:
```bash
cd /home/john/warpline && python -m pytest tests/test_enrichment_helpers.py -q
```
Expected: `5 passed`.

- [ ] Lint + type-check:
```bash
cd /home/john/warpline && ruff check src/warpline/_enrichment.py tests/test_enrichment_helpers.py && pyright src/warpline/_enrichment.py
```
Expected: ruff `All checks passed!`; pyright `0 errors`.

- [ ] Commit:
```bash
cd /home/john/warpline && git add src/warpline/_enrichment.py tests/test_enrichment_helpers.py && git commit -m "feat(enrichment): add sei_reason() pure helper (never-resolved vs unreachable)

Mirrors the completeness_warnings() pattern: a pure state->carrier mapper.
sei present -> clean; absent -> unresolved_input (locator never resolved);
unavailable -> unreachable (Loomweave down). Reuses the canonical 11; no
I/O, no new reason_class. Wiring into tools follows.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 — Wire the sei triple into the three read tools (change_list, entity_timeline, entity_churn_count)

The three read tools emit `sei: present|absent` today with no triple. Attach `sei_reason()` via `enrichment_reasons`. Vectors-first: write the honesty-invariant assertions, watch them fail, then wire.

**Files:**
- Modify `src/warpline/commands.py`:
  - import block (lines 9-14 for `_enrichment`, line 18-24 for `listing`)
  - `change_list` envelope build (lines 307-314)
  - `entity_timeline` envelope build (lines 392-401)
  - `entity_churn_count` envelope build (lines 477-483)
- Modify `tests/test_honesty_invariant.py` (add tests)

**Interfaces:**
- Consumes: `sei_reason(sei_state) -> dict | None` (Task 3, `_enrichment.py`)
- Produces: each of the three tools' envelope gains `enrichment_reasons["sei"]` = the triple for the same scalar it already emits.

**Steps:**

- [ ] Write the failing tests. In `tests/test_honesty_invariant.py`, append:
```python
# --------------------------------------------------------------------------- (e)
def test_change_list_sei_absent_carries_unresolved_input_triple(tmp_path: Path) -> None:
    """A change_list over an entity with no SEI emits sei:absent WITH a triple
    explaining the locator never resolved — not a bare, unexplained scalar."""

    repo = _init_repo(tmp_path)
    first = _commit(repo, "a.py", "a = 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        key = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei=None, commit_sha=first
        )
        store.append_change_event(
            repo_id=repo_id,
            entity_key_id=key,
            commit_sha=first,
            change_kind="modified",
            actor="agent:test",
            changed_at="2026-06-13T00:00:00Z",
            path="a.py",
        )
    env = commands.change_list(repo)
    assert env["enrichment"]["sei"] == "absent"
    assert env["enrichment_reasons"]["sei"]["reason_class"] == "unresolved_input"


def test_change_list_sei_present_is_clean_triple(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    first = _commit(repo, "a.py", "a = 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        key = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei="loomweave:eid:aaaa", commit_sha=first
        )
        store.append_change_event(
            repo_id=repo_id,
            entity_key_id=key,
            commit_sha=first,
            change_kind="modified",
            actor="agent:test",
            changed_at="2026-06-13T00:00:00Z",
            path="a.py",
        )
    env = commands.change_list(repo)
    assert env["enrichment"]["sei"] == "present"
    assert env["enrichment_reasons"]["sei"] == {"reason_class": "clean"}


def test_entity_timeline_sei_absent_carries_unresolved_input_triple(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    first = _commit(repo, "a.py", "a = 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        key = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei=None, commit_sha=first
        )
        store.append_change_event(
            repo_id=repo_id,
            entity_key_id=key,
            commit_sha=first,
            change_kind="modified",
            actor="agent:test",
            changed_at="2026-06-13T00:00:00Z",
            path="a.py",
        )
    env = commands.entity_timeline(repo, "python:function:a")
    assert env["enrichment"]["sei"] == "absent"
    assert env["enrichment_reasons"]["sei"]["reason_class"] == "unresolved_input"


def test_entity_churn_count_sei_absent_carries_unresolved_input_triple(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _commit(repo, "a.py", "a = 1\n")
    env = commands.entity_churn_count(repo, [{"kind": "locator", "value": "python:function:a"}])
    assert env["enrichment"]["sei"] == "absent"
    assert env["enrichment_reasons"]["sei"]["reason_class"] == "unresolved_input"
```
NOTE: the exact `WarplineStore` seeding API used here (`ensure_repo`, `ensure_entity_key`, `append_change_event`) mirrors `tests/test_honesty_invariant.py` and `tests/contracts/test_golden_vectors.py`. `append_change_event` is the canonical change-event API and is FULLY KEYWORD-ONLY (a `*` precedes every argument, so `repo_id` must be passed as `repo_id=repo_id`, never positionally). If you are unsure of its signature, copy the seeding pattern from `tests/contracts/test_golden_vectors.py:_add_change` (lines 51-70) verbatim — it calls `store.append_change_event(repo_id=..., entity_key_id=..., ...)` — rather than inventing argument names.

- [ ] Run them and watch them fail:
```bash
cd /home/john/warpline && python -m pytest tests/test_honesty_invariant.py -k "sei_absent or sei_present" -q
```
Expected failure: `KeyError: 'sei'` on `env["enrichment_reasons"]["sei"]` (only `requirements` is seeded so far).

- [ ] Import the helper into `commands.py`. In `src/warpline/commands.py`, extend the `_enrichment` import block (lines 9-14) to add `sei_reason`:
```python
from warpline._enrichment import (
    EDGES_FOR_COMPLETENESS,
    completeness_warnings,
    edges_enrichment,
    sei_reason,
    staleness_warnings,
)
```

- [ ] Wire `change_list`. In `src/warpline/commands.py`, replace the `change_list` return (lines 307-314) so the sei scalar is computed once and its triple attached:
```python
        sei_state = "present" if has_sei else "absent"
        return build_envelope(
            SCHEMA_CHANGE_LIST,
            query=query,
            data=data,
            enrichment=enrichment_state(sei=sei_state),
            enrichment_reasons={"sei": sei_reason(sei_state)},
            next_actions=next_actions,
            warnings=overflow_warnings,
        )
```
NOTE: `sei_reason(sei_state)` is non-None for `present`/`absent`, so the dict value is always a valid triple here. (If a future refactor could pass an out-of-vocab state, `build_envelope` would reject a `None` value — but `present`/`absent` are the only two values reachable here.)

- [ ] Wire `entity_timeline`. In `src/warpline/commands.py`, replace the `entity_timeline` return (lines 392-401):
```python
        sei_state = "present" if entity_out["sei"] else "absent"
        return build_envelope(
            SCHEMA_ENTITY_TIMELINE,
            query=query,
            data=data,
            enrichment=enrichment_state(
                sei=sei_state,
                governance="present" if rename_feed is not None else "unavailable",
            ),
            enrichment_reasons={"sei": sei_reason(sei_state)},
            warnings=overflow_warnings,
        )
```
(The `governance` triple is added in Task 5; leave `enrichment_reasons` carrying only `sei` for now.)

- [ ] Wire `entity_churn_count`. In `src/warpline/commands.py`, replace the `entity_churn_count` return (lines 477-483):
```python
        sei_state = "present" if has_sei else "absent"
        return build_envelope(
            SCHEMA_ENTITY_CHURN_COUNT,
            query=query,
            data=data,
            enrichment=enrichment_state(sei=sei_state),
            enrichment_reasons={"sei": sei_reason(sei_state)},
            warnings=overflow_warnings,
        )
```

- [ ] Run the new tests and watch them pass:
```bash
cd /home/john/warpline && python -m pytest tests/test_honesty_invariant.py -k "sei_absent or sei_present" -q
```
Expected: `4 passed`.

- [ ] Confirm GV-LW-5 (the scalar-only sei vector) still passes — the scalar is unchanged, only the triple was added:
```bash
cd /home/john/warpline && python -m pytest "tests/contracts/test_golden_vectors.py::test_gv_lw_5_sei_resolution_present_vs_unavailable" -q
```
Expected: `1 passed`.

- [ ] Lint + type-check:
```bash
cd /home/john/warpline && ruff check src/warpline/commands.py && pyright src/warpline/commands.py
```
Expected: ruff `All checks passed!`; pyright `0 errors`.

- [ ] Commit:
```bash
cd /home/john/warpline && git add src/warpline/commands.py tests/test_honesty_invariant.py && git commit -m "feat(commands): attach sei weft-reason triple on the three read tools

change_list, entity_timeline, entity_churn_count now carry a sei triple in
enrichment_reasons explaining present (clean) vs absent (unresolved_input:
locator never resolved). Scalar values unchanged; GV-LW-5 stays green.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 — Wire the sei + governance triples into capture_snapshot and entity_timeline.governance

`capture_snapshot` is the only tool that emits `sei: unavailable` (Loomweave down) — it must carry the `unreachable` triple. `entity_timeline`'s `governance` scalar is bare when `unavailable` (no rename-feed transport) — give it a `disabled` triple. This closes gaps #1 (the 4th sei tool) and #2 (governance).

**Files:**
- Modify `src/warpline/commands.py`:
  - import block (line 18-24, add `reason` from `listing`)
  - `capture_snapshot` envelope build (lines 1111-1117)
  - `entity_timeline` envelope build (the `enrichment_reasons` arg from Task 4)
- Modify `tests/test_honesty_invariant.py` (add tests)

**Interfaces:**
- Consumes: `sei_reason` (Task 3); `listing.reason` (`listing.py:34`) for the inline governance triple.
- Produces: `capture_snapshot` envelope gains `enrichment_reasons["sei"]`; `entity_timeline` envelope gains `enrichment_reasons["governance"]`.

**Steps:**

- [ ] Write the failing tests. In `tests/test_honesty_invariant.py`, append:
```python
# --------------------------------------------------------------------------- (f)
def test_capture_sei_unavailable_carries_unreachable_triple(tmp_path: Path) -> None:
    """Capture against an unreachable Loomweave emits sei:unavailable WITH an
    unreachable triple (peer down) — never an implied clean/resolved state."""

    repo = _init_repo(tmp_path)
    _commit(repo, "a.py", "a = 1\n")
    env = commands.capture_snapshot(repo, commit="HEAD", loomweave_command="/no/such")
    assert env["enrichment"]["sei"] == "unavailable"
    assert env["enrichment_reasons"]["sei"]["reason_class"] == "unreachable"
    assert "loomweave" in env["enrichment_reasons"]["sei"]["cause"].lower()


def test_entity_timeline_governance_unavailable_carries_disabled_triple(tmp_path: Path) -> None:
    """Without a rename-feed transport, governance is unavailable WITH a disabled
    triple (no transport wired) — not a bare scalar."""

    repo = _init_repo(tmp_path)
    first = _commit(repo, "a.py", "a = 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        key = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei=None, commit_sha=first
        )
        store.append_change_event(
            repo_id=repo_id,
            entity_key_id=key,
            commit_sha=first,
            change_kind="modified",
            actor="agent:test",
            changed_at="2026-06-13T00:00:00Z",
            path="a.py",
        )
    env = commands.entity_timeline(repo, "python:function:a")
    assert env["enrichment"]["governance"] == "unavailable"
    assert env["enrichment_reasons"]["governance"]["reason_class"] == "disabled"
    assert env["enrichment_reasons"]["governance"]["fix"]


def test_entity_timeline_governance_present_is_clean_triple(tmp_path: Path) -> None:
    from warpline.siblings import RenameFeed

    repo = _init_repo(tmp_path)
    first = _commit(repo, "a.py", "a = 1\n")
    with WarplineStore.open(default_store_path(repo)) as store:
        repo_id = store.ensure_repo(repo)
        key = store.ensure_entity_key(
            repo_id, locator="python:function:a", sei=None, commit_sha=first
        )
        store.append_change_event(
            repo_id=repo_id,
            entity_key_id=key,
            commit_sha=first,
            change_kind="modified",
            actor="agent:test",
            changed_at="2026-06-13T00:00:00Z",
            path="a.py",
        )
    feed = RenameFeed([{"old_locator": "python:function:a", "new_locator": "python:function:a"}])
    env = commands.entity_timeline(repo, "python:function:a", rename_feed=feed)
    assert env["enrichment"]["governance"] == "present"
    assert env["enrichment_reasons"]["governance"] == {"reason_class": "clean"}
```

- [ ] Run them and watch them fail:
```bash
cd /home/john/warpline && python -m pytest tests/test_honesty_invariant.py -k "capture_sei_unavailable or governance" -q
```
Expected failure: `KeyError: 'sei'` for capture (capture has no `enrichment_reasons` arg yet) and `KeyError: 'governance'` for timeline.

- [ ] Import `reason` into `commands.py`. In `src/warpline/commands.py`, extend the `listing` import block (lines 18-24):
```python
from warpline.listing import (
    apply_filters,
    apply_group_by,
    apply_overflow,
    apply_page,
    apply_sort,
    reason,
)
```

- [ ] Wire `capture_snapshot`. In `src/warpline/commands.py`, replace the `capture_snapshot` return (lines 1111-1117):
```python
        return build_envelope(
            SCHEMA_EDGE_SNAPSHOT,
            query=query,
            data=data,
            enrichment=enrichment_state(edges=edges_state, sei=sei_state),
            enrichment_reasons={"sei": sei_reason(sei_state)},
            warnings=completeness_warnings(str(data["completeness"])) + warnings,
        )
```
(`sei_state` here is `"unavailable"` or `"absent"` — both map to a non-None triple via `sei_reason`.)

- [ ] Wire the governance triple into `entity_timeline`. In `src/warpline/commands.py`, replace the `entity_timeline` return that Task 4 produced so `enrichment_reasons` carries BOTH `sei` and `governance`:
```python
        sei_state = "present" if entity_out["sei"] else "absent"
        if rename_feed is not None:
            governance_reason = reason("clean")
        else:
            governance_reason = reason(
                "disabled",
                cause=(
                    "no rename-feed governance transport was supplied, so the timeline is a "
                    "raw-git stitch with no rename-aware governance provenance"
                ),
                fix=(
                    "pass a RenameFeed (a legis/rename governance read) to entity_timeline so "
                    "pre-rename events stitch with governance provenance; until then governance "
                    "is honestly disabled, not empty"
                ),
            )
        return build_envelope(
            SCHEMA_ENTITY_TIMELINE,
            query=query,
            data=data,
            enrichment=enrichment_state(
                sei=sei_state,
                governance="present" if rename_feed is not None else "unavailable",
            ),
            enrichment_reasons={"sei": sei_reason(sei_state), "governance": governance_reason},
            warnings=overflow_warnings,
        )
```

- [ ] Run the new tests and watch them pass:
```bash
cd /home/john/warpline && python -m pytest tests/test_honesty_invariant.py -k "capture_sei_unavailable or governance" -q
```
Expected: `3 passed`.

- [ ] Confirm GV-LG-2 (the scalar-only governance vector) and GV-LW-5 still pass:
```bash
cd /home/john/warpline && python -m pytest "tests/contracts/test_golden_vectors.py::test_gv_lg_2_timeline_stitches_across_rename_feed" "tests/contracts/test_golden_vectors.py::test_gv_lw_5_sei_resolution_present_vs_unavailable" -q
```
Expected: `2 passed`.

- [ ] Lint + type-check:
```bash
cd /home/john/warpline && ruff check src/warpline/commands.py && pyright src/warpline/commands.py
```
Expected: ruff `All checks passed!`; pyright `0 errors`.

- [ ] Commit:
```bash
cd /home/john/warpline && git add src/warpline/commands.py tests/test_honesty_invariant.py && git commit -m "feat(commands): sei unreachable triple on capture + governance triple on timeline

capture_snapshot (the only sei:unavailable emitter) now carries the
unreachable triple (Loomweave down). entity_timeline's governance scalar
gains a triple: clean when a rename-feed is supplied, disabled (no transport)
otherwise. Scalars unchanged; GV-LG-2 and GV-LW-5 stay green.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6 — Golden-vector lock: extend the executable spec + portable fixture (WS3 overlap)

The honesty-completeness invariants must be locked as frozen golden vectors so the hub-handover package (WS3) advertises them. Add new vectors to BOTH the executable `tests/contracts/test_golden_vectors.py` and the portable `tests/fixtures/contracts/warpline/golden-vectors.json`. This is the "14+N" extension the spec calls for.

**Files:**
- Modify `tests/contracts/test_golden_vectors.py` (add vectors after line 359)
- Modify `tests/fixtures/contracts/warpline/golden-vectors.json` (add entries to `vectors`)

**Interfaces:**
- Consumes: `commands.change_list`, `commands.capture_snapshot`, `commands.entity_timeline` (unchanged signatures); the `enrichment_reasons` carrier (Task 1).
- Produces: 3 new frozen golden vectors (GV-LW-6 sei triple, GV-LG-4 governance triple, GV-RQ-1 requirements reserved).

**Steps:**

- [ ] Write the new vectors. In `tests/contracts/test_golden_vectors.py`, append after line 359:
```python
# ============================================================ honesty completeness (WS2)
def test_gv_lw_6_sei_absence_carries_explained_triple(tmp_path: Path) -> None:
    """GV-LW-6: sei absence is EXPLAINED — change_list with no SEI emits
    sei:absent + unresolved_input triple; capture with Loomweave down emits
    sei:unavailable + unreachable triple. Never a bare, unexplained scalar."""

    repo = _git_repo(tmp_path)
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        a = _seed_entity(store, repo_id, "python:function:m.py::f", None)
        _add_change(store, repo_id, a, path="m.py")
    listed = commands.change_list(repo)
    assert listed["enrichment"]["sei"] == "absent"
    assert listed["enrichment_reasons"]["sei"]["reason_class"] == "unresolved_input"

    captured = commands.capture_snapshot(repo, commit="c1", loomweave_command="/no/such")
    assert captured["enrichment"]["sei"] == "unavailable"
    assert captured["enrichment_reasons"]["sei"]["reason_class"] == "unreachable"


def test_gv_lg_4_timeline_governance_carries_explained_triple(tmp_path: Path) -> None:
    """GV-LG-4: entity_timeline governance is EXPLAINED — present->clean with a
    rename feed, disabled (no transport) without one."""

    repo = _git_repo(tmp_path)
    old = "python:function:old_mod.py::f"
    new = "python:function:new_mod.py::f"
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        a = _seed_entity(store, repo_id, old, None)
        _add_change(store, repo_id, a, path="old_mod.py", commit="c1")

    feed = RenameFeed([{"old_locator": old, "new_locator": new}])
    with_feed = commands.entity_timeline(repo, new, rename_feed=feed)
    assert with_feed["enrichment"]["governance"] == "present"
    assert with_feed["enrichment_reasons"]["governance"] == {"reason_class": "clean"}

    without_feed = commands.entity_timeline(repo, new)
    assert without_feed["enrichment"]["governance"] == "unavailable"
    assert without_feed["enrichment_reasons"]["governance"]["reason_class"] == "disabled"


def test_gv_rq_1_requirements_is_reserved_but_honest_on_every_tool(tmp_path: Path) -> None:
    """GV-RQ-1: the reserved requirements dimension carries a stable disabled
    triple (reserved, not yet wired) on every tool — scalar stays unavailable."""

    repo = _git_repo(tmp_path)
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        a = _seed_entity(store, repo_id, "python:function:m.py::a", "loomweave:eid:aaaa")
        _add_change(store, repo_id, a, path="m.py")
        a_id = a
    envelopes = [
        commands.change_list(repo),
        commands.entity_timeline(repo, "python:function:m.py::a"),
        commands.entity_churn_count(repo, [{"kind": "sei", "value": "loomweave:eid:aaaa"}]),
        commands.impact_radius(repo, [a_id]),
        commands.reverify_worklist(repo, [a_id]),
        commands.capture_snapshot(repo, commit="c1", loomweave_command="/no/such"),
    ]
    for env in envelopes:
        assert env["enrichment"]["requirements"] == "unavailable"
        triple = env["enrichment_reasons"]["requirements"]
        assert triple["reason_class"] == "disabled"
        assert "reserved" in triple["cause"].lower()
```

- [ ] Run the new vectors and watch them pass (the implementation already landed in Tasks 2-5; these LOCK it):
```bash
cd /home/john/warpline && python -m pytest tests/contracts/test_golden_vectors.py -k "gv_lw_6 or gv_lg_4 or gv_rq_1" -q
```
Expected: `3 passed`. (If any fails, the implementation in Tasks 2-5 is incomplete — fix the implementation, NOT the vector.)

- [ ] Add the portable fixture entries. In `tests/fixtures/contracts/warpline/golden-vectors.json`, add three entries to the `vectors` array (after `GV-LG-3`, before the closing `]`):
```json
    {"id": "GV-LW-6", "seam": "loomweave", "tool": "warpline_change_list / warpline_edge_snapshot_capture",
     "assert": "sei absence is explained: change_list no-SEI -> enrichment.sei absent + enrichment_reasons.sei reason_class unresolved_input; capture loomweave-down -> sei unavailable + reason_class unreachable"},
    {"id": "GV-LG-4", "seam": "legis", "tool": "warpline_entity_timeline_get",
     "assert": "timeline governance is explained: rename feed -> governance present + enrichment_reasons.governance clean; no feed -> governance unavailable + reason_class disabled"},
    {"id": "GV-RQ-1", "seam": "all", "tool": "all six",
     "assert": "reserved requirements dimension carries a stable disabled triple (reserved, not yet wired) on every tool; scalar stays unavailable"}
```
(Add a comma after the existing `GV-LG-3` object's closing `}` so the JSON stays valid.)

- [ ] Validate the JSON fixture parses and now lists 17 vectors:
```bash
cd /home/john/warpline && python -c "import json; v=json.load(open('tests/fixtures/contracts/warpline/golden-vectors.json'))['vectors']; print(len(v)); assert [x['id'] for x in v][-3:]==['GV-LW-6','GV-LG-4','GV-RQ-1']; print('ok')"
```
Expected: `17` then `ok`.

- [ ] Run the FULL golden-vector suite to prove nothing in the frozen 14 regressed:
```bash
cd /home/john/warpline && python -m pytest tests/contracts/test_golden_vectors.py -q
```
Expected: `17 passed`.

- [ ] Lint the test file:
```bash
cd /home/john/warpline && ruff check tests/contracts/test_golden_vectors.py
```
Expected: `All checks passed!`.

- [ ] Commit:
```bash
cd /home/john/warpline && git add tests/contracts/test_golden_vectors.py tests/fixtures/contracts/warpline/golden-vectors.json && git commit -m "test(contracts): lock honesty-completeness as golden vectors GV-LW-6/LG-4/RQ-1

Extend the frozen 14 to 17: sei absence carries an explained triple
(unresolved_input vs unreachable), timeline governance carries a triple
(clean vs disabled), and the reserved requirements dimension carries a
stable disabled triple on all six tools. Portable JSON fixture updated in
lockstep so the hub loads the extended spec verbatim.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7 — Full-gate verification (vectors green, no regressions, all gates pass)

Prove the whole change set is honest-complete and breaks nothing the gates protect.

**Files:** none (verification-only task).

**Interfaces:** none.

**Steps:**

- [ ] Run the full pytest suite:
```bash
cd /home/john/warpline && python -m pytest -q
```
Expected: all pass (0 failed). In particular `tests/test_enrichment_merge.py` (the R6 scalar tests at lines 94, 112) stays green because the `risk`/`governance` SCALARS on `reverify_worklist` are unchanged — this plan only adds the `requirements` triple and the read/timeline/capture triples.

- [ ] Run ruff and pyright across the touched modules:
```bash
cd /home/john/warpline && ruff check src/warpline tests && pyright src/warpline
```
Expected: ruff `All checks passed!`; pyright `0 errors, 0 warnings`.

- [ ] Run the two warpline self-gates the global constraints name:
```bash
cd /home/john/warpline && warpline dogfood-eval && warpline mcp-smoke
```
Expected: both exit 0. (`mcp-smoke` exercises the live envelope shape; the additive `enrichment_reasons` key must not trip it. If `mcp-smoke` asserts an exact top-level key set, update its expected key set to include `enrichment_reasons` — that is part of this task, since the carrier is intentionally additive.)

- [ ] Run the member-diff guard to confirm the envelope shape change is the intended additive one:
```bash
cd /home/john/warpline && git diff --stat main...HEAD
```
Expected: only `src/warpline/envelope.py`, `src/warpline/_enrichment.py`, `src/warpline/commands.py`, and the test/fixture files changed. If the member-diff guard is a script (check `scripts/` or `Makefile` for `member-diff`), run it:
```bash
cd /home/john/warpline && ls scripts/ 2>/dev/null | grep -i diff; grep -rn "member-diff\|member_diff" Makefile pyproject.toml 2>/dev/null
```
If a guard command exists, run it and confirm it reports the `enrichment_reasons` addition as an ALLOWED additive change (not a removed/renamed key). If it flags any REMOVED or RENAMED key, the implementation diverged — stop and fix.

- [ ] Confirm the local-only invariant holds on every tool (regression check for the carrier):
```bash
cd /home/john/warpline && python -m pytest "tests/contracts/test_golden_vectors.py::test_gv_lg_3_every_response_is_local_only_with_no_side_effects" -q
```
Expected: `1 passed`.

- [ ] No commit needed (verification-only). If `mcp-smoke`'s expected key set was edited in this task, commit that:
```bash
cd /home/john/warpline && git status --porcelain
```
If anything is modified, stage and commit:
```bash
cd /home/john/warpline && git add -A && git commit -m "test(gates): allow additive enrichment_reasons key in mcp-smoke expectations

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Done criteria

- `enrichment_reasons` is an additive top-level envelope key (Task 1), defaulting to a map that always carries the reserved `requirements` triple (Task 2).
- All FOUR sei-emitting tools (`change_list`, `entity_timeline`, `entity_churn_count`, `capture_snapshot`) carry a `sei` triple: `clean`/`unresolved_input`/`unreachable` (Tasks 4-5). `impact_radius` and `reverify_worklist` are untouched — they never emitted `sei`.
- `entity_timeline` `governance` carries a `clean`/`disabled` triple (Task 5).
- `requirements` is reserved-but-honest: scalar `unavailable` + stable `disabled` triple on every tool (Task 2), key NOT removed.
- No new `reason_class` was added; the canonical-11 guard at `tests/test_list_ergonomics.py:457` is untouched.
- The frozen 14 golden vectors still pass; 3 new vectors (GV-LW-6, GV-LG-4, GV-RQ-1) lock the new invariants in both the executable suite and the portable JSON fixture (Task 6).
- ruff, pyright, full pytest, `warpline dogfood-eval`, `warpline mcp-smoke`, and the member-diff guard are green (Task 7); `meta.local_only`/`peer_side_effects` invariant intact.
