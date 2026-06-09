# Descoped and Deferred

Each entry carries a reactivation trigger. (Gate waivers, if any arise at
assembly, are a different register — they live in the `99-` gate report.)

| # | Item | Disposition | Reactivation trigger |
|---|------|-------------|----------------------|
| D-01 | Member-side consumer wiring (loomweave `high_churn`/`recently_changed` lighting up, wardline scoped re-scan, legis gate scope, charter re-verify pull) | DEFERRED — designed at the seam level in `15-`, built only in each member's own tracker | launch cutover lands (lifts CON-TEC-02) AND spike returns go AND owner admits per §7 |
| D-02 | Requirements-side impact analysis | DESCOPED — Charter's domain (doctrine §2) | never (re-open only via a doctrine change, which is owner-reserved) |
| D-03 | Change execution / rollback provenance | DESCOPED — Shuttle's sketched gap | never within Heddle |
| D-04 | Actor identity verification ("is this actor string true?") | DESCOPED — Tabard (roadmap Later) | Tabard ships; Heddle then consumes, not implements |
| D-05 | Cross-host / multi-machine history | DEFERRED | cross-host federation becomes real (roadmap Later) |
| D-06 | Working-tree (uncommitted) change tracking — blast radius of a *dirty* tree | DEFERRED — spike measures committed-history value first; dirty-tree overlaps mechanism B's write-guard territory and needs a seam ruling | post-spike, jointly with B's design line (avoid building impact-awareness twice) |
| D-07 | Optional convenience watcher/daemon | DEFERRED — core flows are hook-fed and daemonless | only if post-spike dogfood shows hook latency (NFR-02b) unmeetable synchronously |
| D-08 | Non-code entity history (docs, configs) | DEFERRED — start with code entities where SEI + call edges exist | dogfood evidence of doc-blast-radius pain (PDR-0013 bar (a)) |
| D-09 | Permanent name + glossary registration for cross-product field names | DEFERRED — placeholder name per doctrine §8 (CON-ORG-03) | before any wire surface freezes / before admission |
