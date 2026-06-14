# CLI reference

Complete reference for the `warpline` command-line interface, version `1.0.0`.
warpline is an `argparse` application; the surface is the set of subcommands below.
Every command takes `--repo` (default `.`) unless noted, and the data-returning
commands take `--json`.

```text
warpline [--version] {init,install,doctor,session-context,backfill,ingest-commit,
                      loomweave-probe,changed,timeline,churn,blast-radius,reverify,
                      capture-snapshot,dogfood-eval,mcp-smoke,productization-gate} ...
```

```bash
warpline --version
```

```text
warpline 1.0.0
```

## Two executables

The package installs two entry points:

| Executable | Defined as | Purpose |
| --- | --- | --- |
| `warpline` | `warpline.cli:main` | The CLI documented on this page. |
| `warpline-mcp` | `warpline.mcp:main` | The MCP stdio server. See the [MCP tool reference](mcp-tools.md). |

## Conventions

- `--repo PATH` selects the repository whose temporal store the command operates
  on. Default `.` (current directory).
- `--json` prints a single-line, key-sorted JSON object. Without it, the
  data-returning commands print indented JSON; `install`/`doctor` print a
  per-component report.
- The store lives at `<repo>/.weft/warpline/warpline.db` and is created on first
  use. State is git-ignored.

## Environment variables

| Variable | Default | Effect |
| --- | --- | --- |
| `WARPLINE_LOOMWEAVE_COMMAND` | `loomweave` | The loomweave executable warpline shells out to for SEI resolution and edge capture (used by `backfill`, `ingest-commit`, `loomweave-probe`, and `capture-snapshot`). It is **server/project config**, not public agent input. |

Honest scope: the env var is consulted on the **MCP** path (where the tools take
no loomweave-command argument). On the **CLI**, the corresponding flag
(`--loomweave-command`, or `--command` for `loomweave-probe`) defaults to the
literal `loomweave`, which is truthy and therefore **shadows the env var** unless
you pass the flag an explicit value. To point the CLI at a non-default loomweave,
pass the flag — setting only `WARPLINE_LOOMWEAVE_COMMAND` will not change CLI
behavior.

## Exit codes

Most commands exit `0` on success. Three commands use a non-zero exit as a signal:

| Command | `0` | `1` | `2` |
| --- | --- | --- | --- |
| `install` | all selected components applied | one or more components errored | — |
| `doctor` | all components healthy | one or more components unhealthy | — |
| `dogfood-eval` | `ready=true` | — | `ready=false` |
| `mcp-smoke` | `ok=true` | — | `ok=false` |
| `productization-gate` | `allowed=true` | — | `allowed=false` |

All other commands exit `0`. (`ingest-commit` is fail-soft by contract: it logs a
health row and still exits `0` so a git hook never blocks a commit.)

---

## Lifecycle commands

### `warpline init`

Install only the git `post-commit` ingest hook into `--repo`, and print the hook
path. A minimal alternative to `install` when you only want commit ingestion.

```bash
warpline init --repo /path/to/project
```

### `warpline install`

Wire warpline into a repository as a federation member: MCP bindings, hooks, the
agent skill, instruction blocks, and config. Idempotent, atomic, symlink-safe, and
it never clobbers a foreign member's config block.

```bash
warpline install --repo /path/to/project          # everything (default)
warpline install --repo /path/to/project --hooks   # one component only
warpline install --repo /path/to/project --json
```

With no component flag, `install` applies every component. Pass one or more flags
to apply a subset:

| Flag | Component | What it writes |
| --- | --- | --- |
| `--claude-code` | Claude Code MCP | `warpline` server entry in `<repo>/.mcp.json` (stdio). |
| `--codex` | Codex MCP | `[mcp_servers.warpline]` block in `~/.codex/config.toml`. |
| `--claude-md` | CLAUDE.md block | `warpline:instructions` block in `<repo>/CLAUDE.md`. |
| `--agents-md` | AGENTS.md block | `warpline:instructions` block in `<repo>/AGENTS.md`. |
| `--gitignore` | gitignore | `.weft/` entry in `<repo>/.gitignore`. |
| `--hooks` | git post-commit hook | fail-soft `warpline ingest-commit` post-commit hook. |
| `--session-hook` | Claude SessionStart hook | `warpline session-context` hook in `<repo>/.claude/settings.json`. |
| `--skills` | Claude Code skill | `warpline-workflow` skill into `<repo>/.claude/skills/`. |
| `--codex-skills` | Codex skill | `warpline-workflow` skill into `<repo>/.agents/skills/`. |
| `--config` | `.weft/warpline` config | `config.json` + `INSTALL_VERSION` in `<repo>/.weft/warpline/`. |

The `--json` form emits a `warpline.install.v1` object: `{schema, ok, actions[],
errors[]}`. Exit `0` if `ok`, else `1`.

### `warpline doctor`

Verify every installed component and report per-component health. `--fix`
re-applies anything fixable.

```bash
warpline doctor --repo /path/to/project          # report
warpline doctor --repo /path/to/project --fix      # autofix what it can
warpline doctor --repo /path/to/project --json
```

`--json` emits a `warpline.doctor.v1` object:
`{schema, ok, checks: [{name, ok, detail, fixable}], fixed: [{name, detail}]}`.
Exit `0` if all components are healthy, else `1`. (The git post-commit hook check
is marked unfixable when `--repo` is not a git repository.)

### `warpline session-context`

Print a one-line temporal summary for a SessionStart hook. Fail-soft: it never
raises, returning a plain status string instead.

```bash
warpline session-context --repo /path/to/project
```

```text
warpline: 5 change events tracked; no edge snapshot (impact/reverify return NO_SNAPSHOT until capture)
```

When the store is empty it prints `warpline: 0 change events tracked (run
\`warpline backfill\`)`; when a snapshot exists it names the snapshot completeness
and commit prefix.

---

## Ingestion commands

### `warpline backfill`

Walk the repository's git history and record a change event for every entity
touched in every commit. SEI resolution against loomweave is **on by default**.

```bash
warpline backfill --repo /path/to/project --json
warpline backfill --repo /path/to/project --no-resolve-sei --json   # skip loomweave
```

```json
{"commits": 2, "sei": {"absent": 0, "resolved": 0}}
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--resolve-sei` / `--no-resolve-sei` | `--resolve-sei` | Resolve SEIs via loomweave, or skip the loomweave probe entirely. Degrades cleanly when loomweave is absent. |
| `--loomweave-command CMD` | `loomweave` | The loomweave executable used for SEI resolution. |
| `--json` | off | Single-line JSON output. |

With `--json` and `--resolve-sei`, the report includes a `sei_resolution` block
from the loomweave probe.

### `warpline ingest-commit SHA`

Ingest a single commit. This is what the installed `post-commit` hook calls.
**Fail-soft by contract:** on any error it logs a `HOOK_INGEST_FAILED` health row
and exits `0`, so a git hook never blocks a commit.

```bash
warpline ingest-commit HEAD --repo /path/to/project
```

Takes the same `--resolve-sei` / `--no-resolve-sei` and `--loomweave-command`
flags as `backfill`.

### `warpline loomweave-probe`

Probe whether loomweave is reachable for this repo and report its status. Useful
for diagnosing why SEI resolution or snapshots degrade.

```bash
warpline loomweave-probe --repo /path/to/project --json
```

Reports `{status, reason, version, tools?, missing?}`. `status` is `available`
when loomweave is installed, indexed for the repo, and exposes the expected tool
set; otherwise `skipped` with a `reason` (`command_unavailable`, `no_index`,
`serve_failed`, `missing_tools`).

---

## Query commands

These return the same frozen envelopes as the matching MCP tools (see the
[MCP tool reference](mcp-tools.md) for the full `data` shapes).

### `warpline changed`

List changed entities for a revision range; returns ready-to-call `next_actions`.
**Run this first.** Schema `warpline.change_list.v1`.

```bash
warpline changed --repo /path/to/project --rev-range HEAD~1..HEAD
warpline changed --repo /path/to/project --json
```

| Flag | Meaning |
| --- | --- |
| `--rev-range RANGE` | A git revision range, e.g. `HEAD~1..HEAD`. Omit for all recorded changes. |
| `--json` | Single-line JSON. |

An invalid `--rev-range` produces a `warpline.error.v1` with `error_code:
invalid_rev_range`.

### `warpline timeline`

Ordered change history for one entity. Reports `sei_resolution` only — never a
lineage claim. Schema `warpline.entity_timeline.v1`.

```bash
warpline timeline --repo /path/to/project --entity "python:function:src/demo/auth.py::login"
```

| Flag | Meaning |
| --- | --- |
| `--entity VALUE` | (required) The entity ref — a SEI or a locator. |
| `--json` | Single-line JSON. |

### `warpline churn`

Per-entity change-event count. A never-observed entity returns `churn_count: 0`,
not an error. Schema `warpline.entity_churn_count.v1`.

```bash
warpline churn --repo /path/to/project --sei loomweave:eid:0123...  --json
warpline churn --repo /path/to/project --locator "python:function:src/demo/auth.py::login"
```

| Flag | Meaning |
| --- | --- |
| `--sei VALUE` | A SEI to count. Repeatable. |
| `--locator VALUE` | A locator to count. Repeatable. |
| `--json` | Single-line JSON. |

Mix `--sei` and `--locator` freely; results are returned for each ref.

### `warpline blast-radius`

Downstream affected set over the latest dated snapshot, with mandatory
`completeness` + `staleness`. Schema `warpline.impact_radius.v1`.

```bash
warpline blast-radius --repo /path/to/project --changed-entity-key-id 1 --depth 2 --json
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--changed-entity-key-id N` | (required) | A seed entity key id. Repeatable. |
| `--depth N` | `2` | Traversal depth, `0`–`5`. |
| `--json` | off | Single-line JSON. |

With no snapshot, returns `completeness: NO_SNAPSHOT` and an empty `affected`
list — the changed set only, not "nothing affected."

!!! note "Key ids on the CLI vs. refs over MCP"
    The CLI `blast-radius` / `reverify` seed on `--changed-entity-key-id` (the
    warpline-internal row id, handy when chaining from a `changed` result). Over
    MCP the same tools also accept `changed_refs` (`{kind, value}`, SEIs
    preferred) and a `rev_range`. The key id is **not** a federation key — see
    [SEI](../concepts/sei.md).

### `warpline reverify`

The re-verification worklist. Schema `warpline.reverify_worklist.v1`. Same seed
flags as `blast-radius`.

```bash
warpline reverify --repo /path/to/project --changed-entity-key-id 1 --depth 2 --json
```

The changed entities are always in the worklist (`reason: changed`); downstream
entities are added when a snapshot exists.

### `warpline capture-snapshot`

The only mutating query command: capture loomweave's dated edges into the local
store. Writes only `.weft/warpline/`. Schema `warpline.edge_snapshot.v1`.

```bash
warpline capture-snapshot --repo /path/to/project --json
warpline capture-snapshot --repo /path/to/project --commit HEAD~3 --json
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--commit SHA` | `HEAD` | The commit to stamp the snapshot at. |
| `--loomweave-command CMD` | `loomweave` | The loomweave executable (server/project config). |
| `--json` | off | Single-line JSON. |

With loomweave absent, returns `completeness: SKIPPED` and `source_version:
no_index` — an honest "no edges captured," not an error.

---

## Engineering / gate commands

These support development and the federation admission gates; they are not part of
the agent-facing query surface.

### `warpline mcp-smoke`

Drive the live MCP stdio server end-to-end (initialize, `tools/list`, a
`tools/call` per tool, and a bad-input case) and report pass/fail. Exit `0` if
`ok`, else `2`.

```bash
warpline mcp-smoke --repo . --json
warpline mcp-smoke --repo . --no-bad-input
```

### `warpline dogfood-eval`

Run the real change → reverify dogfood evaluator (synthetic lanes plus an optional
real-member lane against an actual loomweave index) and gate on readiness. Exit
`0` if `ready`, else `2`.

```bash
warpline dogfood-eval --json
warpline dogfood-eval --real-member-repo /path/to/member --json
warpline dogfood-eval --skip-real-member --json
```

| Flag | Meaning |
| --- | --- |
| `--output PATH` | Where to write the results JSON. |
| `--work-dir PATH` | Scratch directory for synthetic lanes. |
| `--real-member-repo PATH` | A real repo with a loomweave index to run the real-member lane against. |
| `--skip-real-member` | Skip the real-member lane (synthetic lanes only). |

### `warpline productization-gate`

Read the spike productization decision and the dogfood results, and report whether
productization is allowed. Exit `0` if `allowed`, else `2`.

```bash
warpline productization-gate --report spike/REPORT.md --dogfood-results <path>
```
