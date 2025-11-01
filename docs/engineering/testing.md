# Hotpass Testing & Coverage Strategy (2025-11 Refresh)

This document captures the tiered test strategy used by CI and local agents. It is intended for
operators running inside ephemeral ARC runners, Copilot/Codex agents, and engineers executing
smoke or full regression suites.

## Test Tiers

| Tier   | Invocation                               | What Runs                                                                 | Target Runtime |
|--------|-------------------------------------------|---------------------------------------------------------------------------|----------------|
| Smoke  | `scripts/testing/smoke.sh` or `make qa`   | Ruff formatting + lint, `pytest -m "smoke"`, coverage HTML/XML            | < 5 minutes    |
| Full   | `scripts/testing/full.sh` or `make qa-full` | Ruff, full `pytest`, coverage HTML/XML, mypy, bandit, detect-secrets, pre-commit | < 45 minutes   |
| Gates  | `workflow: quality-gates` nightly         | Quality Gate checks (QG-1…5) plus Playwright e2e matrix                   | < 60 minutes   |
| Nightly E2E | `workflow: playwright-nightly`       | Playwright chromium journey tests with traces & HTML report               | < 40 minutes   |

**Smoke selection** is marker-based:

- Add `@pytest.mark.bandwidth("smoke")` (or module-level `pytestmark = pytest.mark.bandwidth("smoke")`) to
  designate deterministic, lightweight tests.
- All remaining tests fall back to `bandwidth("full")` automatically via `pytest_collection_modifyitems`.
- The smoke tier is what runs on every PR in `.github/workflows/ci-smoke.yml`.

## Coverage Expectations

- Python: `coverage report --fail-under=70` for smoke, `--fail-under=80` for nightly/full runs.
- Web UI: Vitest thresholds enforced via `vitest.config.ts` (60% statements/lines/functions, 50% branches).
- Coverage artefacts (`coverage.xml`, `htmlcov/`, `apps/web-ui/coverage/unit/`) are uploaded by CI.

## CI Layout

1. `.github/workflows/ci-smoke.yml` (PRs & pushes)
   - Python smoke suite with coverage
   - Vitest unit suite with coverage
   - Artifacts: `python-smoke-coverage`, `web-unit-coverage`
2. `.github/workflows/quality-gates.yml` (main + nightly)
   - Full pytest run (`scripts/testing/full.sh`)
   - Quality Gate checks (QG-1 … QG-5)
   - Playwright e2e shard
3. `.github/workflows/playwright-nightly.yml`
   - Scheduled Playwright run for additional assurance

## Helpful Commands

```bash
# Fast feedback on a branch
scripts/testing/smoke.sh

# Full regression before a release
scripts/testing/full.sh

# Vitest coverage in isolation
cd apps/web-ui && npm run test:unit

# Playwright e2e locally (will reuse the Vite dev server)
cd apps/web-ui && npm run test:e2e
```

## Adding New Tests

- **Python**: Prefer `pytest.mark.bandwidth("smoke")` for deterministic, fixture-light tests. Long-running or
  network-dependent tests should be left unmarked (default `full`).
- **Web UI**: For component logic, add Vitest suites in `apps/web-ui/src/**/*.{test,spec}.ts[x]`. For UX-level
  flows, extend Playwright specs under `apps/web-ui/tests/`.
- **Coverage Gaps**: If `coverage report` flags `< 70%` lines for a file, add targeted unit tests before merging.

## Ephemeral Runner Tips

- Both smoke and full scripts pin `PYTEST_ADDOPTS=--max-worker=2` implicitly via CI to reduce memory pressure.
- `uv sync` caches are keyed off `uv.lock`; avoid touching the lock file unless dependencies change.
- Playwright workers are capped to 2 in CI (`playwright.config.ts`) to stay within GitHub-hosted runner limits.
