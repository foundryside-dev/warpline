# Federation

warpline is the **5th admitted member** of the Weft federation, the federation's
temporal / change-impact authority. This page describes how it composes with its
siblings — what it consumes, what it feeds, the frozen seam contracts, and how it
behaves when a sibling is absent.

The one rule that governs every line below: **warpline composes pairwise and
enrich-only.** Every warpline-outbound consumption is an enhancement a member can
omit; every warpline-inbound read degrades to a coherent partial answer. warpline is
never load-bearing for anyone, and no one is load-bearing for warpline.

## The authority split

| Member | Owns | warpline's relationship |
| --- | --- | --- |
| **loomweave** | The current structural graph and SEI minting/resolution. | warpline **consumes** SEI resolution and dated structural edges. |
| **filigree** | Work state (issues, claims, links). | warpline **reads** work-state links to enrich the worklist; never writes. |
| **wardline** | Trust policy / taint findings. | warpline **re-derives** risk as an ordering signal; never a verdict. |
| **legis** | Governance and the git-rename feed. | warpline **feeds** advisory change-impact; **consumes** a rename feed if supplied. |

warpline owns what none of them own: per-entity change history over time, dated edge
snapshots, downstream blast-radius, and the re-verification worklist.

## What warpline consumes (inbound seams)

Seam contracts are **frozen at the clean-break launch cutover**
(`2026-06-13-warpline-interface-lock.md`, hub-owned). warpline implements *to* the
contract; it does not edit it. A `v2` is a new schema URI, never a mutation of
`v1`.

### loomweave — SEI resolution + dated edges (PROVEN, FROZEN)

The only proven, frozen inbound seam, with real consumption:

- **`entity_resolve`** — warpline sends bare, src-layout-stripped dotted qualnames
  (e.g. `warpline.store.WarplineStore.timeline`) and stores the returned
  `loomweave:eid:...` SEI opaquely. Resolution is deployment-independent (works
  against stock loomweave).
- **`entity_neighborhood_get`** — warpline captures the entity's `callers`,
  `callees`, `references_in`, and `references_out` as dated edges
  (`calls`/`references`) into its local store. A truncated neighborhood cannot be
  recorded as a complete (`FULL`) snapshot.

loomweave reachability is detected by probing for an installed `loomweave`
command, a `.weft/loomweave/loomweave.db` index for the repo, and the expected
tool set. Absent any of those, warpline degrades — see below.

### filigree — work-state links (EARNED)

warpline reads filigree's ADR-029 entity-association reverse-lookup
(`entity_association_list_by_entity` keyed on the SEI) plus `issue_get`, to answer
"is this changed entity already tracked, and at what priority?" This is the source
of the worklist's `priority` and its `enrichment.work`. It is **earned** —
consumed by golden vectors — and strictly advisory:

> warpline reads work-state links. It never files, closes, or claims work.

Proposed work surfaces as *candidates* in `data.next_actions.filigree[]`, for a
human or a write-capable tool to act on.

### wardline — risk (RESERVED-SHAPE, non-binding)

The wardline risk seam is reserved in the contract but not yet driven by a real
sibling. warpline re-derives risk only as an *ordering* signal for the worklist —
never a clean/dirty verdict. With wardline absent, warpline reports `risk:
unavailable`, **never** `risk: clean`.

### legis / rename feed — provenance + locator renames (RESERVED-SHAPE)

warpline accepts a generic typed locator-rename feed (`{old_locator, new_locator}`)
from any supplier, to stitch an entity's timeline across renames. legis is the
named future external supplier, but the legis *member* stays non-binding: with no
feed, warpline falls back to raw git. With a feed present, `enrichment.governance`
is `present`.

## What warpline feeds the federation (outbound)

warpline feeds **advisory change-impact facts** to governance-style surfaces (Legis,
or a Charter layer): *what changed* and *what is downstream-affected*. Those
surfaces may run their own policy and their own gates — that is their authority.
warpline supplies the facts and never makes the call.

The contract those consumers read is the frozen `warpline.reverify_worklist.v1`
worklist (and the other five tool schemas). The Filigree consumer
(`warpline_worklist_ingest`) shipped in Filigree 3.0.0 as an earned inbound seam on
Filigree's side; the loomweave / wardline / legis consumers are an admitted
fast-follow *outside* the four-member launch cutover. The seam *contracts* froze at
the cutover; consumer *implementations* land without renegotiating them.

See the consumer seam exercised live on the federation specimen: Lacuna
([`lacuna.foundryside.dev`](https://lacuna.foundryside.dev)) runs warpline's tools
against a catalogued codebase and demonstrates the Filigree consumer seam end to
end.

## Degrade-when-absent — the honest table

| Sibling | Present + indexed | Absent / unreachable |
| --- | --- | --- |
| loomweave | SEIs resolve (`sei: present`); snapshots capture (`edges: present`, `completeness: FULL`). | `sei: unavailable`/`absent`; `capture_snapshot` → `completeness: SKIPPED`, `source_version: no_index`; impact/reverify → `NO_SNAPSHOT`. |
| filigree | Worklist gains `priority` and `enrichment.work: present`. | `work: unavailable`; `priority: unknown`; `next_actions.filigree` empty. |
| wardline | `risk: present`. | `risk: unavailable` — never `clean`. |
| legis / feed | timeline stitched across renames; `governance: present`. | `governance: unavailable`; raw-git fallback. |

In every absent case the answer is still well-formed and useful; it simply states,
in machine-readable form, exactly how much it is missing. See
[Degrade behavior](concepts/degrade.md) for the closed `enrichment` vocabulary and
the `absent` ≠ `unavailable` distinction.

## Member lifecycle

warpline ships the federation-standard `install` / `doctor` lifecycle. `install`
wires MCP bindings (`.mcp.json` for Claude Code, `~/.codex/config.toml` for Codex),
the git `post-commit` ingest hook, the Claude `SessionStart` hook, the
`warpline-workflow` agent skill (into `.claude/skills/` and `.agents/skills/`), the
CLAUDE.md / AGENTS.md instruction blocks (foreign blocks preserved), and
`.weft/warpline/` config — idempotent, atomic, symlink-safe. `doctor` verifies every
component; `doctor --fix` re-applies anything autofixable. See the
[CLI reference](reference/cli.md#warpline-install) for the component list.
