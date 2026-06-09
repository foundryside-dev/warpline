# NFR Specification

> All targets are falsifiable-by-shape PLACEHOLDERS pending spike baselining —
> set against own-use scale (single developer, agent fleet, repos ≤ ~200k LOC,
> ≤ ~20k commits). The spike's measurement harness produces the real baselines;
> a target without a measurement method below is not accepted into this file.

| ID | Dimension | Target (placeholder) | Measurement method | Driver |
|----|-----------|----------------------|--------------------|--------|
| NFR-01 | Propagation-query latency | P95 ≤ 2 s for a blast-radius query at depth ≤ 3 on a 100k-LOC / 10k-commit repo | timed harness over the spike corpus (the weft member repos themselves) | agents ask this every session; slower than grep loses the grep test |
| NFR-02a | Backfill ingest | full-history cold start ≤ 5 min on 10k commits | timed cold-start run per spike repo | cold start on existing repos is the adoption path (FR-05) |
| NFR-02b | Incremental ingest | post-commit hook overhead ≤ 1 s P95 | hook timing wrapper over a working session | a hook that slows commits gets disabled, killing FR-06 |
| NFR-03 | Availability / local-first | 100% of queries answerable offline; no daemon required for core flows | run full query suite with network disabled and no server process | vision anti-goal: no cloud, no weftd |
| NFR-04 | Enrich-only invariant | boots, backfills, and answers all FR-01..05 queries with ZERO siblings installed; sibling absence changes enrichment fields only, never result semantics | CI job on a clean container with git only (the doctrine §5 failure test, mechanized) | doctrine §5; metrics.md guardrail (cross-member hard-blocks ceiling = 0) |
| NFR-05 | Tree cleanliness | 0 working-tree modifications of the analyzed repo at rest | `git status --porcelain` empty after every Heddle operation, asserted in CI | metrics.md guardrail; precedent regression `weft-d822a7de2d` |
| NFR-06 | Propagation false-negative rate | ≤ 5% missed downstream consumers at depth ≤ 2 against a planted-change corpus | lacuna-style planted-defect corpus: plant N changes with known downstream consumers, measure recall | a false negative = an unverified break shipped; false positives merely cost review time |

Explicitly NOT NFR dimensions (rejected at design time):
- **Security posture** — Weft is deconfliction-first; re-derive any security-shaped concern as availability/functional (vision; standing PM ruling).
- **Multi-user / multi-host scale** — out of scope until cross-host federation is real (roadmap Later).
