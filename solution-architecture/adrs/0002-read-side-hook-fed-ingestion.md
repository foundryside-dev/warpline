# ADR-0002 — Ingestion is read-side and hook-fed; no member-side emit

**Status:** Proposed (spike Q1 validates) · 2026-06-10
**Context:** Heddle needs change events and structural edges. Three candidate
acquisition shapes: (a) siblings push events to Heddle; (b) agents log changes
to Heddle as discipline; (c) Heddle pulls — git hooks + reading published
sibling surfaces.

**Decision:** Shape (c). Cold backfill walks `git log`; a post-commit hook
appends incremental events; when a Loomweave surface is readable, Heddle reads
the catalog/edges and snapshots them itself.

**Drivers:**
- CON-TEC-02: (a) requires code in frozen launch members — unavailable
  pre-launch by owner directive, and the whole point of the spike window.
- Doctrine §5/§6: (a) makes siblings *participants* in Heddle's function
  (coupling that outlives the freeze); (c) keeps the dependency arrow pointing
  the federation-safe way — the product that cares does the reading (§6).
- CON-ORG-04 / PDR-0009 principle: (b) is discipline-fed and will rot;
  rejected outright.

**Alternatives considered:** (a) member-side emit — rejected above, recorded in
`05-` resisted list; (b) agent discipline — rejected (CON-ORG-04); hybrid
(hooks + optional emit later) — possible post-launch evolution, but only as
enrichment a member chooses to add in its own tracker, never required by Heddle.

**Consequences:** Heddle's edge data is as fresh as its last read of the
Loomweave surface → staleness must be first-class in every answer (NFR-06,
`11-` Q3). Solo mode (git-only) must be genuinely useful (ADR-0003, spike Q4).

**Rollback / expiry:** if the spike shows the readable surface is insufficient
to snapshot edges (Q1 fail), this ADR falls and the concept likely dies with it
— pull-based acquisition is load-bearing for doctrine fit.
