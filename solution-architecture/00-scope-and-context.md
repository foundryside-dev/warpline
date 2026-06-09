# Scope and Context

## Problem statement
AI coding agents (and the operator dispatching them) have no mechanical answer to
"given this diff, which entities changed, by whom, when — what is downstream-affected,
and what must be re-verified?" No Weft member stores per-entity history: Loomweave is
deliberately point-in-time (its `high_churn`/`recently_changed` tools are dead no-ops),
and Charter's deferred impact surface covers only the requirements-side slice. The gap
is filled today by grep-plus-hope or human blast-radius review, which is exactly the
supervision load the federation exists to remove (PDR-0004, PDR-0013). Heddle is the
candidate bounded temporal-graph authority for that gap — pulled forward into spare
dev capacity while the four launch members are frozen for the gold-standard cutover.

## Input classification
- Shape: business/problem brief (spike ticket `weft-e4589e6570` + weft `roadmap-ideas.md` §3 + PDR-0013) — concept-level, no prior HLD
- Mode: greenfield (new candidate product; integrates read-only with existing siblings — integration in `15-`, no `16-migration-plan.md`)
- scope_tier: M — trigger (a): new bounded context, new deployment unit, and new data owner (Heddle owns temporal change data no member owns today)
- Enterprise: not activated — no ARB, no TOGAF deliverable set, no EA countersign, no ArchiMate tooling; own-use local-first developer tooling
- Archaeologist context available: not applicable (greenfield); sibling-surface facts are cited from weft hub docs and marked `[ASSUMED]` where unverified, because suite docs are known-drifted — verify against executable source before relying on any of them

## In scope
- Per-entity change history across commits/runs, keyed on SEI when available, durable locator otherwise
- Downstream-propagation (blast-radius) query over snapshotted structural-graph edges
- "What must be re-verified" worklist output, agent-consumable (CLI + MCP)
- Git-history backfill + hook-fed incremental ingest (no agent discipline required)
- Solo mode (git-only, locator-keyed) and pair mode (SEI-keyed when a Loomweave catalog is readable)
- The design seam for post-launch member-side consumers (designed, not built — see Out of scope)

## Out of scope
- ANY code change inside filigree, wardline, legis, or loomweave before the launch cutover (owner directive 2026-06-10; CON-TEC-02)
- Requirements-side impact analysis ("which obligations are affected") — that is Charter's domain; Charter is a prospective *consumer* (doctrine §2)
- Change *execution* / rollback — the Shuttle thought-bubble's gap, not Heddle's
- Agent identity/trust — Tabard (Later); Heddle records actor strings as given, it does not verify them
- Cross-host federation, hosted/SaaS anything, telemetry (vision anti-goals)
- Federation admission itself — owner-reserved (doctrine §7)

## Stakeholders
- **Accountable (validates outcome):** john (owner) — rules go/no-go on the spike result and owns the §7 admission call
- **Responsible (builds / runs):** weft-pm (design + dispatch); spare dev capacity (spike execution) — explicitly NOT the four launch-member work streams
- **Consulted / informed:** the four member maintainer lines (their published read surfaces are consumed; their trackers receive consumer-wiring tickets only post-launch); Charter design line (impact-analysis seam)

## Assumptions
1. `[ASSUMED]` Loomweave exposes a readable point-in-time entity catalog + call/dependency edges via a published surface (CLI/MCP/DB) sufficient to snapshot graph edges per commit. Verify against loomweave source, not docs.
2. `[ASSUMED]` SEIs are stable across the commit ranges Heddle ingests (the SEI standard is LOCKED, but per-entity SEI continuity through renames/moves is exactly what the spike must measure).
3. `[ASSUMED]` Git history alone carries enough signal (paths, hunks, authors, timestamps) for a useful locator-keyed solo mode without any sibling.
4. `[ASSUMED]` SQLite is the suite-normal embedded store (evidenced by filigree + loomweave WAL-hygiene work) and is adequate for the temporal store at own-use scale.
5. Actor attribution is taken from commit metadata + filigree-style `--actor` strings as given; trustworthiness of identity is out of scope (Tabard).

## Open questions
1. Can ingest be **purely read-side and hook-fed** (git hooks + reading published sibling surfaces), with zero member-side emit? If member-side emit turns out to be required, the design conflicts with CON-TEC-02 pre-launch and with the aggregator risk — this is spike question Q1 and a potential kill.
2. Is the propagation query honest from **snapshotted** edges (staleness window = since last snapshot), and what staleness is acceptable before answers mislead agents? (Spike Q2; false negatives are the dangerous direction.)
3. Where exactly is the Heddle/Charter seam? Proposed: Heddle = structural/temporal slice, Charter = obligations slice, Charter consumes Heddle. Needs Charter-side confirmation post-launch. (Spike Q3.)
4. Does solo mode pass doctrine §7 Q2 ("useful by itself") in real dogfood — i.e. is locator-keyed history without SEI still preferred over grep by agents? (Spike Q4 / the grep test.)
5. Store placement that cannot regress the tree-cleanliness guardrail (precedent: loomweave runtime DB under `.weft/`, `weft-d822a7de2d`). Default: outside the analyzed repo's working tree.
6. `99-solution-architecture-document.md` + consistency gate are **deliberately deferred until the spike answers Q1–Q4** — assembly before that would gate a design whose load-bearing assumptions are unproven. Recorded here so the gap is a declared stop, not a silent drop.

## Workflow plan
1. quantifying-nfrs → `02-`, `03-` ✓
2. resisting-tech-and-scope-creep → `04-`, `05-`, `06-` ✓
3. router-owned → `07-`, `08-`, `09-`, `10-`, `11-`, `13-` ✓ (12 not required at tier M)
4. writing-rigorous-adrs → `adrs/0001..0004` ✓
5. maintaining-requirements-traceability → `14-` ✓
6. designing-for-integration-and-migration → `15-`, `17-` ✓ (16 skipped: greenfield)
7. mapping-to-togaf-archimate — skipped (enterprise not activated)
8. assembling-solution-architecture-document → `99-` — DEFERRED until spike Q1–Q4 resolve (open question 6)
