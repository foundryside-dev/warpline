# Solution Overview

## The claim
Heddle is a **bounded temporal-graph authority**. It owns exactly one thing no
federation member owns: **what happened to entities over time** — per-entity
change history keyed on SEI (locator in solo mode), plus point-in-time snapshots
of structural edges sufficient to answer "what is downstream of this change."

The doctrinal cut that keeps it out of aggregator territory (doctrine §6):
**Loomweave owns "now" (the current graph, the identity authority); Heddle owns
"over time" (the history Loomweave deliberately discards).** Heddle never serves
current structural truth — a query about "now" is answered by Loomweave or not
at all. Heddle serves trajectories and blast radii, stamped with the staleness
of the edges it traversed.

## Shape (one paragraph)
A local-first tool in the suite mold: a CLI + MCP server over an embedded
store. Ingest is read-side and hook-fed — a git post-commit hook (plus cold
backfill over `git log`) appends change events; when a Loomweave catalog is
readable, an identity resolver upgrades locator keys to SEIs and a snapshot
differ records structural-edge snapshots per ingested commit. Queries traverse
the stored history + edge snapshots: timeline (FR-02), changed-set (FR-01),
blast radius (FR-03), re-verify worklist (FR-04). No daemon, no broker, no
member-side code.

## What it is NOT (anti-goals, inherited and local)
- Not an aggregator or mirror of any sibling's system of record (doctrine §6).
- Not a "now" oracle — point-in-time structural truth stays Loomweave's.
- Not requirements impact — Charter's slice; Charter consumes Heddle post-launch.
- Not change execution (Shuttle's gap), not identity trust (Tabard).
- Not load-bearing for any sibling, ever (doctrine §5).

## Pairwise stories (enrich-only, each coherent alone — doctrine §4/§7 Q3)
- **+ Loomweave:** SEI-keyed history; Loomweave's dead `high_churn` /
  `recently_changed` surfaces light up as consumers (post-launch wiring).
- **+ Charter:** "what must be re-verified" feeds obligation re-verification.
- **+ Legis:** gate scope — which attestations does this diff invalidate.
- **+ Wardline:** scope a re-scan to the affected set instead of the world.
- **+ Filigree:** a re-verify worklist can be filed as issues; change events
  can carry the actor strings filigree already attributes.
- **Absent any of them:** Heddle still ingests git, still answers
  locator-keyed timelines and blast radii. Less rich, never broken.

## Why now
Spare dev capacity exists while the four launch members are frozen
(CON-TEC-02); Heddle is the only shaped candidate that is a genuinely new
system rather than a feature inside a frozen member, and PDR-0013 already
ranked it discovery slot #1. Spike-first: this package designs to a go/no-go,
not to a build commitment.
