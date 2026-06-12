# Heddle Spike Report

## Q1: Loomweave Read Path

Status: available.

Evidence from `uv run heddle loomweave-probe --repo /home/john/loomweave --json`:

```json
{
  "status": "available",
  "version": "loomweave 1.1.0-rc4",
  "required_tools_present": [
    "project_status_get",
    "entity_find",
    "entity_resolve",
    "entity_neighborhood_get",
    "entity_callers_list",
    "entity_source_get"
  ]
}
```

The live tool inventory also includes `entity_high_churn_list` and `entity_recent_change_list`, which are relevant to later pairwise integration but remain Loomweave-owned current-structure/read-surface behavior.

## Q1b: Edge Snapshot Adapter

Unit evidence confirms Heddle preserves caller/callee direction from Loomweave neighborhood payloads. Live evidence confirms `/home/john/loomweave` exposes `entity_neighborhood_get`; Heddle still records dated snapshots only and does not answer current structure as its own authority.

## Q2: Snapshot Honesty and Planted-Change Results

The spike harness uses a bounded planted git repository for repeatable measurements and live member checks only for lightweight federation surface probes. An earlier unbounded live-member backfill attempt against `/home/john/filigree` exceeded four minutes, so the release harness was refactored to avoid making Heddle harder to operate than current grep/manual workflows.

Current measured evidence from `spike/measurements.json`:

- `changed_latency_ms`: 48.793924
- `backfill_events_per_second`: 24.52472433106239
- `hook_ingest_exit_code`: 0
- `planted_recall`: 1.0
- `snapshot_completeness`: `NO_SNAPSHOT`

The planted-change query returned `python:function:planted.py::planted` for `HEAD~1..HEAD`, with absent SEI and edge enrichment reported explicitly rather than hidden.

## Q3: Doctrine Firewall Checklist

- Heddle imports no sibling packages.
- Heddle stores temporal change and dated snapshot facts only.
- Heddle does not own current structure, work state, trust policy, governance, or requirements.
- Member dirty state is compared against `docs/evidence/member-dirty-baseline.txt`.
- Missing graph enrichment produces `NO_SNAPSHOT`, `SKIPPED`, or absent enrichment fields.

## Q4: Grep-Test Dogfood Notes

The bounded spike path is already more agent-friendly than manual grep for the planted corpus: `heddle changed --rev-range HEAD~1..HEAD --json` returns structured entity-level change facts with actor, commit, locator, path, and enrichment state. Full live-member historical backfill is not yet acceptable as a release-gate operation and must remain outside the fast harness until incremental or bounded ingestion is implemented.

Recommendation: go
