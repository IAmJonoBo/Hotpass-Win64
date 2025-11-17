# Marquez bootstrap lineage smoke (2025-11-17)

## Context
- Intended to follow the `observability/marquez-bootstrap` quickstart to validate lineage after optional dependencies landed.
- Current environment lacks packaged optional dependencies (for example `pyarrow`) and outbound package installs are blocked by the proxy, so the Hotpass CLI is not importable.
- Quickstart materials were not present under `observability/marquez-bootstrap`; used the lineage smoke test runbook in `docs/operations/lineage-smoke-tests.md` as reference for expected steps.

## Attempts
1. **Baseline lint** – `python -m ruff check` reported existing issues:
   - `scripts/benchmarks/hotpass_config_merge.py`: E731 (`lambda` assigned instead of `def`).
   - `scripts/docs_refresh.py`: E402 (import not at top of file).
2. **Smoke tests** – `python -m pytest -m "smoke"` failed during module import because `pyarrow` is missing when `hotpass.formatting` runs `_ensure_pyarrow_parquet_format()`.
3. **Dependency install** – `python -m pip install -e ".[dev,orchestration]"` failed with HTTP 403 proxy errors while trying to resolve `setuptools`, leaving `pyarrow` unavailable.

## Outcome
- Marquez stack was not started and no Hotpass runs were executed.
- No Prefect/Marquez run ID or lineage graph could be generated.
- Errors are captured above for reference; rerun is blocked until optional dependencies can be installed offline or proxy access is restored.

## Next steps
- Provision `pyarrow` (and other extras) locally or via an allowlisted cache, then reinstall the project extras.
- Re-run the lineage smoke test using the runbook in `docs/operations/lineage-smoke-tests.md` and persist the resulting run ID, API exports, and graph captures to `docs/lineage/`.
