# Conformance Package + Hub Handover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Extend warpline's golden-vector suite to pin Plan A's capture-visibility invariant and Plan B's triple-on-absence honesty, make the vector fixture portable so the federation hub can load it verbatim, and author the 5th-producer hub handover document as a draft package.

**Architecture:** The golden vectors are split across two artifacts: `tests/fixtures/contracts/warpline/golden-vectors.json` (a prose *manifest* of vector ids + assertions) and `tests/contracts/test_golden_vectors.py` (the *executable* that builds real-git fixtures, calls `warpline.commands`/`warpline.snapshot` directly, and carries the live assertions). This plan adds new vector ids to both, removes the two warpline-local path assumptions (the manifest's repo-relative `executable` key and the contract test's cwd-relative `FIXTURES` path) so the hub can relocate the fixture, and writes the handover doc. This plan is the gated capstone: it depends on Plan A (atomic capture) and Plan B (sei/governance/requirements triples) being green; its new vectors fail against current code until A and B land.

**Tech Stack:** Python 3, pytest, ruff, pyright, JSON fixtures, SQLite-backed `WarplineStore`, real-git subprocess fixtures.

## Global Constraints

- Python repo. Tooling: ruff (lint), pyright (types), pytest (tests). TDD throughout.
- Sequencing is VECTORS-FIRST: each plan opens by writing the failing golden vector / test that expresses the invariant, THEN the implementation makes it green.
- WS1 capture changes are OUTPUT-SHAPE-PRESERVING: the response envelope stays byte-identical; only edge-visibility timing and row lifecycle change.
- Enrichment vocab is a CLOSED, FROZEN contract in src/warpline/envelope.py (keys: sei, edges, work, risk, governance, requirements). Do NOT add or remove keys. The `requirements` key stays (resolved as reserved-but-honest).
- The weft-reason triple is `cause + reason_class + fix`, built ONLY via src/warpline/listing.py `reason()` factory (non-"clean" reason_class requires both cause and fix).
- Every response MUST keep `meta.local_only: true` and `meta.peer_side_effects: []`. Never break the frozen golden vectors or the success/error envelope schema.
- Gates that must stay green: `warpline dogfood-eval`, `warpline mcp-smoke`, ruff, pyright, pytest, and the member-diff guard.
- Authority boundary: all work is reversible and repo-local. The hub handover document is a DRAFT package — it creates no hub/sibling work and freezes nothing.
- Commit messages end with the trailer: Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>

---

## Reground notes the implementer MUST internalise before starting

These are facts from the current code on branch `plan/spine-hardening`. Reference no
symbol that contradicts them.

1. **Vector count is 13 manifest objects, "14" is doctrine.** `golden-vectors.json`
   enumerates exactly **13** vector objects: `GV-LW-1`..`GV-LW-5`, `GV-FI-1`..`GV-FI-3`,
   `GV-WL-1`..`GV-WL-3`, `GV-LG-1`..`GV-LG-3`. `test_golden_vectors.py` defines exactly
   13 test functions. The "14 FROZEN golden vectors" phrase in the test module docstring
   (line 1) and the interface-lock is doctrine that counts `GV-LG-3` ("all six tools") as
   spanning more than one logical vector. **Do not assume a 14th JSON object exists.** This
   plan adds new ids `GV-CAP-1`, `GV-CAP-2` (Plan A invariant) and `GV-HON-1`, `GV-HON-2`,
   `GV-HON-3` (Plan B triples) — additive, never renumbering the frozen `GV-*` namespace.

2. **The fixture is NOT a data-driven oracle.** The JSON `assert` strings are prose. The
   real assertions live in Python; `test_golden_vectors.py` does not read the JSON. "Portable
   so the hub can load it verbatim" therefore means: (a) the manifest's `executable` key
   (line 6) is a warpline-repo-relative path the hub cannot resolve — parameterize it; (b) the
   sibling contract test `test_warpline_contract_fixtures.py` uses `FIXTURES = Path("tests/fixtures/contracts/warpline")`
   (line 8), a cwd-relative path — anchor it to the test file. The handover doc must state that
   GS-7 wiring runs the **Python executable** (it needs the `warpline` package importable), not
   a JSON-only replay.

3. **Plan A re-architects `snapshot.py`/`store.py`; this plan only PINS the result.** Do NOT
   edit `snapshot.py`, `store.py`, `commands.py`, `envelope.py`, `listing.py`, or `federation.py`
   in this plan. The CAP/HON vectors read behaviour through the public surface
   (`warpline.commands`, `warpline.snapshot.capture_edge_snapshot`, `store.latest_snapshot`).

4. **OD-5 is resolved, not open.** Interface-lock §8 (`~/weft/pm/2026-06-13-warpline-interface-lock.md`)
   records: "OD-5 → FOLD INTO GS-7. warpline's 14 golden vectors join the existing four-member
   conformance oracle as a fifth producer (one oracle, one gate, C-12)." The handover frames the
   owner's remaining action as launch-runbook *wiring*, not adjudication.

5. **"draft→frozen" is a freeze-attestation list, not code edits.** Schemas are already named
   `warpline.<contract>.v1` and `test_warpline_contract_fixtures.py:63` asserts `.draft.` is absent;
   `mcp-tool-inventory.json` status is already `admitted-frozen`. The glossary-freeze checklist is a
   governance/signal artifact, not a string rename.

6. **Plan C cannot be green until A and B land.** The CAP vectors fail against today's two-step
   capture (`snapshot.py:95-101` then `:130-136`); the HON vectors fail against today's bare-vocab
   sei/governance and inert `requirements`. This is the intended vectors-first failure. The handover's
   "local pass" status is conditioned on A+B being merged — Task 9 gates the status claim on a live
   green run.

---

## Task 1 — Pin Plan A's capture-visibility invariant: prior snapshot survives a mid-capture failure

**Files:**
- Modify: `tests/contracts/test_golden_vectors.py` (append after `test_gv_lw_5_sei_resolution_present_vs_unavailable`, currently ending at line 202; add a new test plus one helper client class near the other client stubs around line 84-91)

**Interfaces:**
- Consumes: `warpline.snapshot.capture_edge_snapshot(store, repo, *, commit_sha=None, client, source_version, scope_locators=None, scope_failures=None, max_entities=None) -> dict[str, Any]` (snapshot.py:45)
- Consumes: `warpline.store.WarplineStore.latest_snapshot(repo: Path) -> dict[str, object] | None` (store.py:1470)
- Consumes: `warpline.store.WarplineStore.create_edge_snapshot(repo_id, commit_sha, source, source_version, completeness) -> int` (store.py:1403) and `append_snapshot_edge(...)` (store.py:1431)
- Produces: test `test_gv_cap_1_mid_capture_failure_leaves_prior_snapshot_intact(tmp_path: Path) -> None` and helper `class _ExplodingNeighborhoodClient`

**Steps:**

- [ ] Add the failing helper client + test. Insert this class immediately after `_TruncatedNeighborhoodClient` (which ends at line 90 of `tests/contracts/test_golden_vectors.py`):

```python
class _ExplodingNeighborhoodClient:
    """A loomweave that resolves the first entity then dies mid-capture — drives the
    fail-closed branch (mid-capture failure must leave the PRIOR snapshot intact)."""

    def __init__(self) -> None:
        self.calls = 0

    def neighborhood(self, entity: str) -> dict[str, Any]:
        self.calls += 1
        raise RuntimeError("loomweave connection dropped mid-capture")
```

  Then append this test at the end of the SEAM 1 block (after `test_gv_lw_5_...`, line 202):

```python
def test_gv_cap_1_mid_capture_failure_leaves_prior_snapshot_intact(tmp_path: Path) -> None:
    """GV-CAP-1 (Plan A visibility invariant): a mid-capture loomweave failure leaves the
    PRIOR snapshot intact and visible — never a half-written or emptied new one."""
    repo = _git_repo(tmp_path)
    head = _git(repo, ["rev-parse", "HEAD"]).strip()
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        a = _seed_entity(store, repo_id, "python:function:m.py::a", "loomweave:eid:aaaa", head)
        b = _seed_entity(store, repo_id, "python:function:m.py::b", "loomweave:eid:bbbb", head)
        # A prior FULL snapshot with one real edge is the visible state of record.
        prior = store.create_edge_snapshot(repo_id, head, "loomweave", "prior", "FULL")
        store.append_snapshot_edge(
            prior, source_entity_key_id=a, target_entity_key_id=b,
            edge_kind="calls", confidence="resolved",
        )
        prior_edges = len(store.snapshot_edges(prior))
        assert prior_edges == 1

        # Capture against a client that explodes mid-loop. It MUST NOT publish an
        # empty/partial snapshot over the prior one.
        try:
            capture_edge_snapshot(
                store, repo, commit_sha=head, client=_ExplodingNeighborhoodClient(),
                source_version="doomed",
            )
        except Exception:
            pass

        latest = store.latest_snapshot(repo)
        assert latest is not None
        # The visible snapshot is never empty: its edges survived the failed capture.
        assert len(store.snapshot_edges(int(latest["id"]))) == prior_edges
        # And it is never a freshly published-but-empty row for this commit.
        assert latest["completeness"] in {"FULL", "DELTA"}
```

- [ ] Run it and see it fail against current two-step capture. Command:

```bash
python -m pytest tests/contracts/test_golden_vectors.py::test_gv_cap_1_mid_capture_failure_leaves_prior_snapshot_intact -q
```

  Expected output (current code mints/upserts an empty intermediate row via `create_edge_snapshot` + `clear_snapshot_edges` at snapshot.py:95-102, so `latest_snapshot` selects a row whose edges were cleared mid-window):

```
F                                                                        [100%]
=================================== FAILURES ===================================
... assert len(store.snapshot_edges(int(latest["id"]))) == prior_edges
E   assert 0 == 1
1 failed in 0.XXs
```

- [ ] STOP. This test is RED by design (vectors-first). It goes green only when Plan A's atomic-capture re-architecture lands. Do NOT edit `snapshot.py` or `store.py` here. Commit the failing vector as the deliverable:

```bash
git add tests/contracts/test_golden_vectors.py
git commit -m "test(GV-CAP-1): pin prior-snapshot-survives-mid-capture-failure (red until Plan A)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 — Pin Plan A's invariant: a mid-capture reader never sees a published-but-empty snapshot

**Files:**
- Modify: `tests/contracts/test_golden_vectors.py` (append after the Task 1 test in the SEAM 1 block)

**Interfaces:**
- Consumes: `warpline.snapshot.capture_edge_snapshot(...)` (snapshot.py:45)
- Consumes: `warpline.store.WarplineStore.latest_snapshot(repo)` (store.py:1470), `.snapshot_edges(snapshot_id)` (store.py:1484)
- Produces: test `test_gv_cap_2_no_published_empty_snapshot_for_full_capture(tmp_path: Path) -> None`

**Steps:**

- [ ] Append this test immediately after `test_gv_cap_1_...`:

```python
def test_gv_cap_2_no_published_empty_snapshot_for_full_capture(tmp_path: Path) -> None:
    """GV-CAP-2 (Plan A visibility invariant): when a FULL capture completes, the latest
    visible snapshot has its edges present — there is no window where latest_snapshot()
    resolves a published-but-empty row. We assert the post-condition the atomic txn
    guarantees: the visible row's id carries the edge count the capture reported."""
    repo = _git_repo(tmp_path)
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        _seed_entity(store, repo_id, "python:function:pkg/mod.py::a", None)
        _seed_entity(store, repo_id, "python:function:pkg/other.py::b", None)
        result = capture_edge_snapshot(
            store, repo, commit_sha="c1", client=_FullNeighborhoodClient(),
            source_version="t",
        )
        assert result["completeness"] == "FULL"
        assert result["edges"] > 0

        latest = store.latest_snapshot(repo)
        assert latest is not None
        # The published row is the one the capture produced AND it already has its edges.
        visible_edges = store.snapshot_edges(int(latest["id"]))
        assert len(visible_edges) == result["edges"]
        assert latest["completeness"] == "FULL"
```

- [ ] Run it. Command:

```bash
python -m pytest tests/contracts/test_golden_vectors.py::test_gv_cap_2_no_published_empty_snapshot_for_full_capture -q
```

  Expected: under Plan A this PASSES (atomic capture publishes the row with edges already present); under current two-step capture it may pass *by accident* because the second `create_edge_snapshot` upserts the same `(repo,commit,source)` row after edges were appended. That accidental pass is acceptable — GV-CAP-1 is the discriminating red test. If it fails, the failure is the empty-window symptom:

```
.                                                                        [100%]
1 passed in 0.XXs
```

  (If RED instead, that is also acceptable vectors-first; do not patch `snapshot.py`.)

- [ ] Commit:

```bash
git add tests/contracts/test_golden_vectors.py
git commit -m "test(GV-CAP-2): pin FULL-capture publishes row with edges present

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 — Pin Plan B's triple-on-absence for `sei` (never-resolved vs loomweave-unreachable)

**Files:**
- Modify: `tests/contracts/test_golden_vectors.py` (append a new SEAM "honesty" block after the SEAM 4 legis block, which currently ends at line 360)

**Interfaces:**
- Consumes: `warpline.commands.change_list(repo: Path, ...) -> dict` (commands.py:311; emits `enrichment.sei`)
- Consumes: `warpline.commands.capture_snapshot(repo, commit=..., loomweave_command=...) -> dict` (commands.py:965; emits `enrichment.sei`)
- Consumes (Plan B Produces): the top-level `enrichment_reasons` carrier on the response that holds the `{reason_class, cause, fix}` triple for `sei`. Plan B adds a `sei_warnings()` reason path mirroring `completeness_warnings()` (`_enrichment.py:71-77`); the triple is surfaced on the response top level under `env["enrichment_reasons"]["sei"]` — a NEW top-level envelope key (sibling of the top-level `enrichment` key), NOT under `data` (Plan B Produces this key — see Plan B Task "sei triple plumbing").
- Produces: test `test_gv_hon_1_sei_absence_carries_reason_triple(tmp_path: Path) -> None`

> NOTE TO IMPLEMENTER: The carrier is CONFIRMED (no longer an open assumption): Plan B
> produces a NEW top-level envelope key `enrichment_reasons` — a sibling of the top-level
> `enrichment` key, NOT nested under `data` — a dict mapping dimension name → `{reason_class,
> cause, fix}`. These tests access it at the response top level (e.g.
> `env["enrichment_reasons"]["sei"]`). This plan pins the *shape* `{reason_class, cause, fix}`
> and that a non-`clean` class carries both `cause` and `fix`; keep the triple-shape assertions
> identical.

**Steps:**

- [ ] Append a new seam header and test at the end of the file (after line 360):

```python
# ===================================================== SEAM 5 — honesty triples (WS2)
def _assert_reason_triple(triple: dict[str, Any]) -> None:
    """A weft-reason carrier: clean omits cause/fix; every other class carries both."""
    assert "reason_class" in triple
    if triple["reason_class"] == "clean":
        assert "cause" not in triple and "fix" not in triple
    else:
        assert triple.get("cause") and triple.get("fix")


def test_gv_hon_1_sei_absence_carries_reason_triple(tmp_path: Path) -> None:
    """GV-HON-1 (Plan B): sei is never bare vocab on absence/unavailable — it carries a
    {reason_class, cause, fix} triple distinguishing never-resolved from loomweave-unreachable."""
    repo = _git_repo(tmp_path)
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        # An entity with NO sei (never resolved) — change_list reports sei absent.
        a = _seed_entity(store, repo_id, "python:function:m.py::a", None)
        _add_change(store, repo_id, a, path="m.py")

    present = commands.change_list(repo)
    assert present["enrichment"]["sei"] == "absent"
    sei_reason = present["enrichment_reasons"]["sei"]
    _assert_reason_triple(sei_reason)
    assert sei_reason["reason_class"] != "clean"  # absence is explained, not earned-empty

    # loomweave unreachable on capture → sei unavailable, with a transport-shaped triple.
    unavailable = commands.capture_snapshot(repo, commit="c1", loomweave_command="/no/such")
    assert unavailable["enrichment"]["sei"] == "unavailable"
    cap_reason = unavailable["enrichment_reasons"]["sei"]
    _assert_reason_triple(cap_reason)
    assert cap_reason["reason_class"] != "clean"
```

- [ ] Run it. Command:

```bash
python -m pytest tests/contracts/test_golden_vectors.py::test_gv_hon_1_sei_absence_carries_reason_triple -q
```

  Expected failure against current code (today `change_list`/`capture_snapshot` emit only the bare vocab string at commands.py:311 / :1115 and carry no `enrichment_reasons` key):

```
F                                                                        [100%]
=================================== FAILURES ===================================
... sei_reason = present["enrichment_reasons"]["sei"]
E   KeyError: 'enrichment_reasons'
1 failed in 0.XXs
```

- [ ] STOP — RED by design until Plan B lands. Do NOT edit `commands.py`/`_enrichment.py`. Commit:

```bash
git add tests/contracts/test_golden_vectors.py
git commit -m "test(GV-HON-1): pin sei triple-on-absence (red until Plan B)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 — Pin Plan B's `governance` triple on `entity_timeline` when unavailable

**Files:**
- Modify: `tests/contracts/test_golden_vectors.py` (append after the Task 3 test in the SEAM 5 block)

**Interfaces:**
- Consumes: `warpline.commands.entity_timeline(repo: Path, locator: str, *, rename_feed=None) -> dict` (commands.py:396; emits `enrichment.governance` = `present` if rename_feed else `unavailable`)
- Consumes (Plan B Produces): top-level `env["enrichment_reasons"]["governance"]` triple emitted when governance is `unavailable` (Plan B Task "governance triple on entity_timeline")
- Produces: test `test_gv_hon_2_governance_unavailable_carries_reason_triple(tmp_path: Path) -> None`

**Steps:**

- [ ] Append after `test_gv_hon_1_...`:

```python
def test_gv_hon_2_governance_unavailable_carries_reason_triple(tmp_path: Path) -> None:
    """GV-HON-2 (Plan B): entity_timeline governance == unavailable (no rename-feed transport)
    is explained by a triple, not a bare vocab value."""
    repo = _git_repo(tmp_path)
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        a = _seed_entity(store, repo_id, "python:function:m.py::f", None)
        _add_change(store, repo_id, a, path="m.py")

    without_feed = commands.entity_timeline(repo, "python:function:m.py::f")
    assert without_feed["enrichment"]["governance"] == "unavailable"
    gov_reason = without_feed["enrichment_reasons"]["governance"]
    _assert_reason_triple(gov_reason)
    assert gov_reason["reason_class"] != "clean"
```

- [ ] Run it. Command:

```bash
python -m pytest tests/contracts/test_golden_vectors.py::test_gv_hon_2_governance_unavailable_carries_reason_triple -q
```

  Expected failure (today entity_timeline emits bare `governance="unavailable"` at commands.py:396-398, no `enrichment_reasons`):

```
F                                                                        [100%]
... gov_reason = without_feed["enrichment_reasons"]["governance"]
E   KeyError: 'enrichment_reasons'
1 failed in 0.XXs
```

- [ ] STOP — RED until Plan B. Commit:

```bash
git add tests/contracts/test_golden_vectors.py
git commit -m "test(GV-HON-2): pin governance triple-on-unavailable (red until Plan B)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 — Pin Plan B's `requirements` reserved-but-honest reason

**Files:**
- Modify: `tests/contracts/test_golden_vectors.py` (append after the Task 4 test in the SEAM 5 block)

**Interfaces:**
- Consumes: `warpline.commands.change_list(repo)` (commands.py:311) — its envelope carries `enrichment.requirements` defaulting to `unavailable` (`_DEFAULT_ENRICHMENT`, envelope.py:21-29; the closed key stays per Global Constraints)
- Consumes (Plan B Produces): top-level `env["enrichment_reasons"]["requirements"]` carrying a STABLE reason_class declaring "reserved, not yet wired" (Plan B Task "requirements reserved-but-honest")
- Produces: test `test_gv_hon_3_requirements_reserved_but_honest(tmp_path: Path) -> None`

**Steps:**

- [ ] Append after `test_gv_hon_2_...`:

```python
def test_gv_hon_3_requirements_reserved_but_honest(tmp_path: Path) -> None:
    """GV-HON-3 (Plan B): the RESERVED requirements key stays in the frozen vocab but reads as
    reserved-but-honest — a stable reason_class declaring 'reserved, not yet wired', never a
    silent bare 'unavailable'. The vocab key is NOT removed (frozen envelope)."""
    repo = _git_repo(tmp_path)
    with _store(repo) as store:
        repo_id = store.ensure_repo(repo)
        a = _seed_entity(store, repo_id, "python:function:m.py::a", "loomweave:eid:aaaa")
        _add_change(store, repo_id, a, path="m.py")

    env = commands.change_list(repo)
    # The frozen key is still present in the closed vocab.
    assert "requirements" in env["enrichment"]
    assert env["enrichment"]["requirements"] == "unavailable"
    req_reason = env["enrichment_reasons"]["requirements"]
    _assert_reason_triple(req_reason)
    # Reserved-but-honest: a stable class, identical run-to-run, never 'clean'.
    assert req_reason["reason_class"] != "clean"
    env2 = commands.change_list(repo)
    assert env2["enrichment_reasons"]["requirements"] == req_reason
```

- [ ] Run it. Command:

```bash
python -m pytest tests/contracts/test_golden_vectors.py::test_gv_hon_3_requirements_reserved_but_honest -q
```

  Expected failure (today `requirements` defaults to bare `unavailable` in `_DEFAULT_ENRICHMENT`, no `enrichment_reasons`):

```
F                                                                        [100%]
... req_reason = env["enrichment_reasons"]["requirements"]
E   KeyError: 'enrichment_reasons'
1 failed in 0.XXs
```

- [ ] STOP — RED until Plan B. Commit:

```bash
git add tests/contracts/test_golden_vectors.py
git commit -m "test(GV-HON-3): pin requirements reserved-but-honest reason (red until Plan B)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6 — Register the new vectors in the manifest (count reconciliation)

**Files:**
- Modify: `tests/fixtures/contracts/warpline/golden-vectors.json` (the `vectors` array, lines 7-36; the manifest currently holds 13 objects)

**Interfaces:**
- Produces: 5 new manifest objects (`GV-CAP-1`, `GV-CAP-2`, `GV-HON-1`, `GV-HON-2`, `GV-HON-3`), each `{id, seam, tool, assert}`, appended after `GV-LG-3`.

**Steps:**

- [ ] Add the five new vector objects. Open `tests/fixtures/contracts/warpline/golden-vectors.json` and replace the `GV-LG-3` entry (currently lines 34-35) so the array continues with the new entries. The `GV-LG-3` object is:

```json
    {"id": "GV-LG-3", "seam": "all", "tool": "all six",
     "assert": "every response carries meta.local_only true, peer_side_effects []"}
```

  Change it to (add a trailing comma and the five new objects):

```json
    {"id": "GV-LG-3", "seam": "all", "tool": "all six",
     "assert": "every response carries meta.local_only true, peer_side_effects []"},
    {"id": "GV-CAP-1", "seam": "capture-visibility", "tool": "warpline_edge_snapshot_capture",
     "assert": "mid-capture loomweave failure leaves the PRIOR snapshot intact and visible (its edges survive); never a published-but-empty/half-written new row"},
    {"id": "GV-CAP-2", "seam": "capture-visibility", "tool": "warpline_edge_snapshot_capture",
     "assert": "a completed FULL capture publishes a snapshot whose edges are already present; latest_snapshot never resolves a published-but-empty row"},
    {"id": "GV-HON-1", "seam": "honesty", "tool": "warpline_change_list / warpline_edge_snapshot_capture",
     "assert": "sei absence/unavailability carries a {reason_class,cause,fix} triple (never-resolved vs loomweave-unreachable), never a bare vocab value"},
    {"id": "GV-HON-2", "seam": "honesty", "tool": "warpline_entity_timeline_get",
     "assert": "governance == unavailable (no rename-feed transport) carries a {reason_class,cause,fix} triple, not bare vocab"},
    {"id": "GV-HON-3", "seam": "honesty", "tool": "warpline_change_list",
     "assert": "requirements stays in the frozen vocab as reserved-but-honest: a stable reason_class declaring 'reserved, not yet wired', never a silent bare unavailable"}
```

- [ ] Validate the JSON is well-formed and now lists 18 vectors. Command:

```bash
python -c "import json; d=json.load(open('tests/fixtures/contracts/warpline/golden-vectors.json')); print(len(d['vectors']), [v['id'] for v in d['vectors']])"
```

  Expected output:

```
18 ['GV-LW-1', 'GV-LW-2', 'GV-LW-3', 'GV-LW-4', 'GV-LW-5', 'GV-FI-1', 'GV-FI-2', 'GV-FI-3', 'GV-WL-1', 'GV-WL-2', 'GV-WL-3', 'GV-LG-1', 'GV-LG-2', 'GV-LG-3', 'GV-CAP-1', 'GV-CAP-2', 'GV-HON-1', 'GV-HON-2', 'GV-HON-3']
```

- [ ] Commit:

```bash
git add tests/fixtures/contracts/warpline/golden-vectors.json
git commit -m "fixture(golden-vectors): register GV-CAP-* and GV-HON-* vectors (13 -> 18 manifest)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7 — Make the manifest's `executable` path portable

**Files:**
- Modify: `tests/fixtures/contracts/warpline/golden-vectors.json` (the `executable` key, line 6)

**Interfaces:**
- Produces: a relocatable executable descriptor the hub can resolve without assuming warpline's tree layout. Replaces the single repo-relative string with a `{ "module": ..., "fixture_root_relative_to_repo": ..., "note": ... }` object plus a `schema_version` note.

**Steps:**

- [ ] Replace line 6. The current line is:

```json
  "executable": "tests/contracts/test_golden_vectors.py",
```

  Replace it with a portable descriptor (importable module path + a note that the hub runs the Python executable with the `warpline` package importable, not a JSON-only replay):

```json
  "executable": {
    "kind": "pytest-module",
    "module": "tests.contracts.test_golden_vectors",
    "import_requires": "warpline",
    "note": "These vectors are a Python executable, not a data-driven replay. The hub must run this pytest module with the warpline package importable on sys.path; the JSON below is the vector index, the assertions live in the module. Resolve the module relative to wherever this fixture tree is mounted."
  },
```

- [ ] Validate JSON well-formed and the key is now an object. Command:

```bash
python -c "import json; d=json.load(open('tests/fixtures/contracts/warpline/golden-vectors.json')); e=d['executable']; print(type(e).__name__, e['module'], e['import_requires'])"
```

  Expected output:

```
dict tests.contracts.test_golden_vectors warpline
```

- [ ] Confirm no contract test reads `executable` as a string (grep — there is none today, this guards against regression):

```bash
grep -rn "executable" tests/contracts/ || echo "no test reads executable: safe to change shape"
```

  Expected output:

```
no test reads executable: safe to change shape
```

- [ ] Commit:

```bash
git add tests/fixtures/contracts/warpline/golden-vectors.json
git commit -m "fixture(golden-vectors): make executable descriptor portable (no warpline-tree-relative path)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8 — Anchor the contract-test fixture root to the test file (kill cwd-relative path)

**Files:**
- Modify: `tests/contracts/test_warpline_contract_fixtures.py` (line 8: `FIXTURES = Path("tests/fixtures/contracts/warpline")`)

**Interfaces:**
- Consumes: nothing new.
- Produces: `FIXTURES` anchored to `Path(__file__)` so the suite locates the fixture regardless of the process cwd (the hub will not run from warpline's repo root).

**Steps:**

- [ ] Write a failing test that proves the path resolves independent of cwd. Append this test to the END of `tests/contracts/test_warpline_contract_fixtures.py` (after `test_reverify_response_fixture_carries_honesty_fields`, line 94):

```python
def test_fixtures_root_resolves_independent_of_cwd(tmp_path: Path, monkeypatch) -> None:
    """The fixture root must resolve from the test file location, not the process cwd, so the
    federation hub can run this suite from any working directory (portability)."""
    monkeypatch.chdir(tmp_path)
    assert (FIXTURES / "golden-vectors.json").is_file()
    assert (FIXTURES / "mcp-tool-inventory.json").is_file()
```

  This requires a `tmp_path`/`monkeypatch` import-free signature (both are pytest fixtures); no new imports needed since `Path` is already imported (line 4).

- [ ] Run it and see it fail (cwd-relative `FIXTURES` cannot find the file from `tmp_path`):

```bash
python -m pytest "tests/contracts/test_warpline_contract_fixtures.py::test_fixtures_root_resolves_independent_of_cwd" -q
```

  Expected failure:

```
F                                                                        [100%]
... assert (FIXTURES / "golden-vectors.json").is_file()
E   assert False
1 failed in 0.XXs
```

- [ ] Make it pass with the minimal change. Edit line 8 of `tests/contracts/test_warpline_contract_fixtures.py`. Current:

```python
FIXTURES = Path("tests/fixtures/contracts/warpline")
```

  Replace with (anchor to the test file: `tests/contracts/<file>` → repo-root → `tests/fixtures/contracts/warpline`):

```python
FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "contracts" / "warpline"
```

- [ ] Run the new test and the full contract-fixtures module — both must be green:

```bash
python -m pytest tests/contracts/test_warpline_contract_fixtures.py -q
```

  Expected output (3 existing tests + the new one):

```
....                                                                     [100%]
4 passed in 0.XXs
```

- [ ] Confirm the existing frozen-schema assertions still hold (no `.draft.` strings; this is the freeze-attestation invariant the handover cites). Command:

```bash
python -m pytest "tests/contracts/test_warpline_contract_fixtures.py::test_mcp_tool_inventory_is_agent_first_and_enrich_only" -q
```

  Expected: `1 passed`.

- [ ] Commit:

```bash
git add tests/contracts/test_warpline_contract_fixtures.py
git commit -m "test(contracts): anchor FIXTURES root to test file for cwd-independent (portable) load

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9 — Verify the full suite + gates; confirm CAP/HON status against A+B

**Files:** none (verification only).

**Interfaces:**
- Consumes: the full pytest suite, ruff, pyright, and the gate commands from Global Constraints.
- Produces: a recorded, evidenced pass/fail status that Task 10's handover doc quotes verbatim. The handover's "local pass" claim is gated on this run.

**Steps:**

- [ ] Run ruff and pyright on the touched files. Command:

```bash
ruff check tests/contracts/test_golden_vectors.py tests/contracts/test_warpline_contract_fixtures.py && pyright tests/contracts/test_golden_vectors.py tests/contracts/test_warpline_contract_fixtures.py
```

  Expected: ruff `All checks passed!`; pyright `0 errors, 0 warnings, 0 informations`. Fix any lint/type finding at the test source before continuing.

- [ ] Run the whole golden-vector + contract suite and capture which CAP/HON vectors are red. Command:

```bash
python -m pytest tests/contracts/ -q
```

  Expected on THIS branch (Plan A/B not yet merged): the 13 legacy GV vectors and the contract-fixtures tests PASS; `GV-CAP-1`, `GV-HON-1`, `GV-HON-2`, `GV-HON-3` FAIL (red-by-design). Record the exact failing ids — they are the proof the vectors discriminate. Example tail:

```
... 4 failed, 1X passed in X.XXs
FAILED tests/contracts/test_golden_vectors.py::test_gv_cap_1_mid_capture_failure_leaves_prior_snapshot_intact
FAILED tests/contracts/test_golden_vectors.py::test_gv_hon_1_sei_absence_carries_reason_triple
FAILED tests/contracts/test_golden_vectors.py::test_gv_hon_2_governance_unavailable_carries_reason_triple
FAILED tests/contracts/test_golden_vectors.py::test_gv_hon_3_requirements_reserved_but_honest
```

- [ ] DECISION GATE. If Plan A AND Plan B are merged into this branch, re-run the command above; all CAP/HON vectors MUST go green. If any are still red after A+B, STOP — the gap is in A/B, not this plan; surface it (do not patch around it). The handover doc (Task 10) may claim "local pass" ONLY when this command is fully green. If A/B are not yet merged, proceed to Task 10 but mark the status as "vectors authored, green pending A+B merge" (the doc has an explicit conditional field for this).

- [ ] Run the federation gates named in Global Constraints. Commands:

```bash
warpline dogfood-eval && warpline mcp-smoke
```

  Expected: both exit 0. (These exercise the live MCP surface and the dogfood loop; the new test files do not change the runtime surface, so they must stay green.)

- [ ] No commit (verification-only task). Proceed to Task 10.

---

## Task 10 — Author the hub handover document (draft package)

**Files:**
- Create: `docs/integration/2026-06-22-warpline-5th-producer-handover.md`

**Interfaces:**
- Consumes (cited verbatim, do not invent): the frozen vocabularies and ids established above and in current code:
  - 6 endorsed/shim MCP name pairs + their `warpline.<contract>.v1` data schemas (`mcp-tool-inventory.json`, lines 7-218): `warpline_impact_radius_get`/`blast_radius` (`warpline.impact_radius.v1`), `warpline_edge_snapshot_capture`/`capture_snapshot` (`warpline.edge_snapshot.v1`, the ONLY `mutates:true`), `warpline_change_list`/`changed` (`warpline.change_list.v1`), `warpline_entity_churn_count_get`/`churn` (`warpline.entity_churn_count.v1`), `warpline_reverify_worklist_get`/`reverify` (`warpline.reverify_worklist.v1`), `warpline_entity_timeline_get`/`timeline` (`warpline.entity_timeline.v1`).
  - 11 error codes + 3 retryability values (`errors.py:8-23`); error schema URI `warpline.error.v1` (`errors.py:59`).
  - 6 closed enrichment keys + value sets (`envelope.py:10-17`); the canonical 11 reason classes (`listing.py:17-31`).
  - The OD-5 §8 resolution quote (`~/weft/pm/2026-06-13-warpline-interface-lock.md`).
  - The proven-vs-unproven member statuses (`golden-vectors.json` `reserved_shape_inbound`; `federation.py:156-219` disabled-by-default wardline/legis transports).
- Produces: the complete handover markdown below. The doc FREEZES NOTHING and creates no hub/sibling work (authority boundary).

**Steps:**

- [ ] Create `docs/integration/2026-06-22-warpline-5th-producer-handover.md` with EXACTLY this content (fill the one conditional status field per the Task 9 decision gate):

```markdown
# Warpline 5th-Producer Conformance — Hub Handover (DRAFT package)

Date: 2026-06-22
Status: DRAFT — handover package for the federation hub owner. This document
freezes nothing and creates no hub or sibling work. It describes a package the
owner may, on their signal, wire into the GS-7 oracle and freeze. (Authority
boundary: warpline's grant is repo-local; GS-7 inclusion and the glossary freeze
are the owner's act.)

Producer: warpline (admitted 2026-06-13 as the federation's 5th member, PDR-0022).
Branch of record: plan/spine-hardening.

## 1. What 5th-producer conformance is

Warpline contributes a golden-vector suite to the four-member GS-7 conformance
oracle as a fifth producer. The suite is two artifacts:

- `tests/fixtures/contracts/warpline/golden-vectors.json` — the vector **manifest**
  (an index of `{id, seam, tool, assert}` objects). It is NOT a data-driven replay
  oracle; the `assert` strings are prose.
- `tests/contracts/test_golden_vectors.py` — the **executable**. It builds real-git
  fixtures + stubbed loomweave clients and calls `warpline.commands` /
  `warpline.snapshot` directly. The live assertions are here.

### Vector inventory (count: 13 legacy + 5 new = 18 manifest objects)

The interface-lock and the test module docstring say "14 golden vectors"; that is
doctrine that counts `GV-LG-3` ("all six tools carry local-only + no side effects")
as spanning more than one logical check. The JSON manifest enumerates 13 legacy
objects. This package ADDS 5:

- Legacy (frozen 2026-06-13): `GV-LW-1..5`, `GV-FI-1..3`, `GV-WL-1..3`, `GV-LG-1..3`.
- New, this package:
  - `GV-CAP-1` — a mid-capture loomweave failure leaves the PRIOR snapshot intact
    and visible (its edges survive); never a published-but-empty/half-written row.
    Pins Plan A's visibility invariant.
  - `GV-CAP-2` — a completed FULL capture publishes a snapshot whose edges are
    already present; `latest_snapshot()` never resolves a published-but-empty row.
  - `GV-HON-1` — `sei` absence/unavailability carries a `{reason_class, cause, fix}`
    triple distinguishing never-resolved from loomweave-unreachable.
  - `GV-HON-2` — `entity_timeline` governance == `unavailable` carries a triple, not
    bare vocab.
  - `GV-HON-3` — `requirements` stays in the frozen vocab as reserved-but-honest: a
    stable reason_class declaring "reserved, not yet wired", never a silent bare
    `unavailable`.

### The frozen envelope / error contract

- **Success envelope** (`warpline.<contract>.v1`): keys `{schema, ok, query, data,
  warnings, next_actions, enrichment, meta}`. `meta.local_only` is always `true`;
  `meta.peer_side_effects` is always `[]`.
- **Enrichment vocab** (CLOSED, `src/warpline/envelope.py:10-17`): 6 keys —
  `sei` / `work` / `risk` / `governance` / `requirements` ∈ {present, absent,
  unavailable}; `edges` ∈ {present, absent, stale, partial, skipped, unavailable}.
- **Weft-reason triple** (`src/warpline/listing.py`): `{reason_class, cause, fix}`,
  built only via `reason()`. `clean` omits cause/fix; every other class carries
  both. The canonical 11 reason classes: clean, disabled, unresolved_input,
  rejected, dead_path, unreachable, misrouted, error, scheme_mismatch, stale,
  partial.
- **Error contract** (`warpline.error.v1`, `src/warpline/errors.py`): 11 closed
  error codes — missing_required_field, invalid_repo, invalid_rev_range,
  invalid_entity_ref, invalid_changed_refs, invalid_depth, invalid_filter,
  invalid_sort, peer_unavailable, snapshot_unavailable, internal_error. 3
  retryability values — retry_safe, retry_with_changes, fatal. Additions are a v2
  contract URI, never a mutation of v1.

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
itself. Source: `~/weft/pm/2026-06-13-warpline-interface-lock.md` §8.

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

**Local conformance:** <FILL FROM TASK 9 DECISION GATE — one of:
"PROVEN — all 18 vectors green locally (Plans A and B merged; `pytest tests/contracts/`
fully green on <date/sha>)" OR "VECTORS AUTHORED — GV-CAP-* and GV-HON-* are red by
design pending Plan A (atomic capture) and Plan B (sei/governance/requirements
triples) merge; the 13 legacy vectors + contract-fixtures suite are green.">

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
```

- [ ] Verify the doc references no fabricated symbol. Confirm every MCP name, error code, enrichment key, and reason class in the doc exists in current code:

```bash
python - <<'PY'
import re, pathlib
from warpline.errors import ERROR_CODES, RETRYABILITY
from warpline.envelope import ENRICHMENT_VOCAB
from warpline.listing import REASON_CLASSES
doc = pathlib.Path("docs/integration/2026-06-22-warpline-5th-producer-handover.md").read_text()
for code in ERROR_CODES:
    assert code in doc, f"missing error code {code}"
for rc in REASON_CLASSES:
    assert rc in doc, f"missing reason class {rc}"
for key in ENRICHMENT_VOCAB:
    assert key in doc, f"missing enrichment key {key}"
print("all 11 codes, 11 reason classes, 6 enrichment keys present in handover doc")
PY
```

  Expected output:

```
all 11 codes, 11 reason classes, 6 enrichment keys present in handover doc
```

- [ ] Commit:

```bash
git add docs/integration/2026-06-22-warpline-5th-producer-handover.md
git commit -m "docs(integration): author warpline 5th-producer hub handover (DRAFT package)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 11 — Final gate: portability + suite + handover cross-check

**Files:** none (verification + final commit if anything was missed).

**Interfaces:** consumes the full gate set; produces the green (or conditionally-red-by-design) evidence the capstone exit criterion requires.

**Steps:**

- [ ] Prove the suite is locatable from an arbitrary cwd (the hub-load simulation). Command:

```bash
cd /tmp && python -m pytest "tests/contracts/test_warpline_contract_fixtures.py::test_fixtures_root_resolves_independent_of_cwd" -q
```

  Expected: `1 passed`. (Confirms Task 8's anchoring removed the cwd dependency.)

- [ ] Run the full contracts suite one final time from the repo root and confirm the legacy 13 + contract-fixtures stay green and only the by-design CAP/HON reds remain (or all green if A+B merged). Command:

```bash
python -m pytest tests/contracts/ -q
```

  Expected (A+B not merged): legacy + fixtures green; `GV-CAP-1`, `GV-HON-1`, `GV-HON-2`, `GV-HON-3` red-by-design. (A+B merged): all green.

- [ ] Run ruff/pyright across all touched files one final time:

```bash
ruff check tests/contracts/ && pyright tests/contracts/test_golden_vectors.py tests/contracts/test_warpline_contract_fixtures.py
```

  Expected: ruff `All checks passed!`; pyright `0 errors`.

- [ ] Confirm the handover doc's status field was filled (no literal `<FILL ...>` placeholder remains):

```bash
grep -c "FILL FROM TASK 9" docs/integration/2026-06-22-warpline-5th-producer-handover.md
```

  Expected output:

```
0
```

  If this prints `1`, the status field is still a placeholder — fill it per the Task 9 decision gate and re-commit before declaring done.

- [ ] If any file changed in this task, commit:

```bash
git add -A
git commit -m "chore(conformance): final portability + handover status gate

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Exit criterion (this plan)

Done when ALL hold:
1. `GV-CAP-1`, `GV-CAP-2`, `GV-HON-1`, `GV-HON-2`, `GV-HON-3` exist as tests in
   `tests/contracts/test_golden_vectors.py` and as manifest objects in
   `golden-vectors.json` (18 total).
2. The manifest's `executable` is a relocatable descriptor and the contract test's
   `FIXTURES` root is cwd-independent; the hub-load simulation (Task 11 step 1) passes.
3. `docs/integration/2026-06-22-warpline-5th-producer-handover.md` exists, references
   only real symbols (Task 10 cross-check passes), and its status field is filled.
4. Lint/types green; legacy 13 vectors + contract-fixtures green; the CAP/HON
   vectors are either all green (if Plans A and B are merged) or red-by-design with
   the status field marked accordingly.
```
