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
uv run pytest "$@"
uv run coverage html
uv run python tools/coverage/report_low_coverage.py coverage.xml --min-lines 5 --min-branches 0

mypy apps/data-platform/hotpass/pipeline/config.py \
	apps/data-platform/hotpass/pipeline/orchestrator.py \
	ops/quality/fitness_functions.py
bandit -r apps/data-platform ops
python -m detect_secrets scan apps/data-platform tests ops
pre-commit run --all-files --show-diff-on-failure
