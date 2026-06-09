# ADR-0004 — The aggregator firewall: Heddle owns "over time," never "now"

**Status:** Proposed (the spike's central doctrinal question) · 2026-06-10
**Context:** Doctrine §6 forbids a central store, a system of record for
cross-product state, and any mirror of sibling authority. A temporal authority
that snapshots Loomweave's graph LOOKS like a mirror — this is the named
go/no-go risk in the concept source ("naive framing makes it a forbidden
aggregator") and the reason Heddle is a spike, not a build.

**Decision:** A hard firewall on what the Temporal Store may contain and what
queries Heddle may answer:

1. **Stored:** only temporal facts no sibling stores — append-only change
   events; *dated* edge snapshots whose value is precisely their datedness;
   the entity-key map with upgrade lineage. Re-derivable from git + a sibling
   re-read; Heddle's store is never the recovery source for anyone else's data.
2. **Never stored:** finding lifecycle (Filigree's), trust baselines
   (Wardline's), attestations (Legis's), obligations (Charter's), the *current*
   catalog (Loomweave's). Not even as a cache.
3. **Never answered:** "what is the current structure?" — a `now`-shaped query
   is answered with a pointer to Loomweave (or `NO_SNAPSHOT` honesty in solo
   mode), not from the freshest snapshot. The freshest snapshot is still
   *history*.
4. **Placement:** the store lives outside any analyzed repo's working tree
   (NFR-05) and outside any sibling's data dir — one DB per repo under the user
   data dir, no shared DB across members (§6 "no shared store").

**Alternatives considered:**
- *Cache the current catalog for convenience* — rejected: the cache becomes
  the de-facto read path, i.e. the stealth-monolith failure mode (§3).
- *Store full graph copies per commit* — rejected: indistinguishable from a
  mirror; deltas keyed to commits keep the data honestly temporal (also
  NFR-02a).

**Consequences:** some queries agents will ask ("who calls X *right now*?")
are deliberately out of scope and routed to Loomweave; the spike's doctrine
review (Q1/Q3) tests whether this firewall holds under real query pressure.

**Rollback / expiry:** if dogfood shows agents need Heddle to answer
"now"-queries to be useful at all, that is a NO-GO signal per §6 — escalate to
the owner with evidence; do not widen the firewall unilaterally.
