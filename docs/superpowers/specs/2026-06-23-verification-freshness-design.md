# Verification-Freshness (Rung 2, Track B) — Design

Date: 2026-06-23
Status: approved (brainstorming → ready for writing-plans)
Branch: plan/spine-hardening (built atop the merged spine-hardening bet)
Product direction: Rung 2 diagnostic tier — the one diagnostic capability not yet
landed (co-change graph, risk/governance enrichment, and the temporal COP already
shipped). The post-hardening pivot named by the hardening bet's reversal trigger.

## Problem

Warpline's reverify worklist answers *"what changed since HEAD~1"* — a purely
git-history question. It has **no notion of verification**: there is no per-entity
`last_verified`, no "proven-good" marker, nothing time-aware about trust. An agent
re-verifying after a change cannot ask the better question — *"what changed since it
was last proven good, and how stale is that trust?"*

The store today tracks only change (`change_events.changed_at`, the Rung 1b
`detected_at` anchor) and presence (`entity_keys.first_seen_commit`/`last_seen_commit`).
There is no verification concept anywhere in the codebase.

## Goal & non-goals

**Goal:** give warpline a `last_verified` axis sourced from **warpline's own gate
result**, so the reverify worklist surfaces a `fresh / stale / unverified`
verification state plus a trust-decay signal per item — advisory, enrich-only, never
gating.

**Non-goals (and why):**

- **Sibling-sourced verification** (wardline-resolved findings, filigree issue
  closure, legis attestation) — each needs a *sibling-side surface that does not
  exist today* (wardline `dossier.trust` exposes only `active_findings`, no RESOLVED
  state/timestamp; filigree `issue.closed_at` unconfirmed; legis has no per-SEI
  attestation read transport). Those are owner/sibling escalations. They stay
  honest-absent RESERVED extension points.
- **Promoting `verification` into the FROZEN closed envelope enrichment vocab** (the
  6 keys: sei/edges/work/risk/governance/requirements) — that is a contract/glossary
  evolution and the owner's escalation. v1 carries verification as a reverify-item
  field instead, leaving the just-hardened contract untouched.
- **Gating / filtering** — warpline never gates (hard anti-goal). Verification is
  advisory: it annotates and may re-sort the worklist, but never removes an item.

## Decisions (from brainstorming)

1. **Source = warpline's own gate result.** An external gate (CI / a test-runner
   wrapper / the human) records a pass via a new verb. The only source fully within
   warpline's authority; no sibling dependency.
2. **Data model A — per-commit `verification_events`.** A gate run is a *per-commit*
   fact ("gate K passed as-of commit C"), one row per run, mirroring `change_events`.
   Freshness is computed by git reachability, not by stamping every entity
   (rejected B's denormalized columns and C's per-entity events — both cause
   write-amplification for a whole-repo gate and lose event history).
3. **Verification rides as a reverify-item field**, not a frozen-envelope dimension.
4. **Advisory trust-decay sort is in v1** (stale-of-trust first); items are never
   removed.

## Components

### 1. Store — v4 migration + accessors (`src/warpline/store.py`)

New table, following the v2/v3 migration pattern (O(1), NULLable-friendly,
`HIGHEST_KNOWN_VERSION → 4`, presence-floor check for `verification_events`):

```sql
CREATE TABLE IF NOT EXISTS verification_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  repo_id TEXT NOT NULL,
  commit_sha TEXT NOT NULL,          -- resolved object SHA (never a symbolic ref)
  kind TEXT NOT NULL,                -- e.g. 'test_pass', 'ci_pass', 'gate_pass'
  verified_at TEXT NOT NULL,         -- ISO-8601 UTC
  actor TEXT,                        -- who/what verified (CI id, reviewer, automation)
  source TEXT NOT NULL DEFAULT 'warpline',  -- provenance; 'warpline' for self-gate
  UNIQUE(repo_id, commit_sha, kind, source)
);
```

Accessors: `record_verification_event(*, repo_id, commit_sha, kind, verified_at, actor, source) -> int`
and `verification_events_for_repo(repo_id) -> list[dict]` (ordered by `verified_at`).

### 2. Write path — `verify-record` verb (CLI + MCP)

A new verb the external gate calls after passing: `warpline verify-record --commit
HEAD --kind test_pass [--actor <id>]`, and MCP tool `warpline_verification_record`
(the 2nd mutating tool besides `edge_snapshot_capture`; `mutates: true`,
`local_only: true`, writes only `.weft/warpline/`). It resolves the commit ref to an
object SHA (reuse the Plan A `git rev-parse --verify` discipline — never store a
symbolic ref), then inserts the event. Returns the standard envelope. Bad ref →
structured `invalid_rev_range` / `invalid_entity_ref` error.

### 3. Freshness compute — `src/warpline/verification.py` (pure)

Mirrors `_enrichment.py` (pure, enrich-only, no I/O beyond the git-reachability
helper passed in). For one entity:

```python
def compose_verification_freshness(
    entity_changes: list[dict],        # the entity's change_events (with commit_sha)
    verification_events: list[dict],   # repo verification events
    covers: Callable[[str, str], bool],# covers(verified_commit, change_commit): is change reachable from verified?
) -> dict:  # {"state": "fresh"|"stale"|"unverified"|"unavailable",
            #  "last_verified_at": str|None, "last_verified_commit": str|None,
            #  "decay": {"commits_behind": int|None}, "reason": <weft-reason triple>}
    ...
```

Semantics:

- **`fresh`** — the entity's LATEST change commit is *covered* by some verification
  event (a gate run at a commit `V` such that the change commit is an
  ancestor-or-equal of `V` — the gate ran at or after the change landed).
- **`stale`** — the entity has at least one covering verification event, but its
  latest change is NOT covered (it changed since it was last proven good).
- **`unverified`** — no verification event covers any of the entity's changes (e.g.
  no gate has been recorded, or none reachable).
- **`unavailable`** — git reachability could not be computed (shallow clone, missing
  commit). Fail-soft, never a crash.

`decay.commits_behind` = number of commits between the last covering verification
commit and the entity's latest change (parallels the snapshot `commits_behind`).

Every non-`fresh` state carries a weft-reason triple (`cause + reason_class + fix`)
via `listing.reason()`; `fresh` is `clean`. Absence never reads as verified.

### 4. Reverify integration (`src/warpline/reverify.py`, `src/warpline/commands.py`)

- Each worklist item gains a `verification` block (the dict above), computed
  alongside the existing per-item enrichment. This is the **reverify worklist item
  schema** — distinct from the frozen envelope `enrichment` closed vocab, which is
  NOT touched.
- The reverify `data` block gains a `verification_summary`
  (`{fresh, stale, unverified, unavailable}` counts + whether any local source is
  configured).
- **Advisory sort:** within the existing ordering (by depth), items are tie-broken /
  re-ordered so stale-of-trust surfaces first — but every affected item remains
  present. No item is ever filtered out.
- Always-on (no opt-in flag); verification is warpline-local. If no verification
  events exist, every item reads `unverified` with a reason — honest, never silent.

### 5. Honesty

Verification follows the enrich-only doctrine: advisory, never gates; every absence
is explained (`unverified`/`unavailable` carry triples); sibling verification sources
(wardline/filigree/legis) remain RESERVED with honest `disabled`/`unavailable`
reasons until those surfaces exist. `meta.local_only: true` / `peer_side_effects: []`
preserved.

## Data flow

- **Write:** external gate passes → `warpline verify-record --commit HEAD --kind
  test_pass` → resolve object SHA → insert `verification_events` row.
- **Read (reverify):** for each affected entity, join its last-change commit against
  `verification_events` via git reachability → freshness block → attach to the item
  + roll up `verification_summary` + advisory-sort.

## Error handling

- `verify-record` on an unresolvable commit ref → structured `invalid_rev_range` /
  `invalid_entity_ref`; no row written.
- Freshness compute is fail-soft: reachability failure → `unavailable` + reason.
- Zero verification events → all items `unverified` + reason (never silently fresh).

## Testing

- v4 migration test (table created, `user_version`/presence-floor bump to 4,
  idempotent re-open).
- `verify-record` verb test: records an event; proves a symbolic ref (`HEAD`) is
  stored as the resolved object SHA (the Plan A lesson); bad ref → structured error.
- `compose_verification_freshness` unit tests: `fresh` (change covered by a later
  gate), `stale` (change after last covering gate), `unverified` (no covering gate),
  `unavailable` (reachability fails). Each asserts the weft-reason triple shape.
- Reverify integration test: worklist items carry the `verification` block; the
  `verification_summary` rolls up; **no affected item is filtered out** (advisory
  only); stale-of-trust sorts first.
- Golden vector `GV-VF-1`: locks the `fresh/stale/unverified` semantics and the
  unverified-when-no-source honesty (and the never-filter invariant).
- Gates: ruff, mypy (`uv run mypy src/warpline`), pytest, `warpline dogfood-eval`,
  `warpline mcp-smoke` (the new mutating tool appears in `tools/list` with correct
  metadata), member-diff guard.

## Exit criterion (bounded)

Done when: `verify-record` writes verification events; the reverify worklist carries
an honest `fresh/stale/unverified` verification block + trust-decay per item,
advisory-sorted, **never filtering**; locked by `GV-VF-1`; all gates green. Sibling
verification sources remain honest-absent RESERVED. The bet **stops** there.

**Reversal trigger:** reopen if the local-gate verification signal proves not useful
in practice on a real repo (e.g. nobody records gate passes, so everything reads
`unverified` and the axis adds noise not signal), or if a sibling ships a richer
verification surface that should supersede the local source.

## Authority-boundary check

All of v1 is reversible and repo-local — within the grant. The new mutating verb
writes only `.weft/warpline/`. Promoting `verification` to the frozen envelope vocab,
and any sibling-surface dependency, are explicitly OUT and flagged as escalations. ✅

## Implementation plan shape (for writing-plans)

Vectors-first, TDD. Likely task seams:

1. v4 `verification_events` schema + accessors (store).
2. `verify-record` CLI + MCP verb (ref-resolution, errors, tool metadata).
3. `verification.py` pure freshness compute (fresh/stale/unverified/unavailable +
   reason triples) — vectors-first unit tests.
4. Reverify integration: per-item `verification` block + `verification_summary` +
   advisory sort (never filter).
5. Golden vector `GV-VF-1` + honesty lock.
6. Gate sweep.
