# Warpline 5th-Producer Conformance — Hub Handover (DRAFT package)

Date: 2026-06-22
Status: DRAFT — handover package for the federation hub owner. This document
freezes nothing and creates no hub or sibling work. It describes a package the
owner may, on their signal, wire into the GS-7 oracle and freeze. (Authority
boundary: warpline's grant is repo-local; GS-7 inclusion and the glossary freeze
are the owner's act.)

Producer: warpline (admitted 2026-06-13 as the federation's 5th member, PDR-0022).
Branch of record: plan/spine-hardening (work executed in worktree branch harden/exec).

## 1. What 5th-producer conformance is

Warpline contributes a golden-vector suite to the four-member GS-7 conformance
oracle as a fifth producer. The suite is two artifacts:

- `tests/fixtures/contracts/warpline/golden-vectors.json` — the vector **manifest**
  (an index of `{id, seam, tool, assert}` objects). It is NOT a data-driven replay
  oracle; the `assert` strings are prose.
- `tests/contracts/test_golden_vectors.py` — the **executable**. It builds real-git
  fixtures + stubbed loomweave clients and calls `warpline.commands` /
  `warpline.snapshot` directly. The live assertions are here.

### Vector inventory (count: 14 legacy + 4 new = 18 manifest objects)

The interface-lock and the test module docstring say "14 golden vectors"; that is
doctrine that counts `GV-LG-3` ("all six tools carry local-only + no side effects")
as spanning more than one logical check. The JSON manifest enumerates 14 legacy
objects. This package ADDS 4:

- Legacy (frozen 2026-06-13): `GV-LW-1..5`, `GV-FI-1..3`, `GV-WL-1..3`, `GV-LG-1..3`.
- New, this hardening work (Plans A and B, branch harden/exec):
  - `GV-LW-6` — atomic-capture fail-closed: a hard mid-capture loomweave failure
    leaves the PRIOR snapshot intact and visible; no edge_snapshots row is visible
    until all its edges are committed (never a published-but-empty/half-written row).
    Pins Plan A's visibility invariant.
  - `GV-HON-SEI` — `sei` absence/unavailability carries a `{reason_class, cause, fix}`
    triple distinguishing never-resolved (`unresolved_input`) from
    loomweave-unreachable (`unreachable`).
  - `GV-HON-GOV` — `entity_timeline` governance carries a triple (clean with
    rename-feed, disabled without), not bare vocab.
  - `GV-HON-REQ` — `requirements` stays in the frozen vocab as reserved-but-honest:
    a stable `disabled` reason_class declaring "reserved, not yet wired", never a
    silent bare `unavailable`.

### The frozen envelope / error contract

- **Success envelope** (`warpline.<contract>.v1`): keys `{schema, ok, query, data,
  warnings, next_actions, enrichment, meta}`. `meta.local_only` is always `true`;
  `meta.peer_side_effects` is always `[]`.
- **Enrichment vocab** (CLOSED, `src/warpline/envelope.py:12-19`): 6 keys —
  `sei` / `work` / `risk` / `governance` / `requirements` ∈ {present, absent,
  unavailable}; `edges` ∈ {present, absent, stale, partial, skipped, unavailable}.
- **Weft-reason triple** (`src/warpline/listing.py`): `{reason_class, cause, fix}`,
  built only via `reason()`. `clean` omits cause/fix; every other class carries
  both. The canonical 11 reason classes: `clean`, `disabled`, `unresolved_input`,
  `rejected`, `dead_path`, `unreachable`, `misrouted`, `error`, `scheme_mismatch`,
  `stale`, `partial`.
- **Error contract** (`warpline.error.v1`, `src/warpline/errors.py`): 11 closed
  error codes — `missing_required_field`, `invalid_repo`, `invalid_rev_range`,
  `invalid_entity_ref`, `invalid_changed_refs`, `invalid_depth`, `invalid_filter`,
  `invalid_sort`, `peer_unavailable`, `snapshot_unavailable`, `internal_error`. 3
  retryability values — `retry_safe`, `retry_with_changes`, `fatal`. Additions are
  a v2 contract URI, never a mutation of v1.

### Endorsed MCP names + shims (6 pairs)

Each pair returns identical schema + data. The endorsed name is canonical; the
short shim is an ergonomic alias.

| Endorsed name | Shim | Data schema | Mutates |
|---|---|---|---|
| `warpline_impact_radius_get` | `blast_radius` | `warpline.impact_radius.v1` | no |
| `warpline_edge_snapshot_capture` | `capture_snapshot` | `warpline.edge_snapshot.v1` | **yes** (only mutating tool) |
| `warpline_change_list` | `changed` | `warpline.change_list.v1` | no |
| `warpline_entity_churn_count_get` | `churn` | `warpline.entity_churn_count.v1` | no |
| `warpline_reverify_worklist_get` | `reverify` | `warpline.reverify_worklist.v1` | no |
| `warpline_entity_timeline_get` | `timeline` | `warpline.entity_timeline.v1` | no |

Inventory source of record: `tests/fixtures/contracts/warpline/mcp-tool-inventory.json`
(schema `warpline.mcp_tool_inventory.v1`, status `admitted-frozen`). The capture
tool writes only `.weft/warpline/`; all tools are `local_only: true`,
`peer_side_effects: []`.

## 2. How to wire it into GS-7 CI

- **Fixture location:** mount `tests/fixtures/contracts/warpline/golden-vectors.json`
  and `tests/fixtures/contracts/warpline/mcp-tool-inventory.json` into the oracle's
  fixture tree. Both are now portable: the manifest's `executable` is a relocatable
  descriptor (no warpline-tree-relative path), and the warpline-side contract test
  anchors its fixture root to the test file (cwd-independent).
- **Executable entry point:** `tests/contracts/test_golden_vectors.py`. This is a
  pytest module, NOT a JSON replay. The oracle must run it with the `warpline`
  package importable on `sys.path` (the manifest `executable.import_requires` field
  names this dependency: `warpline`). It builds its own real-git + stubbed-loomweave
  fixtures; it needs `git` on PATH.
- **Producer-registration shape the four-member oracle expects:** register warpline
  as a producer keyed on `producer: "warpline"` (manifest field), advertising
  `schema: "warpline.golden_vectors.v1"`, the `executable` descriptor, and the
  `vectors[]` index. The oracle runs the pytest module and gates on its exit code;
  green = all 18 vectors pass.

## 3. The decision the owner is waiting on — OD-5 (RESOLVED-direction; wiring pending)

OD-5 is NOT an open adjudication. The interface-lock §8 records it resolved at lock
time (owner nod 2026-06-13):

> OD-5 → FOLD INTO GS-7. warpline's 14 golden vectors join the existing four-member
> conformance oracle as a fifth producer (one oracle, one gate, C-12).

Original call-needed rationale (retained for provenance, §8):

> OD-5 — Does the golden-vector gate for warpline run at the SAME four-member
> contract gate (GS-7 oracle), or a separate warpline gate? ... fold warpline's 14
> golden vectors (§1D, 2C, 3C, 4C) into the existing four-member conformance oracle
> as a fifth producer, or stand up a warpline-specific gate. Recommendation: fold
> into the existing oracle — same discipline, one gate, per [do-it-right]
> gold-standard. This is a launch-runbook ordering call, owner-visible.

**Owner's remaining action:** the launch-runbook *wiring* (registering warpline as
the 5th producer in the GS-7 oracle and turning the gate on), not the decision
itself. Source: `weft/pm/2026-06-13-warpline-interface-lock.md` §8.

## 4. Glossary-freeze checklist (freeze-attestation on the owner's signal)

These vocabularies are already named non-draft (`warpline.<contract>.v1`;
`mcp-tool-inventory.json` status is `admitted-frozen`; the contract test asserts no
`.draft.` string). This is therefore an ATTESTATION list the owner signs on the
freeze signal — NOT a set of pending code renames.

- [ ] **Exact MCP names** — the 6 endorsed names + 6 shims (table in §1) frozen as
  the public tool surface.
- [ ] **Error codes** — the 11 codes + 3 retryability values (`errors.py`) frozen
  under `warpline.error.v1`.
- [ ] **Enrichment vocab** — the 6 closed keys + value sets (`envelope.py`) and the
  canonical 11 reason classes (`listing.py`) frozen.
- [ ] **Schema URIs** — `warpline.golden_vectors.v1`, `warpline.mcp_tool_inventory.v1`,
  `warpline.error.v1`, and the 6 `warpline.<contract>.v1` data schemas frozen;
  any future change is a new vN+1 URI, never a v1 mutation.

## 5. Proven vs unproven (status)

**Local conformance:** PROVEN — all 18 golden vectors green locally on branch
harden/exec; full suite green. Contract suite: 22 passed. Full suite: 333 passed,
3 skipped. Plans A (atomic-capture, GV-LW-6) and B (sei/governance/requirements
triples, GV-HON-SEI / GV-HON-GOV / GV-HON-REQ) are complete and merged on this
branch.

**Sibling-consumption gaps remaining post-admission** (enrich-only, non-binding —
honest absence, never an implied clean state):

- **loomweave** — PROVEN + FROZEN. Real consumption (`entity_resolve`,
  `entity_neighborhood_get`) in HX1 and capture.
- **filigree** — EARNED. warpline consumes `entity_association_list_by_entity` +
  `issue_get` for reverify work-enrichment (GV-FI-1, GV-FI-3).
- **wardline** — NON-BINDING, degrade-only. warpline does not consume wardline
  findings; `risk` reads `unavailable` with a triple. The transport is
  disabled-by-default (`federation.py:_consult_wardline` returns
  `reason("disabled", ...)` when no `RiskClient` is passed). GV-WL-3 pins this.
- **legis** — NON-BINDING member. The generic locator-rename FEED shape is earned
  (GV-LG-2); legis stays a future external supplier. No per-SEI governance read
  transport is wired (`federation.py:_consult_legis` returns `reason("disabled", ...)`
  when no `LegisClient` is passed); governance reads `unavailable` with a triple.

These gaps are by design: warpline is enrich-only and every absence is explained,
never faked clean. Closing them is sibling-side implementation work, post-admission,
outside warpline's authority grant.
