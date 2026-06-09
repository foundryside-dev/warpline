# Component Specifications

All components live in the core library (see `08-`). Format per component:
responsibility (one sentence) · public interface · dependencies · consumed
NFRs (from `03-`) · satisfied requirements.

## Ingest — History Walker
- **Responsibility:** cold-start backfill — walk `git log` once and append a change event per touched entity per commit.
- **Interface:** `backfill(repo, since?) -> IngestReport`
- **Dependencies:** Identity Resolver, Temporal Store, git plumbing
- **NFRs:** NFR-02a (single-pass, resumable), NFR-05
- **Requirements:** FR-05, FR-01 (historic), FR-02 (historic)

## Ingest — Hook Adapter
- **Responsibility:** post-commit entrypoint that appends the new commit's change events with minimum synchronous work.
- **Interface:** `ingest_commit(repo, sha) -> IngestReport` (invoked by the installed git hook via the CLI)
- **Dependencies:** Identity Resolver, Temporal Store
- **NFRs:** NFR-02b (defer snapshotting to lazy step), NFR-05
- **Requirements:** FR-06, CON-ORG-04

## Ingest — Catalog Reader + Snapshot Differ
- **Responsibility:** when a Loomweave surface is readable, capture the entity catalog + structural edges relevant to the ingested commits and store edge snapshots (deltas, not full copies, where possible).
- **Interface:** `snapshot_edges(repo, sha) -> SnapshotReport | SKIPPED(reason)`
- **Dependencies:** Loomweave published read surface (OPTIONAL — returns SKIPPED cleanly when absent), Temporal Store
- **NFRs:** NFR-04 (absence is a clean skip, never an error in core flows), NFR-06 (edge coverage drives recall)
- **Requirements:** FR-03 (edge source), FR-07

## Identity Resolver
- **Responsibility:** key every change event durably — SEI when resolvable against a readable catalog, locator (path + qualname) otherwise — and record locator→SEI upgrades when a catalog appears later, without rewriting history.
- **Interface:** `resolve(repo, path, symbol, sha) -> EntityKey {sei?, locator}` ; `upgrade_keys(repo) -> UpgradeReport`
- **Dependencies:** Loomweave catalog (OPTIONAL), Temporal Store
- **NFRs:** NFR-04 (the load-bearing component for enrich-only: locator mode is first-class, not a fallback error path)
- **Requirements:** FR-01, FR-07, CON-TEC-01 (treats SEI as frozen external contract)

## Propagation Engine
- **Responsibility:** traverse stored edge snapshots from a changed-entity set to the downstream-affected set, stamping every answer with edge-snapshot staleness and traversal depth.
- **Interface:** `blast_radius(repo, changed: [EntityKey], depth, as_of?) -> AffectedSet`
- **Dependencies:** Temporal Store
- **NFRs:** NFR-01 (pre-built snapshots, indexed), NFR-06 (staleness visible, never silent)
- **Requirements:** FR-03, FR-04 (input set)

## Query Surfaces (CLI + MCP)
- **Responsibility:** expose changed-set, timeline, blast-radius, and re-verify-worklist queries to agents and humans; machine-readable output first.
- **Interface:** CLI verbs + MCP tools mirroring `11-interface-contracts.md`
- **Dependencies:** all core components
- **NFRs:** NFR-03 (offline, no daemon)
- **Requirements:** FR-01..FR-04, FR-08

## Temporal Store
- **Responsibility:** own the durable temporal data — change events, edge snapshots, key map — in one SQLite DB per analyzed repo, outside that repo's working tree.
- **Interface:** internal repository API (append-only events; immutable snapshots)
- **Dependencies:** SQLite
- **NFRs:** NFR-05 (placement), NFR-01/02 (indexing), NFR-03
- **Requirements:** FR-02 (timeline), FR-05; CON-ORG-01 (stores ONLY Heddle-authoritative temporal data — the aggregator firewall, ADR-0004)
