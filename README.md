# heddle — temporal change-impact authority

Version 1.0.0 · Weft federation member (5th) · local-first · enrich-only

heddle is the Weft federation's **temporal / change-impact authority**. It owns
the one thing no other member stores — **per-entity change history across runs,
keyed on SEI** — and the downstream-propagation query over it. It answers, every
session, the question an agent asks before claiming a change is done:

> *Given this diff: which entities changed, by whom, when — what is
> downstream-affected over the call graph, and what must I re-verify?*

The federation split is deliberate: **loomweave owns "now"** (the point-in-time
graph and SEI minting); **heddle owns "over time"** (dated change facts and edge
snapshots). heddle is **enrich-only** — it boots, ingests, and answers with no
sibling installed, and its facts are advisory and never gate.

## Features

- **6 MCP tools** for change lists, entity timelines, churn counts, impact
  radius, reverify worklists, and dated edge-snapshot capture — each with a
  frozen `heddle.<contract>.v1` schema.
- **Honest answers**: every response carries `completeness` + `staleness` and a
  CLOSED `enrichment` vocabulary (`present | absent | unavailable`). Sibling
  absence is explicit, never an implied "clean/allowed" state.
- **Local-first & safe**: all state lives under `.weft/heddle/` (git-ignored);
  the only mutating tool writes there and never touches a sibling repo.
- **Real SEI resolution** against the live loomweave, deployment-independent.
- **Federation member lifecycle**: `heddle install` / `heddle doctor [--fix]`
  wire and verify MCP bindings, hooks, the agent skill, and config.
- **Endorsed names + short shims**: e.g. `heddle_change_list` and `changed`
  return identical schema and data.

## Installation

Install as a [uv](https://docs.astral.sh/uv/) tool (recommended — provides the
`heddle` and `heddle-mcp` executables on your `PATH`):

```bash
uv tool install heddle
heddle --version        # heddle 1.0.0
```

For development from a checkout:

```bash
git clone <repo-url> heddle && cd heddle
uv run heddle --version
```

**Requires Python ≥ 3.12.**

## Quick start

### 1. Install heddle into a repository

`heddle install` wires heddle as a federation member of the target repo —
idempotent, atomic, and it never clobbers a sibling's config block:

```bash
heddle install --repo /path/to/project   # MCP bindings, hooks, skill, config
heddle doctor  --repo /path/to/project   # verify; add --fix to autofix
```

`doctor` exits non-zero if anything is missing and prints a per-component
report (`--json` emits a `heddle.doctor.v1` summary).

### 2. The core loop (CLI)

```bash
heddle backfill --repo /path/to/project --json          # ingest git history
heddle changed  --repo /path/to/project --rev-range HEAD~1..HEAD --json
heddle capture-snapshot --repo /path/to/project --json  # capture loomweave edges
heddle reverify --repo /path/to/project --changed-entity-key-id 1 --json
```

The post-commit hook installed in step 1 keeps the temporal store fresh as you
commit, so `changed`/`timeline`/`churn` answer without a manual backfill.

### 3. The same flow from an MCP host

1. `tools/list` — discover the surface (read/write posture, idempotency, repo
   requirement, touched paths, federation dependencies).
2. `heddle_change_list` (`changed`) — **call first**; read its `next_actions`.
3. `heddle_reverify_worklist_get` (`reverify`) — the worklist to recheck.
4. `heddle_impact_radius_get` / `heddle_entity_timeline_get` — for explanation.
5. `heddle_edge_snapshot_capture` (`capture_snapshot`) — when impact/reverify
   reports `NO_SNAPSHOT` and loomweave is available.

## MCP tools

Endorsed name and short shim are interchangeable and return identical
schema + data.

| Endorsed name | Shim | Schema | Role |
| --- | --- | --- | --- |
| `heddle_change_list` | `changed` | `heddle.change_list.v1` | Changed entities for a rev range; hands back ready-to-call next actions. |
| `heddle_entity_timeline_get` | `timeline` | `heddle.entity_timeline.v1` | Ordered change history for one entity; reports `sei_resolution` only, never lineage. |
| `heddle_entity_churn_count_get` | `churn` | `heddle.entity_churn_count.v1` | Per-entity change-event counts; a never-observed entity is `churn_count: 0`. |
| `heddle_impact_radius_get` | `blast_radius` | `heddle.impact_radius.v1` | Downstream affected set with mandatory `completeness` + `staleness`. |
| `heddle_reverify_worklist_get` | `reverify` | `heddle.reverify_worklist.v1` | The agent worklist to recheck before claiming completion. |
| `heddle_edge_snapshot_capture` | `capture_snapshot` | `heddle.edge_snapshot.v1` | The only mutating tool; captures dated loomweave edges into `.weft/heddle/`. |

### Response contract

Every outbound tool returns the frozen success envelope:

```json
{
  "schema": "heddle.<contract>.v1",
  "ok": true,
  "query": { "repo": "...", "tool": "...", "arguments": {}, "sort": {}, "page": {} },
  "data": { },
  "warnings": [],
  "next_actions": {},
  "enrichment": {"sei": "...", "edges": "...", "work": "...",
                  "risk": "...", "governance": "...", "requirements": "..."},
  "meta": {"producer": {"tool": "heddle", "version": "1.0.0"},
            "local_only": true, "peer_side_effects": []}
}
```

- `enrichment` is a CLOSED vocab: `present` (peer present, fact attached),
  `absent` (peer present, no fact), `unavailable` (peer unreachable) — plus
  `stale | partial | skipped` for `edges`. None of these is ever a transport
  error or an implied clean state.
- Errors use `heddle.error.v1` with a CLOSED `error_code` set and `retryability`
  of `retry_safe | retry_with_changes | fatal`. Switch on `error_code`, not
  message text.
- Every entity carries both `locator` and `sei` (`loomweave:eid:...`, opaque —
  heddle never mints or parses it). `heddle_entity_key_id` is internal and **not**
  a federation key; key on `sei` (preferred) or `locator`.

Full contract: [`docs/federation/contracts.md`](docs/federation/contracts.md)
and the bundled `heddle-workflow` skill
([`src/heddle/skills/heddle-workflow/`](src/heddle/skills/heddle-workflow/)).

## Federation member lifecycle

`heddle install` installs everything by default, or a subset via flags
(`--claude-code`, `--codex`, `--claude-md`, `--agents-md`, `--gitignore`,
`--hooks`, `--session-hook`, `--skills`, `--codex-skills`, `--config`):

| Component | What it does |
| --- | --- |
| MCP bindings | Registers heddle in `.mcp.json` (Claude Code) and `~/.codex/config.toml` (Codex), stdio transport. |
| Hooks | git `post-commit` (fail-soft `heddle ingest-commit`) + Claude `SessionStart` (`heddle session-context`). |
| Skill | Copies `heddle-workflow` into `.claude/skills/` and `.agents/skills/`. |
| Instructions | Injects a `heddle:instructions` block into CLAUDE.md / AGENTS.md (foreign blocks preserved). |
| Config | Writes `.weft/heddle/config.json` + `INSTALL_VERSION`. |

`heddle doctor` checks all of the above; `heddle doctor --fix` re-applies
anything fixable.

## Configuration & runtime layout

heddle is local-first; runtime state lives under `.weft/heddle/` and is
git-ignored:

```text
.weft/heddle/
├── heddle.db          # SQLite temporal store (change events, edge snapshots)
├── config.json        # member identity {prefix, name, version}
├── INSTALL_VERSION    # schema/version marker
└── .gitignore         # keeps ephemeral runtime files out of commits
```

The loomweave command heddle uses for SEI resolution / edge capture is
server/project config — set `HEDDLE_LOOMWEAVE_COMMAND` (default `loomweave`); it
is **not** a public MCP tool argument. `git add -A` never stages a heddle DB.

## Development

```bash
uv run ruff check .          # lint
uv run mypy                  # strict type-check
uv run pytest                # test suite
uv run heddle mcp-smoke --repo . --json          # live stdio MCP smoke
uv run heddle dogfood-eval --real-member-repo /home/john/lacuna --json
```

`heddle dogfood-eval` exercises the real change → reverify loop (synthetic lanes
plus a real-member lane against an actual loomweave index) and gates on
`ready=True`. See [`spike/REPORT.md`](spike/REPORT.md) for the readiness verdict
and [`CHANGELOG.md`](CHANGELOG.md) for release history.

## Documentation

| Topic | Where |
| --- | --- |
| Federation seam contracts (frozen) | [`docs/federation/contracts.md`](docs/federation/contracts.md) |
| Agent usage (progressive-disclosure skill) | [`src/heddle/skills/heddle-workflow/`](src/heddle/skills/heddle-workflow/) |
| Solution architecture | [`solution-architecture/`](solution-architecture/) |
| Product workspace (vision, roadmap, PDRs) | [`docs/product/`](docs/product/) |
| Consumer integration tickets | [`docs/integration/post-admission-consumer-tickets.md`](docs/integration/post-admission-consumer-tickets.md) |
| Release history | [`CHANGELOG.md`](CHANGELOG.md) |

The authoritative interface-lock specification is hub-owned
(`2026-06-13-heddle-interface-lock.md` in the weft hub); heddle implements **to**
it and does not edit it.

## Contributing

heddle implements to a frozen cross-member contract. Changes to a tool's name,
input/output schema, the envelope, or the error/enrichment vocabularies are a
hub decision — escalate with evidence rather than diverging. Internal changes
must keep `ruff`, `mypy --strict`, and the full test suite green, and the 14
golden vectors (`tests/contracts/test_golden_vectors.py`) passing.

## License

MIT — see [`LICENSE`](LICENSE). Copyright (c) 2026 John Morrissey. Consistent
with the rest of the Weft federation.
