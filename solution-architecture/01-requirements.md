# Requirements

## Functional requirements
- FR-01  Given a commit, commit range, or working-tree diff, report which entities changed — keyed on SEI when resolvable, durable locator (path + qualname) otherwise — with actor, timestamp, and change kind.
- FR-02  Answer a per-entity timeline query: every recorded change to entity E across the ingested history, in order, with provenance.
- FR-03  Answer the downstream-propagation query: given a changed-entity set, return the downstream-affected set over snapshotted structural edges (callers/dependents), with traversal depth and a staleness stamp on the edges used.
- FR-04  Render the affected set as a re-verification worklist consumable by an agent (machine-readable first; human-readable secondary).
- FR-05  Backfill from existing git history with no prior Heddle presence in the repo (cold start on any repo).
- FR-06  Ingest incrementally via hooks on commit — hook-fed, never dependent on an agent remembering to log a change (PDR-0013 bar (e)).
- FR-07  Operate in solo mode with only git + the repo present (locator-keyed); upgrade keying to SEI automatically when a Loomweave catalog is readable. Sibling absence degrades enrichment, never semantics.
- FR-08  Expose all queries via CLI and MCP tools (agent-first surfaces, matching suite convention).

## Non-functional requirements
(See `02-nfr-specification.md` for quantified detail.)
- NFR-01  Performance — propagation-query latency
- NFR-02  Performance — ingest cost (backfill + incremental)
- NFR-03  Availability — local-first, offline, no required network or daemon
- NFR-04  Composability — enrich-only invariant, mechanically testable (boots/ingests/answers with zero siblings installed)
- NFR-05  Hygiene — working-tree cleanliness of the analyzed repo (zero dirt at rest)
- NFR-06  Answer quality — bounded false-negative rate on the propagation query (the dangerous direction: a missed downstream consumer means an unverified break)

## Constraints
- CON-TEC-01  The SEI standard (`weft/sei-standard.md`) is LOCKED (2026-06-05). Heddle keys on it as a frozen external contract; no change requests to it. Non-negotiable.
- CON-TEC-02  Zero code changes inside filigree, wardline, legis, or loomweave until the launch cutover (owner directive, 2026-06-10). Heddle consumes published read surfaces only. Time-boxed: lifts at cutover; member-side consumer wiring then proceeds via each member's own tracker.
- CON-TEC-03  Local-first: no cloud dependency, no telemetry-home, fully functional offline (vision anti-goals).
- CON-ORG-01  Federation doctrine §5/§6 are binding: enrich-only composition; no shared runtime/store/broker; Heddle must not become a system of record for any sibling's state. Non-negotiable; the §6 test is the spike's central question.
- CON-ORG-02  Doctrine §7 admission is owner-reserved. This package authorizes design + spike only; "go" yields a recommendation to the owner, never an admission.
- CON-ORG-03  "Heddle" is a naming placeholder (doctrine §8); all cross-product-visible field names must clear the glossary discipline before any wire surface freezes.
- CON-ORG-04  Hook-fed over discipline-fed (PDR-0013 admission bar (e)): any mechanism that relies on agents remembering to invoke it is rejected at design time.
