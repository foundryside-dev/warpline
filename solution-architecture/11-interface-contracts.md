# Interface Contracts

Prose contracts (pre-spike; a machine-readable MCP tool schema + CLI `--json`
schema freeze AFTER the spike settles shapes — freezing wire shapes before the
go/no-go would repeat the exact mistake the launch is busy paying down).
Field names are provisional until glossary clearance (CON-ORG-03 / D-09).

Conventions, all operations: read-only against the analyzed repo; errors are
structured `{error, code, details?}` switched on `code` (suite convention);
sibling absence yields degraded-but-coherent results plus an explicit
`enrichment: {sei: present|absent, edges: present|absent|stale}` block — never
an error (NFR-04).

## Q1 — changed-set (FR-01)
- **Op:** `changed(rev_range | diff)`
- **In:** commit sha, range, or unified diff; optional `key_mode: sei|locator|auto`
- **Out:** list of `{entity_key, change_kind, actor, at, commit}` + enrichment block
- **Errors:** `BAD_REVISION`, `NOT_INGESTED` (with backfill hint)
- **Idempotent:** yes (pure read)

## Q2 — timeline (FR-02)
- **Op:** `timeline(entity)`
- **In:** SEI or locator; optional `since`, `until`, `limit`
- **Out:** ordered change events with provenance; key-upgrade lineage included
- **Errors:** `UNKNOWN_ENTITY` (with nearest-locator suggestions)
- **Idempotent:** yes

## Q3 — blast radius (FR-03)
- **Op:** `blast_radius(changed_set | rev_range, depth=2, as_of?)`
- **Out:** `{changed: [...], affected: [{entity_key, depth, via_edges}], staleness: {snapshot_commit, commits_behind}, completeness}` — staleness and completeness are MANDATORY in every answer (NFR-06: a thin answer must look thin)
- **Errors:** `NO_SNAPSHOT` (solo mode / loomweave never read — returns changed-set only, plus the flag, NOT an error exit)
- **Idempotent:** yes

## Q4 — re-verify worklist (FR-04)
- **Op:** `reverify(rev_range, format: json|md)`
- **Out:** blast-radius result rendered as a checklist: per affected entity — why (edge path), suggested verification (tests touching it, where derivable from git)
- **Idempotent:** yes

## I1 — backfill (FR-05)
- **Op:** `backfill(since?)` — resumable; re-running is a no-op over already-ingested commits
- **Idempotent:** yes (append-only with commit-sha dedup)

## I2 — hook ingest (FR-06)
- **Op:** `ingest-commit <sha>` (installed as git post-commit hook by `heddle init`)
- **Contract:** synchronous path ≤ NFR-02b budget; edge snapshotting deferred to next query or explicit `snapshot` verb; MUST exit 0 even on internal failure (a broken hook must never block a commit) — failures land in the store's own health log, surfaced on next query
- **Idempotent:** yes

## Versioning stance
Single `heddle_schema_version` in the store + surfaced on every MCP/CLI
response. Pre-1.0: schema may break freely (it is a spike). Post-admission:
follows whatever wire-freeze discipline the federation's conformance oracle
(GS-7 line) establishes — Heddle would enter the oracle corpus before its
first frozen release, not after (lesson of the current launch).
