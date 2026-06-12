# Agentic MCP Product Design - Heddle

Status: product-candidate design bar, pre-admission

Heddle should feel like a first-class Weft federation member and a first-class
agentic MCP product. That means an agent can discover the product, understand
authority boundaries, ask the core questions, and act on the result without
reading source code, raw SQLite, or sibling-specific tribal knowledge.

MCP deficiencies are P0 product defects. They are not minor polish. If the MCP
surface is not at least as good as existing tools in solo mode and better with
federation members, Heddle has no reason to exist. The right response is
refactor, not workaround.

## Agent job

When an agent finishes or reviews a change, it needs to know:

1. what entities changed in this rev range
2. who/when changed them and where the evidence came from
3. what downstream entities may be affected
4. what should be reverified before completion
5. what is unknown, absent, stale, or skipped

The happy path is:

1. `tools/list`
2. `changed`
3. `reverify`

`timeline` and `blast_radius` are supporting tools for explanation, debugging,
and deeper review. The core flow must not require a user to know table names,
store paths, snapshot internals, or Loomweave implementation details.

## MCP product rules

- tools/list is the front door. Tool names, descriptions, schemas, and
  required fields must teach the workflow without a README.
- Responses are structured product contracts, not CLI transcripts.
- Every response includes enough metadata to tell what repo, range/entity, and
  Heddle version produced the answer.
- Every degraded response states the degradation explicitly: `NO_SNAPSHOT`,
  `SKIPPED`, absent SEI, absent edges, stale snapshot, unknown staleness, or a
  structured recoverable error.
- Every core response should tell the agent what to do next when the answer is
  thin.
- CLI and MCP should share handlers. Divergence means the product has two
  truths, and MCP must not be the poorer one.

## Federation product rules

- Heddle is enrich-only. Sibling absence makes answers thinner, not impossible.
- Heddle is not an aggregator. It stores temporal change-impact facts and dated
  edge snapshots only.
- Heddle never mints, parses, or owns SEI. It preserves SEI opaquely when
  Loomweave supplies it.
- Heddle never files work, closes work, waives findings, gates commits, signs
  governance, or decides requirements impact.
- Draft contracts in this repo are Heddle-owned until owner admission. Sibling
  products choose whether and how to consume them after admission.

## First-class Weft federation member bar

Heddle can be argued as a first-class Weft federation member only when:

- solo mode is at least as good as existing tools without siblings
- pair mode is better with federation members through published sibling
  surfaces only
- MCP contracts are discoverable and fixture-backed
- release-candidate gates prove member repo cleanliness
- admission artifacts separate Heddle-owned facts from sibling-owned authority
- a dogfood run shows agents choose Heddle over manual grep for impact review

Until then, Heddle is a product candidate with a `go` spike recommendation, not
an admitted member.

## P0 MCP deficiency examples

- A core query can only be answered through CLI, not MCP.
- `tools/list` leaves an agent unable to infer the next call.
- A degraded response omits completeness, staleness, or enrichment state.
- Errors are plain strings without recoverable codes or query context.
- Reverify output requires manual grep to decide what to verify.
- MCP response shape diverges from CLI behavior or contract fixtures.

Any of these should trigger a productization/refactor slice before new feature
work.
