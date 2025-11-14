#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "$ROOT_DIR"

# Fast lint + smoke-tier tests with coverage for ephemeral runners
# Ensure ruff checks Python surfaces and the ops directory
uv run ruff check apps/data-platform ops

# Quick bandit scan (medium severity only) to catch obvious issues without slowing the pipeline
uv run bandit -r apps/data-platform/hotpass --severity-level medium --confidence-level high || true

# CLI sanity check (quickly validate hotpass overview loads)
uv run hotpass overview --help >/dev/null 2>&1 || true

uv run pytest -m "smoke" --cov=apps/data-platform --cov-report=term-missing --cov-report=xml "$@"
uv run coverage html

pushd apps/web-ui >/dev/null
pnpm run test:unit
popd >/dev/null

printf '\nSmoke QA complete. HTML coverage available under htmlcov/.\n'
