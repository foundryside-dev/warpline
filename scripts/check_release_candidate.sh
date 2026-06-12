#!/usr/bin/env bash
set -euo pipefail

git diff --quiet
git diff --cached --quiet
bash scripts/check_no_member_diffs.sh
bash scripts/run_spike.sh
uv run heddle dogfood-eval --output /tmp/heddle-dogfood-results.json --json >/tmp/heddle-dogfood-results-run.json
uv run heddle productization-gate --report spike/REPORT.md
uv run ruff check .
uv run mypy src/heddle
uv run pytest tests -v
git diff --quiet
git diff --cached --quiet
