#!/usr/bin/env bash
set -euo pipefail

bash scripts/check_no_member_diffs.sh

tmp_repo="$(mktemp -d)"
trap 'rm -rf "$tmp_repo"' EXIT
git -C "$tmp_repo" init >/dev/null
git -C "$tmp_repo" config user.email agent@example.test
git -C "$tmp_repo" config user.name Agent
printf 'def planted():\n    return 1\n' >"$tmp_repo/planted.py"
git -C "$tmp_repo" add planted.py
git -C "$tmp_repo" commit -m 'planted initial' >/dev/null
printf 'def planted():\n    return 2\n' >"$tmp_repo/planted.py"
git -C "$tmp_repo" commit -am 'planted change' >/dev/null

uv run heddle loomweave-probe --repo /home/john/loomweave --json >/tmp/heddle-loomweave-probe.json

start_ns="$(date +%s%N)"
uv run heddle backfill --repo "$tmp_repo" --json >/tmp/heddle-backfill.json
backfill_ns="$(( $(date +%s%N) - start_ns ))"

start_ns="$(date +%s%N)"
uv run heddle changed --repo "$tmp_repo" --rev-range HEAD~1..HEAD --json >/tmp/heddle-planted-changed.json
changed_ns="$(( $(date +%s%N) - start_ns ))"

hook_exit=0
uv run heddle ingest-commit HEAD --repo "$tmp_repo" >/tmp/heddle-hook-ingest.json || hook_exit="$?"

planted_hits="$(python - <<'PY'
import json
payload = json.load(open('/tmp/heddle-planted-changed.json', encoding='utf-8'))
print(sum(1 for row in payload.get('changed', []) if row.get('path') == 'planted.py'))
PY
)"

python - <<PY
import json
import os
from pathlib import Path
backfill_ns = int("$backfill_ns")
changed_ns = int("$changed_ns")
planted_hits = int("$planted_hits")
payload = {
    "changed_latency_ms": changed_ns / 1_000_000,
    "backfill_events_per_second": None if backfill_ns == 0 else 2 / (backfill_ns / 1_000_000_000),
    "hook_ingest_exit_code": int("$hook_exit"),
    "planted_recall": 1.0 if planted_hits > 0 else 0.0,
    "snapshot_completeness": "NO_SNAPSHOT",
}
Path("/tmp/heddle-measurements.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
target = Path("spike/measurements.json")
if not target.exists() or os.environ.get("HEDDLE_UPDATE_SPIKE_MEASUREMENTS") == "1":
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

uv run pytest tests -v
bash scripts/check_no_member_diffs.sh
