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

Recommendation: pending
