#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "$ROOT_DIR"

# Aggregate lint/format checks via Trunk when available.
if [[ ${TRUNK_SKIP_TRUNK:-0} != "1" ]]; then
	TRUNK_ALLOW_MISSING="${TRUNK_ALLOW_MISSING:-1}" \
		TRUNK_FMT_MODE="${TRUNK_FMT_MODE:-check}" \
		TRUNK_UPSTREAM="${TRUNK_UPSTREAM:-origin/main}" \
		scripts/testing/trunk_check.sh
fi

# Comprehensive suite (lint, coverage, security) for scheduled/nightly runs
# Use -n auto for parallel execution with pytest-xdist
if uv run python -c "import xdist" >/dev/null 2>&1; then
	echo "[testing] Detected pytest-xdist; running in parallel."
	uv run pytest -n auto "$@"
else
	echo "[testing] pytest-xdist not available; falling back to serial pytest run."
	uv run pytest "$@"
fi
uv run coverage html
uv run python tools/coverage/report_low_coverage.py coverage.xml --min-lines 5 --min-branches 0

uv run mypy \
	apps/data-platform/hotpass/pipeline/config.py \
	apps/data-platform/hotpass/pipeline/orchestrator.py \
	ops/quality/fitness_functions.py
uv run bandit -r apps/data-platform ops --severity-level medium --confidence-level high
uv run python -m detect_secrets scan \
  --exclude-files '(pnpm-lock\.yaml$|scancode-sample\.json$)' \
  apps docs infra ops scripts src tests tools
uv run pre-commit run --all-files --show-diff-on-failure
