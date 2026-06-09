# NFR Mapping — which component is load-bearing for which NFR

Components are defined in `09-component-specifications.md`.

| NFR | Load-bearing component(s) | How the load lands |
|-----|---------------------------|--------------------|
| NFR-01 (query latency) | Propagation Engine; Temporal Store | traversal must run on pre-built edge snapshots + indexed history, never recompute the graph per query |
| NFR-02a (backfill) | Ingest — History Walker | single-pass git-log walk; per-commit work bounded; resumable on interrupt |
| NFR-02b (incremental) | Ingest — Hook Adapter | post-commit path does the minimum durable append, defers graph snapshotting to a lazy/async step |
| NFR-03 (local-first) | all; Query Surfaces | CLI/MCP operate directly on the local store; no network calls anywhere in core flows |
| NFR-04 (enrich-only) | Identity Resolver; Ingest — Catalog Reader | SEI keying is an *upgrade path* over locator keying, applied when a catalog is readable; both ingest and query produce coherent results with the resolver in locator-only mode |
| NFR-05 (tree cleanliness) | Temporal Store | store lives outside the analyzed repo's working tree (ADR-0004 records placement); no scratch files in-repo |
| NFR-06 (false negatives) | Propagation Engine; Snapshot Differ | recall depends on edge-snapshot freshness + edge-kind coverage; engine must stamp staleness on every answer so a thin snapshot is visible, not silent |
