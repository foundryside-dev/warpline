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

Recommendation: pending
