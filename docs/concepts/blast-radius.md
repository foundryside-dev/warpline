# Blast-radius and the re-verification worklist

These are the two questions warpline exists to answer:

1. **Blast-radius** (`warpline_impact_radius_get` / `blast_radius`): given a set of
   changed entities, what is downstream-affected over the code graph?
2. **Re-verification worklist** (`warpline_reverify_worklist_get` / `reverify`):
   turn that into a prioritized list of things to recheck before claiming the
   change is done.

## How blast-radius is computed

warpline does a bounded breadth-first traversal over the latest dated edge
snapshot:

1. Start from the changed entities (the seed set).
2. Walk outward along the snapshot's edges, one hop at a time, up to `depth`
   hops (`depth` is `0`–`5`, default `2`).
3. Each newly reached entity is reported as `affected`, with its `depth` (hops
   from the nearest seed) and the `via_edges` path that connects it.

Edges come from loomweave's neighborhood: `calls` edges (caller → callee) and
`references` edges (referencer → referenced). Each edge carries a `confidence`.

The traversal is over the **snapshot**, which is dated — so blast-radius is a
historical answer ("as of this snapshot's commit, these are downstream"), and its
freshness is reported in `staleness`. See
[Temporal facts vs. the current graph](temporal-vs-graph.md).

## Completeness is mandatory and load-bearing

Every blast-radius and reverify answer carries a `completeness` field. **There is
no "the affected set is empty" without a completeness qualifier.** This is the
single most important thing to read correctly:

| `completeness` | Meaning | What to do |
| --- | --- | --- |
| `FULL` | A snapshot is present and the neighborhood was captured fully. | Trust the affected set. |
| `DELTA` | A snapshot is present but some entities failed to capture. | Inspect `failed_entities`; treat the affected set as a floor, not a ceiling. |
| `NO_SNAPSHOT` | No usable snapshot exists. | The answer is the changed set only — run `capture_snapshot` and retry. |
| `SKIPPED` | A capture ran but loomweave was absent, so no edges were recorded. | Same as `NO_SNAPSHOT` for traversal. |

A `DELTA` answer includes a `failed_entities` list naming which entities were not
captured and why — see the
[`capture_snapshot` data shape](../reference/mcp-tools.md#warpline_edge_snapshot_capture--capture_snapshot)
in the MCP tool reference (`[{"locator": "...", "reason": "..."}]`).

An empty `affected` list under `NO_SNAPSHOT` means **"warpline has no graph to look
at,"** not **"nothing is affected."** warpline will never let a thin answer pass for
a complete one — a `warnings` entry restates the limitation in prose, too.

`staleness.commits_behind` reports how many commits have landed since the snapshot
was captured. A `FULL` snapshot that is far behind `HEAD` is still a dated answer;
the number tells you how much to discount it.

## The re-verification worklist

`reverify` takes the blast-radius result and renders a worklist. Each item is one
entity to recheck:

```json
{
  "entity": {"locator": "...", "sei": "..."},
  "priority": "P1 | P2 | P3 | unknown",
  "reason": "changed | downstream",
  "depth": 0,
  "why": [ /* the via_edges path, for downstream items */ ],
  "suggested_verification": [
    {"kind": "test", "command": "run tests touching this entity if known"},
    {"kind": "inspection", "command": "inspect callers and behavior at this boundary"}
  ],
  "enrichment": {"work": [], "risk": [], "governance": [], "requirements": []}
}
```

Key properties:

- **The changed entities are always in the worklist** (`reason: changed`), so the
  worklist is non-empty and useful even with `NO_SNAPSHOT`. Downstream entities
  (`reason: downstream`) are added only when a snapshot exists.
- **`priority` comes from sibling enrichment, not from warpline.** When the
  Filigree work-state seam is wired, an entity linked to a high-priority issue
  gets that issue's priority. With no work enrichment, `priority` is `unknown` —
  warpline does not invent a priority.
- **`suggested_verification` is advice, not a command warpline runs.** warpline
  never executes tests or makes changes.

## warpline proposes work; it never files it

The reverify answer carries `data.next_actions.filigree[]` — *candidate* work
items warpline suggests, such as "review this linked issue." These are proposals.

> warpline files nothing, closes nothing, claims nothing.

A candidate in `next_actions.filigree[]` is something a human or a write-capable
tool can choose to act on. warpline reads work-state links to enrich the worklist;
it never writes work state. This is the same advisory boundary that governs every
warpline seam — see [Advisory, never gating](advisory-not-gating.md).
