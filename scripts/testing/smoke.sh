#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "$ROOT_DIR"

# Fast lint + smoke-tier tests with coverage for ephemeral runners
ruff check apps/web-ui
uv run pytest -m "smoke" --cov=apps/data-platform --cov-report=term-missing --cov-report=xml "$@"
uv run coverage html

pushd apps/web-ui >/dev/null
npm run test:unit
popd >/dev/null

printf '\nSmoke QA complete. HTML coverage available under htmlcov/.\n'
