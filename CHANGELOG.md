# Changelog

All notable changes to heddle are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and heddle adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The cross-member MCP seam contracts are versioned independently as
`heddle.<contract>.v1` and frozen at the federation clean-break launch; a `v2`
is a new contract URI, never a mutation of `v1`.

## [1.0.0] - 2026-06-13

First stable release. heddle joins the Weft federation as its 5th member — the
temporal / change-impact authority ("if I touch X, what breaks, and what must I
re-verify?"), implemented to the hub-frozen interface-lock
(`2026-06-13-heddle-interface-lock.md`).

### Added

- **6 frozen outbound MCP tools**, each with an endorsed name and a short shim
  returning identical schema+data:
  - `heddle_change_list` / `changed` — `heddle.change_list.v1`
  - `heddle_entity_timeline_get` / `timeline` — `heddle.entity_timeline.v1`
  - `heddle_entity_churn_count_get` / `churn` — `heddle.entity_churn_count.v1`
    (new: per-entity change-event aggregation; the no-dead-by-design read that
    lights up loomweave's `entity_high_churn_list`)
  - `heddle_impact_radius_get` / `blast_radius` — `heddle.impact_radius.v1`
    (carries the wardline `affected_scope` and legis `preflight_impact` payloads)
  - `heddle_reverify_worklist_get` / `reverify` — `heddle.reverify_worklist.v1`
  - `heddle_edge_snapshot_capture` / `capture_snapshot` — `heddle.edge_snapshot.v1`
    (the only mutating tool; writes `.weft/heddle/` only)
- **Canonical success envelope** (`query`, `data`, `warnings`, `next_actions`,
  `enrichment`, `meta`) with `meta.local_only: true`, `meta.peer_side_effects: []`,
  and a CLOSED `enrichment` vocabulary (`present | absent | unavailable`, plus
  `stale | partial | skipped` for edges). Sibling absence is explicit, never an
  implied clean/allowed state (enrich-only, deconfliction-first).
- **`heddle.error.v1`** with CLOSED `error_code` and `retryability`
  (`retry_safe | retry_with_changes | fatal`) vocabularies.
- **SEI keying**: every entity carries both `locator` and `sei`
  (`loomweave:eid:...`, opaque — heddle never mints or parses it).
- **Federation member lifecycle** (`heddle install` / `heddle doctor`):
  - `install` wires MCP bindings (`.mcp.json` + `~/.codex/config.toml`), the git
    `post-commit` ingest hook, the Claude `SessionStart` hook, the
    `heddle-workflow` skill (into `.claude/skills/` and `.agents/skills/`), the
    CLAUDE.md/AGENTS.md instruction blocks, and `.weft/heddle/` config —
    idempotent, atomic, symlink-safe, and never clobbering a foreign member's
    block.
  - `doctor` verifies every component; `doctor --fix` re-applies anything
    autofixable. JSON via `--json` (`heddle.doctor.v1`).
- **`heddle-workflow` skill** with progressive-disclosure references
  (`contract.md`, `tools.md`, `degrade-and-federation.md`) and a worked example.
- **14 golden vectors** (executable `tests/contracts/test_golden_vectors.py` plus
  a manifest for the GS-7 conformance oracle).

### Fixed

- **HX1 — real SEI resolution.** heddle now sends bare, src-layout-stripped
  dotted qualnames to loomweave `entity_resolve` (which resolves the import path,
  not the filesystem path), keeping prefixed entity ids only for
  `entity_neighborhood_get`. Resolution now returns real `loomweave:eid:` SEIs
  against the live loomweave and is **deployment-independent** (works against
  stock loomweave). Ingest resolves SEIs by default.
- **HX2 — portable executed baseline.** The dogfood baseline uses `git grep`
  instead of a hardcoded `ripgrep` dependency, so it reaches `ready=True` on a
  host without `rg`.

### Notes

- Reserved-shape inbound seams: loomweave is PROVEN and frozen; filigree,
  wardline, and the legis rename feed remain reserved-shape / non-binding until a
  golden vector demonstrates real consumption.

## [0.1.0] - pre-admission

Pre-admission spike: local-first temporal store, git backfill/ingest, the initial
draft MCP surface, and the dogfood readiness gate. Superseded by 1.0.0.
