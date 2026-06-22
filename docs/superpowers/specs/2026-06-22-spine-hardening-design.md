# Spine Hardening — Correct-by-Construction (Design)

Date: 2026-06-22
Status: approved (brainstorming → ready for writing-plans)
Branch: `harden/spine-correct-by-construction`
Product direction: HARDENING (owner-accepted 2026-06-22) — harden the v1.1 spine to
*earn* the federation admission before climbing the capability ladder. See
`docs/product/roadmap.md` (capability ladder) and the PDR to be recorded at checkpoint.

## Problem

Warpline shipped v1.1 and was admitted as the 5th Weft member (PDR-0022) as a
fast-follow. The snapshot edge-capture path — the spine that makes `blast_radius`
and `reverify` non-empty — shipped with a cluster of correctness defects (tracked
bugs `warpline-2a4ff441b6`, `warpline-afc5fa71c7`, `warpline-479c710389`, and the
now-code-complete `warpline-4db9c30b3b`). All four are instances of **one
structural flaw**: capture writes a snapshot in two steps, leaving a window where a
reader can see a published-but-empty snapshot and orphaning intermediate rows.

A member that emits wrong-but-confident facts is worse than one that emits honest
absence. The product's entire value is *trustworthy temporal facts*, so the spine
must be trustworthy **by construction** and **provably** so — not merely patched.

## Reground corrections (post-authoring, 2026-06-22)

Re-grounding each plan against the current branch corrected several premises in this
spec. The plans carry the corrected understanding; this note keeps the spec honest:

- **The orphan-row / published-empty failures were already neutralized** by commit
  `127c4fd` ("fix: delay full snapshot publication"). `create_edge_snapshot` upserts
  on `UNIQUE(repo_id,commit_sha,source)` (one row, not two), and the FULL flip happens
  after edges commit, so a mid-window reader sees the prior row, or DELTA/0-edges, or
  FULL-with-edges — never a published-empty row. **The genuine open gap is different:**
  capture is still three auto-committed transactions, so the invariant holds only by an
  *emergent* property, and **fail-closed-to-prior-snapshot is violated today** (the
  step-1 upsert degrades the prior FULL row to DELTA and clears its edges before
  Loomweave is queried, so a mid-capture death destroys the last good snapshot). Plan A
  now targets *that* — one `BEGIN IMMEDIATE` capture method that computes completeness
  before mutating any visible row.
- **The honesty triple cannot nest in the closed scalar `enrichment` dict** (it is
  validated value-by-value). Plan B adds a new **top-level `enrichment_reasons`**
  carrier (sibling of `enrichment`), a map of dimension → `{reason_class, cause, fix}`.
  This is an additive envelope evolution — within "refine Warpline-owned pre-admission
  contracts," and itself an entry for the handover's glossary-freeze checklist.
- **No `reserved` reason_class exists**; Plan B reuses the canonical 11
  (`requirements` → `disabled` with reserved-flavored cause/fix), leaving the frozen
  vocab and its guard test untouched.
- **OD-5 is already resolved** (fold into GS-7 as the 5th producer); the owner action
  is launch-runbook *wiring*, not adjudication. The governance line at `commands.py`
  is `:398`, not `:303`. The suite is **13 manifest vectors (14-as-doctrine** — GV-LG-3
  spans six tools).

## Goal & non-goals

**Goal:** make the snapshot spine correct-by-construction, honesty-complete, and
locked behind conformance, then hand the federation hub a package to admit
warpline's golden vectors as the 5th producer.

**Non-goals (and why):**
- The four point-bugs — owned by the in-flight bug agent. This bet *assumes they
  land*, then makes the failure class structurally impossible.
- Actual GS-7 oracle wiring, the OD-5 decision, and the glossary freeze — these are
  hub/sibling territory the authority grant reserves to the owner. This bet
  produces the *handover package*; the owner pushes the button.
- Optimization — changed-set p95 is 48 ms against a 250 ms target; no latency pain.
- Any Rung-2+ enhancement — sequenced *after* the spine is trustworthy.

## Decisions (from brainstorming)

1. **Re-architect capture** (not patch-on-top) — make the publish-before-edges /
   orphan-row class impossible, not just absent today.
2. **Autonomous half + escalation package** — the bet completes everything within
   warpline's authority and produces a hub handover document; GS-7 inclusion +
   glossary freeze are flagged as the owner's escalation.
3. **Hub handover document is a first-class deliverable** (owner request).
4. **Vectors-first sequencing** — the golden vector that expresses each invariant is
   written first (fails), then the implementation makes it green. The test that
   locks the invariant *is* the deliverable.
5. **3 implementation plans, cut by dependency seam** (not by workstream).

## Workstreams

### WS1 — Capture correct-by-construction

**Invariant:** *no `edge_snapshots` row is ever visible to a reader until all of its
edges are committed.*

**Current (broken) shape** — `src/warpline/snapshot.py`:
- `:94` mints an intermediate `DELTA` row and `clear_snapshot_edges()`s it,
- appends edges,
- `:127` mints a *second* row flipped to `FULL`.

Because `store.latest_snapshot()` (`store.py:1470`) selects `id DESC`, a reader in
the window between the two steps can pick a published-but-empty/partial snapshot;
on a first capture the intermediate row is left orphaned (zero edges, stale id).

**Target shape:** one atomic capture transaction.
- Stage edges, compute completeness (`FULL`/`DELTA`/`SKIPPED`) **before** any
  visible row exists.
- Insert the `edge_snapshots` row **last**, inside a single `BEGIN IMMEDIATE` …
  `COMMIT`, so `latest_snapshot()` can never select a row whose edges aren't present.
- No intermediate row, no `clear_snapshot_edges` dance, no orphan.

**Surface:** store-layer change (atomic capture semantics in `store.py` +
`snapshot.py`). **Output-shape-preserving** — the response envelope is identical;
only edge-visibility *timing* and row *lifecycle* change.

**Fail-closed:** a mid-capture Loomweave failure or `max_entities` cap leaves the
*prior* snapshot intact and visible (never a half-written new one) and degrades to
`DELTA`/`SKIPPED` honestly.

### WS2 — Honesty completeness

Every absence must read as *explained* absence — the `weft-reason` triple
(`cause + reason_class + fix`) on every dimension. The audit found three gaps:

1. **`sei` is vocab-only.** `sei: absent`/`unavailable` carry no triple explaining
   *why* (never-resolved vs Loomweave-unreachable). Add a `sei_warnings()` reason
   path mirroring `completeness_warnings()`/`edges`. Touches every tool that emits
   `sei` — confirm the exact set during planning (`change_list`, `entity_timeline`,
   `entity_churn_count`, `edge_snapshot_capture`, and any other; note `impact_radius`
   emits only `edges`, not `sei`).
2. **`governance` on `entity_timeline`** (`commands.py:303`) — emit the triple when
   `unavailable` (no rename-feed transport), not a bare vocab value.
3. **`requirements` is RESERVED-but-inert.** Resolve it as **reserved-but-honest**:
   emit a stable `reason_class` declaring "reserved, not yet wired" rather than
   silently defaulting to `unavailable`. Removing the key would edit a frozen
   envelope (a contract change) — document, do not mutate.

**Surface:** additive reason plumbing in `envelope.py` / `_enrichment.py` /
`federation.py` / `commands.py`. Low-risk; no output keys removed.

### WS3 — Conformance + hub handover

- **Extend the 14 golden vectors** with new vectors pinning WS1's visibility
  invariant (a mid-capture read never sees a published-but-empty snapshot) and WS2's
  triple-on-absence. Vectors-first: these fail before WS1/WS2 land.
- **Portable fixture:** make `tests/fixtures/contracts/warpline/golden-vectors.json`
  relocatable — no warpline-local path assumptions — so the hub can load it verbatim.
- **Hub handover document** — `docs/integration/2026-06-22-warpline-5th-producer-handover.md`:
  - *What 5th-producer conformance is:* the 14+N vectors, the frozen
    envelope/error contract, endorsed MCP names + shims.
  - *How to wire it into GS-7 CI:* where the portable fixture lives, the executable
    entry point (`tests/contracts/test_golden_vectors.py`), the producer-registration
    shape the four-member oracle expects.
  - *The decision the owner is waiting on:* OD-5 (fold into the four-member gate as a
    5th producer vs a separate warpline gate), quoted from
    `~/weft/pm/2026-06-13-warpline-interface-lock.md`.
  - *Glossary-freeze checklist:* the exact MCP names, error codes, enrichment vocab,
    and schema URIs that move draft→frozen on the owner's signal.
  - *Proven vs unproven:* local pass status; the sibling-consumption gaps
    (Wardline/Legis enrich-only) that remain post-admission.

## Architecture / isolation

| Unit | Does | Depends on | Changed by |
|---|---|---|---|
| `store.py` capture txn | Atomically stage edges + insert snapshot row | SQLite, migration runner | WS1 |
| `snapshot.py` | Orchestrate Loomweave neighborhood reads → edges | store, Loomweave client | WS1 |
| `_enrichment.py` / `envelope.py` | Map state → enrichment vocab + reason triple | closed vocab | WS2 |
| `federation.py` | Per-member weft-reason triples | `listing.reason()` | WS2 (sei/gov gaps) |
| `tests/contracts/` golden vectors | Executable invariant spec | tool surface | WS3 (+ opens WS1/WS2) |
| handover doc | Hub admission package | frozen contract, vectors | WS3 |

## Testing

- Repo posture: real-git fixtures + stubbed Loomweave clients (per
  `tests/test_snapshots.py`), plus the golden-vector executor.
- WS1 new test: kill the client mid-loop → assert the prior snapshot still reads and
  no partial/orphan row appears; assert a mid-capture reader never sees the new row
  until edges are committed.
- WS2 new tests: each of the 5 `sei`-emitting tools carries a triple on
  absence/unavailability; `entity_timeline` governance triple; `requirements`
  reserved-but-honest reason.
- Gate stays green: `warpline dogfood-eval`, `warpline mcp-smoke`, lint/types/tests,
  member-diff guard. New vectors join the contract suite.

## Exit criterion (bounded — no hardening treadmill)

Done when **all three** hold:
1. Capture's visibility invariant holds and is locked by a golden vector.
2. All six enrichment dimensions are triple-complete on absence.
3. The portable vector package + hub handover document exist and CI is green.

At that point the spine is *provably* member-grade within warpline's authority and
the bet **stops**; GS-7 inclusion is handed to the owner.

**Reversal trigger:** pivot to enhancement (Rung 2 verification-freshness) once the
hub accepts the package, or sooner if the owner judges the spine trustworthy enough.

## Authority-boundary check

WS1–WS3 are reversible and repo-local — within the grant. The handover document is a
draft package, not an act: it creates no hub/sibling work and freezes nothing until
the owner acts on it. ✅

## Implementation plans (3, by dependency seam)

| Plan | Contains | Risk | Depends on |
|---|---|---|---|
| **A — Capture correct-by-construction** | WS1 + its visibility-invariant vectors | High | bug agent's point-fixes landed |
| **B — Honesty completeness** | WS2 + its triple-on-absence vectors | Low | — (parallel with A) |
| **C — Conformance package + hub handover** | portable fixture, extended vector suite, handover doc | Low | A **and** B green |

A and B run in parallel; C is the gated capstone producing the hub handover document.
