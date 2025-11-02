---
title: Governance — pipeline gap analysis
summary: Findings from the audit-first review ahead of the online research and validation overhaul.
last_updated: 2025-11-02
---

This report captures repository context, current QA posture, and critical gaps that should be closed before the online research and validation overhaul proceeds.

## Repository context snapshot

- **Mission**: Hotpass coordinates spreadsheet ingest and orchestrated research crawlers to clean, backfill, map relationships, and publish analysis-ready outputs with Prefect orchestration, enrichment, and compliance features. (See the [project charter](project-charter.md) for programme context.)
- **Documentation system**: The docs follow the Diátaxis framework with detailed architecture, governance, security, and roadmap content under `docs/` (see [architecture overview](../explanations/architecture.md)).
- **Contribution workflow**: Contributors are expected to run the full QA suite (pytest + coverage, Ruff lint/format, mypy, Bandit, detect-secrets, build) and keep `Next_Steps.md` up to date before raising PRs.【F:README.md†L18-L37】

## Baseline QA status (2025-10-26)

| Check            | Command                                                         | Status                                                            |
| ---------------- | --------------------------------------------------------------- | ----------------------------------------------------------------- |
| Tests + coverage | `uv run pytest --cov=src --cov=tests --cov-report=term-missing` | ✅ (277 passed, 2 skipped; overall coverage 87%)【3c25ae†L1-L63】 |
| Lint             | `uv run ruff check`                                             | ✅【1eb8af†L1-L2】                                                |
| Format           | `uv run ruff format --check`                                    | ✅ (already formatted)【3b2dd9†L1-L2】                            |
| Type-check       | `uv run mypy src tests scripts`                                 | ✅ (advisory notes only)【cefa64†L1-L24】                         |
| Security         | `uv run bandit -r src scripts`                                  | ✅ (no issues)【826adc†L1-L25】                                   |
| Secrets          | `uv run detect-secrets scan src tests scripts`                  | ✅ (no findings)【febc0f†L1-L69】                                 |
| Build            | `uv run uv build`                                               | ✅ (sdist + wheel succeed)【de0834†L1-L94】                       |

Skips: Parquet-related tests remain skipped when `pyarrow` is unavailable, so coverage for Parquet code paths depends on optional extras being installed locally.【3c25ae†L39-L56】

## Key gaps and risks

### 1. CLI/orchestration duplication and exception handling

- `hotpass.cli_enhanced.cmd_orchestrate` rebuilds pipeline configuration, archive handling, and Prefect dispatch logic already implemented inside `hotpass.orchestration.refinement_pipeline_flow`, leading to duplicated behaviours and diverging error handling paths.【F:apps/data-platform/hotpass/cli_enhanced.py†L165-L255】【F:apps/data-platform/hotpass/orchestration.py†L154-L218】
- The same function and `cmd_resolve` wrap the entire execution in broad `except Exception` blocks that swallow root causes and only emit console messages, making automated recovery and monitoring difficult.【F:apps/data-platform/hotpass/cli_enhanced.py†L196-L325】

**Impact**: High risk of logic drift between CLI and Prefect workflows, inconsistent exit codes, and hard-to-diagnose failures during the overhaul.

### 2. Prefect logging monkey patch

- Importing `hotpass.orchestration` mutates Prefect’s console handler by overriding `emit` on the handler class at module import time to guard against ValueErrors.【F:apps/data-platform/hotpass/orchestration.py†L37-L71】

**Impact**: Global monkey patches can break when Prefect internals change, and they apply process-wide (even when Hotpass is imported as a library), creating maintenance and observability risks.

### 3. Deployment scheduling gap

- `hotpass.orchestration.deploy_pipeline` accepts a `cron_schedule` argument but never applies it to the Prefect deployment, so scheduled runs cannot be configured through the CLI despite the surface API suggesting otherwise.【F:apps/data-platform/hotpass/orchestration.py†L221-L245】

**Impact**: Violates the principle of least astonishment and blocks teams from automating validated schedules without manual Prefect UI changes.

### 4. Entity history ingestion safeguards

- `_load_entity_history` feeds history file columns through `ast.literal_eval`, trusting raw strings from CSV/JSON input.【F:apps/data-platform/hotpass/entity_resolution.py†L299-L333】

**Impact**: Although `literal_eval` is safer than `eval`, it will still raise exceptions or consume excessive memory on malicious input, and it expands the threat surface for ingestion of unvetted history dumps. Sanitised schema-aware parsing would be safer.

### 5. Geospatial scaling and error handling

- `calculate_distance_matrix` builds an `n x n` matrix using nested Python loops and silently returns an empty frame on any exception.【F:apps/data-platform/hotpass/geospatial.py†L315-L357】

**Impact**: O(n²) Python loops will time out on moderate datasets, while the blanket error handling hides operational issues and erodes trust in geospatial analytics.

### 6. Evidence logging coverage gap

- `hotpass.evidence` contains the compliance/export logging helpers but lacks dedicated tests (0% coverage) even though they manipulate filesystem state and timestamps that underpin compliance audit trails.

**Impact**: Regressions in audit log generation would go unnoticed; forthcoming overhaul work should introduce unit tests and deterministic timestamp strategies.

### 7. Optional dependency coverage debt

- Several critical modules (e.g., `cli_enhanced` at 45% coverage, `entity_resolution` at 73%, `geospatial` at 62%, `orchestration` at 59%) remain far below the package’s average coverage because optional extras are hard to exercise in CI.【3c25ae†L19-L57】

**Impact**: The upcoming overhaul risks destabilising under-tested code paths; targeted fixtures or dependency fakes are needed to make these modules testable without heavy installs.

## Recommended next steps

1. Consolidate CLI and Prefect orchestration logic behind a shared service layer and replace blanket exception handling with structured error propagation.
2. Replace the Prefect handler monkey patch with a local log wrapper or document an upstream change request.
3. Implement schedule/work-pool wiring in `deploy_pipeline`, with tests verifying Prefect deployment metadata.
4. Harden entity history parsing by validating schemas and removing `ast.literal_eval` in favour of typed JSON parsing.
5. Vectorise geospatial computations (e.g., use GeoPandas distance methods) and raise actionable errors instead of returning empty frames.
6. Add regression tests for evidence logging and introduce deterministic timestamp injection to support reproducible assertions.
7. Create dependency-light fixtures or feature flags so that enhanced CLI/geospatial/entity resolution code paths can be exercised in CI.

Document owners should track progress in `Next_Steps.md` and update roadmap items accordingly.

## Remediation status (2025-10-26)

- ✅ Consolidated CLI orchestration with Prefect helpers and removed blanket exception handling. The enhanced CLI now delegates to shared `PipelineRunOptions` logic and surfaces structured errors while preserving success/validation exit codes.
- ✅ Removed the Prefect console-handler monkey patch in favour of scoped logging guards inside `run_pipeline_task` and `refinement_pipeline_flow`.
- ✅ `deploy_pipeline` now applies cron schedules and work pools directly to Prefect deployment objects, ensuring automation metadata is honoured.
- ✅ Entity history parsing swaps `ast.literal_eval` for JSON-aware parsing with deterministic safeguards; regression tests cover malicious-string handling.
- ✅ Geospatial distance calculations use a vectorised haversine implementation without requiring GeoPandas and raise actionable `GeospatialError` instances.
- ✅ Evidence logging accepts deterministic clocks so audit artefacts are reproducible, with fixtures covering consent and export helpers.
- ✅ Added dependency-light orchestration, geospatial, and entity-resolution tests to raise coverage without optional extras.
