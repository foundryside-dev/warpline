# Heddle - temporal / change-impact authority (product candidate)

**Status: PRODUCT CANDIDATE - spike recommends `go`; owner admission still reserved.**
Name is a placeholder per federation doctrine §8.

Heddle is a candidate Weft federation member: a bounded **temporal-graph
authority** owning the one thing no existing member stores — **per-entity change
history across runs, keyed on SEI** — and the downstream-propagation query over
it. It exists to answer, mechanically, every agent's every-session question:

> *Given this diff: which entities changed, by whom, when — what is
> downstream-affected over the call graph, and what must be re-verified?*

Today that question is answered by grep-plus-hope or human blast-radius review
(= supervision load). Loomweave deliberately stores only the point-in-time
graph; its `high_churn` / `recently_changed` tools are dead no-ops because no
member keeps history. Heddle's claim: **Loomweave owns "now"; Heddle owns "over
time."**

## Governing artifacts

| What | Where |
|---|---|
| Spike ticket (go/no-go) | `weft-e4589e6570` in the weft hub tracker |
| Discovery mandate | weft `pm/product/decisions/0013-…` (Heddle = discovery slot #1) |
| Concept source | weft `roadmap-ideas.md` §3 "Heddle" |
| Federation doctrine (binding) | weft `doctrine.md` — esp. §5 enrich-only, §6 not-an-aggregator, §7 admission test (owner-reserved), §8 naming |
| Identity contract (frozen) | weft `sei-standard.md` — LOCKED 2026-06-05 |
| Product workspace | [`docs/product/`](docs/product/) — vision, roadmap, metrics, PDRs, PRDs, MCP product bar |
| Design workspace | [`solution-architecture/`](solution-architecture/) — numbered artifact set, tier M |
| Spike brief | [`spike/SPIKE-BRIEF.md`](spike/SPIKE-BRIEF.md) — the go/no-go questions and kill criteria |

## Product posture

Heddle is now treated inside this repo as a first-class product candidate. Its
primary user is the coding agent trying to finish or review a change without
guessing at blast radius. The MCP surface is therefore a product surface, not a
transport wrapper: if an agent cannot discover and use Heddle from `tools/list`
and structured responses alone, that is a P0 product defect. The minimum bar is
solo-mode parity with existing tools and better answers when federation member
enrichment is present.

Federation admission is still not claimed here. The current product decision is
recorded in [`docs/product/decisions/0001-product-candidate-ownership.md`](docs/product/decisions/0001-product-candidate-ownership.md):
Heddle may be developed and evaluated as a product candidate, while admission,
wire freeze, glossary clearance, sibling tickets, and outward-facing release
decisions remain owner-gated.

## Standing constraints (read before touching anything)

1. **Zero changes to the four launch members** (filigree, wardline, legis,
   loomweave) until the clean-break cutover lands — owner directive 2026-06-10.
   Heddle is read-side only against their published surfaces. Consumer wiring
   inside members is designed here but **deferred** (see `06-` and `15-`).
2. **Enrich-only, never load-bearing** (doctrine §5). Heddle must boot, ingest,
   and answer with no sibling installed.
3. **Not an aggregator** (doctrine §6). Heddle stores only what it is
   authoritative for — temporal change data. It never mirrors a sibling's
   system of record. This is the spike's central question; see ADR-0004.
4. **Member admission is the owner's call** (doctrine §7). This workspace
   authorizes design + spike work only. A "go" result produces an admission
   recommendation, not an admission.
