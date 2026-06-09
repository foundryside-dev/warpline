# Requirements Traceability Matrix

| Req | Satisfied by (component, `09-`) | Design artifacts | Verified by |
|-----|--------------------------------|------------------|-------------|
| FR-01 changed-set | History Walker; Hook Adapter; Identity Resolver; Query Surfaces | `11-` Q1 | spike harness: changed-set vs hand-derived truth on weft repos |
| FR-02 timeline | Temporal Store; Query Surfaces | `10-` CHANGE_EVENT; `11-` Q2 | spike harness: timeline continuity through known renames |
| FR-03 blast radius | Catalog Reader + Snapshot Differ; Propagation Engine | `10-` EDGE_SNAPSHOT; `11-` Q3; ADR-0002 | NFR-06 planted-change corpus (recall) |
| FR-04 re-verify worklist | Propagation Engine; Query Surfaces | `11-` Q4 | dogfood: agent consumes worklist unprompted (grep test) |
| FR-05 backfill | History Walker | `11-` I1 | NFR-02a timed cold start |
| FR-06 hook-fed ingest | Hook Adapter | `11-` I2; ADR-0002 | NFR-02b hook timing; hook-never-blocks-commit test |
| FR-07 solo mode | Identity Resolver; Catalog Reader (clean SKIP) | ADR-0003 | NFR-04 zero-sibling CI job |
| FR-08 CLI + MCP | Query Surfaces | `08-`, `11-` | surface smoke tests |
| NFR-01 query latency | Propagation Engine; Temporal Store | `03-` | timed harness (`02-`) |
| NFR-02a/b ingest cost | History Walker; Hook Adapter | `03-` | timed harness (`02-`) |
| NFR-03 local-first | all; deployment | `13-` | offline run of full query suite |
| NFR-04 enrich-only | Identity Resolver; Catalog Reader | ADR-0003; `03-` | zero-sibling CI job (doctrine §5 test, mechanized) |
| NFR-05 tree cleanliness | Temporal Store placement | ADR-0004 §4; `13-` | `git status --porcelain` assertion in CI |
| NFR-06 false negatives | Propagation Engine; Snapshot Differ | `11-` Q3 staleness contract | planted-change corpus recall |
| CON-TEC-01 SEI frozen | Identity Resolver | ADR-0003 | code review: SEI treated as opaque; no parse/mint |
| CON-TEC-02 no member changes | Ingest design as a whole | ADR-0002; `15-` Phase 0 | review: zero diffs in the four member repos until cutover |
| CON-TEC-03 local-first | deployment | `13-` | offline test (NFR-03) |
| CON-ORG-01 §5/§6 binding | Temporal Store firewall | ADR-0004; `04-` | spike doctrine review (Q1/Q3) + owner §7 ruling |
| CON-ORG-02 admission owner-reserved | — (process) | ADR-0001 | go/no-go report routes to owner; no admission act in-repo |
| CON-ORG-03 name placeholder | — (process) | `06-` D-09 | glossary clearance before any wire freeze |
| CON-ORG-04 hook-fed | Hook Adapter | ADR-0002 | design review (discipline-fed paths rejected) |

**Orphan check (this revision):** no FR/NFR/CON without a component or process
owner; no component in `09-` satisfying zero requirements. The Temporal Store's
firewall duties trace to CON-ORG-01, not to a feature — by design.
