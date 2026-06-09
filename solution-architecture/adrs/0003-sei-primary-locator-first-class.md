# ADR-0003 — Keying: SEI when resolvable, locator as first-class solo mode

**Status:** Proposed (spike Q4 measures the lossiness) · 2026-06-10
**Context:** The concept keys history on SEI — but SEI is minted by Loomweave,
and doctrine §5 forbids Heddle's semantics from requiring a sibling. A
SEI-only design would be load-bearing on Loomweave (failure modes 1 and 2 of
the §5 test) and would have no solo story (§7 Q2).

**Decision:** Every change event carries a durable **locator** (path +
qualname) unconditionally; the Identity Resolver adds the SEI when a Loomweave
catalog is readable, and can retroactively *upgrade* locator-keyed history when
a catalog appears later — recorded as lineage, never rewriting events. Locator
mode is a first-class mode, not an error path. The SEI scheme itself
(`loomweave:eid:...`) is consumed as a frozen opaque string (CON-TEC-01) —
Heddle never parses, mints, or extends it.

**Alternatives considered:**
- *SEI-only* — rejected: load-bearing coupling; no solo mode.
- *Locator-only* — rejected: renames/moves shred history continuity, and the
  whole pairwise story with every sibling keys on SEI.
- *Heddle-minted identity* — rejected hard: a second identity scheme is the
  identity-reconciliation-service anti-goal (doctrine §6) and re-litigates the
  LOCKED standard.

**Consequences:** solo-mode rename handling is lossy (`possible_predecessor`
edges, `10-`); the spike must measure whether locator-keyed answers still beat
grep (the grep test, admission bar (b)).

**Rollback / expiry:** if spike Q4 shows solo mode loses the grep test badly,
the honest outcomes are (i) narrow the §7 claim ("useful by itself" = single
mode with reduced continuity) for owner judgment, or (ii) no-go. Not: quietly
making Loomweave required.
