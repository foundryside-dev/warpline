# Degrade semantics & federation lifecycle

Load this when an answer looks thin, or when wiring heddle into a repo.

## Completeness & staleness (read thin answers honestly)

`heddle_impact_radius_get` / `heddle_reverify_worklist_get` always carry
`completeness` and `staleness` — a thin answer must look thin (NFR-06):

| completeness | meaning | what to do |
| --- | --- | --- |
| `FULL` | snapshot present, full neighborhood | trust the affected set |
| `DELTA` | snapshot partial (some entities failed) | inspect `failed_entities`; treat as a floor |
| `NO_SNAPSHOT` | no usable snapshot | changed-set-only answer — run `capture_snapshot`, retry |
| `SKIPPED` | capture ran but loomweave was absent | same as NO_SNAPSHOT for traversal |

`staleness.commits_behind` is how far the snapshot lags HEAD. Never read
`NO_SNAPSHOT`/empty `affected` as "nothing breaks".

## Enrichment (CLOSED vocab — absence is never "clean")

`enrichment` keys: `sei, edges, work, risk, governance, requirements`.

- `present` — peer present, fact attached.
- `absent` — peer present, no fact for this entity. **Not** an error.
- `unavailable` — peer unreachable. **Not** an error, and **never** an implied
  clean/allowed/governed state.
- `edges` may also be `stale | partial | skipped`.

heddle is deconfliction tooling, not security: every sibling fact is advisory and
**never gates**. wardline absent → `risk: unavailable`, never `clean`.

## Seam authority (who owns what)

- **loomweave** — current structure + SEI minting/resolution. PROVEN+frozen
  inbound (heddle resolves SEIs and captures dated edges through it).
- **filigree** — work state; heddle reads links (`entity_association_list_by_entity`
  + `issue_get`), never files/closes/claims.
- **wardline** — trust policy; heddle re-derives risk as an ordering signal only.
- **legis** — governance + the locator-rename feed; heddle emits advisory impact,
  never governs, and falls back to raw git when the feed is absent.

## Member lifecycle (federation standard)

- `heddle install` — wires MCP bindings (`.mcp.json` + `~/.codex/config.toml`),
  the git post-commit ingest hook, the Claude/Codex SessionStart hook, this skill
  (into `.claude/skills/` + `.agents/skills/`), the CLAUDE.md/AGENTS.md
  instruction blocks (foreign blocks preserved), and `.weft/heddle/` config.
  Idempotent, atomic, symlink-safe.
- `heddle doctor` — verifies every component; `heddle doctor --fix` re-applies
  anything autofixable. JSON via `--json` (`heddle.doctor.v1`).
- Runtime state lives in `.weft/heddle/` (git-ignored); `git add -A` never stages
  a heddle DB.
