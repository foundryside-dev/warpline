# Heddle go/no-go spike — brief

**Ticket:** `weft-e4589e6570` (weft hub) · **Mandate:** PDR-0013 discovery slot #1
**Mode:** prove or kill. A "go" is a recommendation to the owner (doctrine §7 —
admission is owner-reserved). "No-go" is a fully successful spike outcome.
**Standing constraint:** zero diffs in filigree/wardline/legis/loomweave
(CON-TEC-02). If a question can't be answered without one, that IS the answer
to that question.

## The question (verbatim from the ticket)
Can a bounded temporal-graph authority own per-entity change history keyed on
SEI across runs + the downstream-propagation query — "given this diff, which
SEIs changed / by whom / when, what is downstream-affected, what must be
re-verified?" — WITHOUT becoming the forbidden aggregator (doctrine §6)?

## Spike questions → kill criteria

**Q1 — Acquisition (ADR-0002, RSK-02).** Verify against loomweave SOURCE (not
docs): does a published read surface expose catalog + edges sufficiently to
snapshot per-commit deltas, read-only? Build a throwaway reader to prove it.
*Kill if:* no sufficient surface exists AND providing one needs member-side
code (then: park-until-cutover or no-go — report, don't patch).

**Q2 — Honesty of snapshots (NFR-06, RSK-05).** On the weft member repos as
corpus: plant N changes with known downstream consumers; measure recall at
depth ≤ 2 and the staleness window at which answers start missing consumers.
*Kill if:* recall < ~80% even with fresh snapshots (placeholder bar — set
properly at spike start), or honest answers require near-continuous
re-snapshotting (cost makes it a daemon, doctrine §6).

**Q3 — Doctrine fit (ADR-0004, RSK-01, RSK-03).** Run the §5 failure test and
§6 checklist against the prototype's actual store and query log: did anything
mirror sibling state? Did any query answer "now"? Write the Heddle/Charter seam
section. *Kill if:* the firewall can't hold under real query pressure — agents
only find it useful when it answers "now"-shaped questions.

**Q4 — The grep test, solo mode (ADR-0003, RSK-04; admission bar (b)).** Give
agents real tasks on a repo with Heddle available, unprompted, in both modes
(SEI-keyed and locator-only). Measure: do they reach for it over grep? Is the
locator-only mode still preferred?
*Kill if:* agents ignore it even when SEI-keyed. *Narrow the claim if:* only
the SEI mode wins (then §7 Q2 needs owner judgment).

## Deliverable
`spike/REPORT.md`: per-question evidence, measured numbers vs the NFR-02/06
placeholders, the doctrine review, the Charter-seam statement, and a single
recommendation line: **go (admission recommendation to owner) / no-go /
park-until-cutover** — plus, on go, which `05-` deferred selections the
evidence now decides.

## Expiry
ADR-0001: if not run by 2026-08-09, re-examine before executing — the design
assumptions and the launch context will both have moved.
