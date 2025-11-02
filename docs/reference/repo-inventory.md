---
title: Reference — repository inventory
summary: Snapshot of Hotpass packages, interfaces, orchestration flows, tests, datasets, and CI automation.
last_updated: 2025-11-02
---

This inventory highlights the moving parts that power Hotpass. Use the tables below to
jump to the relevant code, fixtures, or automation when you need to trace behaviour or
extend the platform.

## Packages and modules

| Area                      | Description                                                                                                                                       | Key entry points                                                                                                                                                                                                                                           |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pipeline execution        | Core orchestration, configuration, and reporting for the refinement pipeline, including ingestion, aggregation, validation, and publishing logic. | [`apps/data-platform/hotpass/pipeline/`](../../apps/data-platform/hotpass/pipeline/) · [`pipeline_enhanced.py`](../../apps/data-platform/hotpass/pipeline_enhanced.py) · [`pipeline_reporting.py`](../../apps/data-platform/hotpass/pipeline_reporting.py) |
| Automation delivery       | Circuit breakers, retry-aware HTTP client, and webhook/CRM hooks for downstream automation.                                                       | [`apps/data-platform/hotpass/automation/`](../../apps/data-platform/hotpass/automation/)                                                                                                                                                                   |
| Enrichment services       | Intent collectors, validators, and provider adapters for enrichment extras.                                                                       | [`apps/data-platform/hotpass/enrichment/`](../../apps/data-platform/hotpass/enrichment/)                                                                                                                                                                   |
| Entity resolution         | Probabilistic linkage runner plus Splink integration.                                                                                             | [`apps/data-platform/hotpass/linkage/`](../../apps/data-platform/hotpass/linkage/) · [`entity_resolution.py`](../../apps/data-platform/hotpass/entity_resolution.py)                                                                                       |
| Transform & scoring       | Feature engineering, scoring, and transformation helpers.                                                                                         | [`apps/data-platform/hotpass/transform/`](../../apps/data-platform/hotpass/transform/) · [`transform/scoring.py`](../../apps/data-platform/hotpass/transform/scoring.py)                                                                                   |
| Domain models             | Typed representations of contacts, organisations, telemetry payloads, and shared enums.                                                           | [`apps/data-platform/hotpass/domain/`](../../apps/data-platform/hotpass/domain/)                                                                                                                                                                           |
| Data access               | Data source adapters and persistence abstractions (Excel, parquet, Polars datasets).                                                              | [`apps/data-platform/hotpass/data_sources/`](../../apps/data-platform/hotpass/data_sources/) · [`apps/data-platform/hotpass/storage/`](../../apps/data-platform/hotpass/storage/)                                                                          |
| Configuration & profiles  | Canonical config schema, upgrade helpers, and reusable profile presets.                                                                           | [`config_schema.py`](../../apps/data-platform/hotpass/config_schema.py) · [`config_doctor.py`](../../apps/data-platform/hotpass/config_doctor.py) · [`profiles/`](../../apps/data-platform/hotpass/profiles/)                                              |
| CLI surface               | Unified CLI, progress logging, and enhanced compatibility shim.                                                                                   | [`cli/`](../../apps/data-platform/hotpass/cli/) · [`cli_enhanced.py`](../../apps/data-platform/hotpass/cli_enhanced.py)                                                                                                                                    |
| MCP & agent automation    | MCP stdio server, tool registry, and agent policy scaffolding.                                                                                    | [`mcp/server.py`](../../apps/data-platform/hotpass/mcp/server.py) · [`docs/reference/mcp-tools.md`](mcp-tools.md) · [`AGENTS.md`](../../AGENTS.md) · [`ops/agents/`](../../ops/agents/)                                                                   |
| Compliance & validation   | POPIA/ISO evidence logging, PIIs redaction, schema + expectation gates.                                                                           | [`compliance.py`](../../apps/data-platform/hotpass/compliance.py) · [`compliance_verification.py`](../../apps/data-platform/hotpass/compliance_verification.py) · [`validation.py`](../../apps/data-platform/hotpass/validation.py)                        |
| Observability & telemetry | Metric exporters, OpenTelemetry wiring, and structured logging helpers.                                                                           | [`telemetry/`](../../apps/data-platform/hotpass/telemetry/) · [`observability.py`](../../apps/data-platform/hotpass/observability.py)                                                                                                                      |
| Benchmarks & profiling    | Performance baselines for configuration merges and future orchestration hotspots.                                                                 | [`ops/benchmarks/hotpass_config_merge.py`](../../ops/benchmarks/hotpass_config_merge.py) · `dist/benchmarks/`                                                                                                                                              |

## Console scripts

| Script             | Module                                                                          | Purpose                                                                                       |
| ------------------ | ------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `hotpass`          | [`hotpass.cli:main`](../../apps/data-platform/hotpass/cli/main.py)              | Unified CLI for running the pipeline, orchestrations, deployments, dashboards, and tooling.   |
| `hotpass-enhanced` | [`hotpass.cli_enhanced:main`](../../apps/data-platform/hotpass/cli_enhanced.py) | Backwards-compatible entry point that delegates to the unified CLI with deprecation warnings. |

## Prefect flows

| Flow name                     | Definition                                                                      | Highlights                                                                                                              |
| ----------------------------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `hotpass-backfill`            | [`backfill_pipeline_flow`](../../apps/data-platform/hotpass/orchestration.py)   | Rehydrates archived inputs, reruns the pipeline for historical windows, and aggregates metrics with concurrency guards. |
| `hotpass-refinement-pipeline` | [`refinement_pipeline_flow`](../../apps/data-platform/hotpass/orchestration.py) | Primary Prefect flow that loads inputs, runs the canonical pipeline, and optionally archives outputs.                   |

## Test suites

- [ ] `tests/pipeline/` — Feature toggles, ingestion validation, and orchestrator behaviour tests.
- [ ] `tests/automation/` — HTTP client policies and webhook/CRM delivery fixtures.
- [ ] `tests/enrichment/` — Intent collectors, validators, and enrichment adapters.
- [ ] `tests/linkage/` — Entity resolution and probabilistic matching coverage.
- [ ] `tests/cli/` — Command parsing, progress reporting, and option integration tests (includes plan/research and resolve Label Studio coverage added 2025-10-31).
- [ ] `tests/data_sources/` — Reader/writer adapters and dataset helpers.
- [ ] `tests/accessibility/` — Accessibility smoke tests for dashboards and reports.
- [ ] `tests/contracts/` — Golden contracts for CLI outputs and pipeline reports.
- [ ] `tests/domain/` — Domain model invariants and schema serialisation checks.
- [ ] `tests/fixtures/` — Shared fixtures for telemetry, orchestration, and pipeline flows.

_Tick a box when reviewing or updating a suite during a docs or QA sweep._

## Data, contracts, and expectations

| Location                                         | Purpose                                                                                                | Notes                                                                                                                 |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| [`data/`](../../data/)                           | Sample raw/refined workbooks, compliance evidence, logs, and asset inventory used in tutorials and QA. | Includes compliance verification log (`data/compliance/verification-log.json`) and packaged archives produced by CI.  |
| [`contracts/`](../../contracts/)                 | Pact-like CLI contract describing required output structure.                                           | [`hotpass-cli-contract.yaml`](../../contracts/hotpass-cli-contract.yaml) captures argument and artifact expectations. |
| [`data_expectations/`](../../data_expectations/) | Great Expectations suites grouped by dataset (contact, reachout, sacaa).                               | Feed pipeline validation via [`validation.py`](../../apps/data-platform/hotpass/validation.py).                       |
| [`schemas/`](../../schemas/)                     | Canonical schema descriptors for SSOT and ingestion layers.                                            | Distributed with the package via `pyproject.toml` data-files.                                                         |

## Continuous integration workflows

| Workflow                                                                     | Trigger                              | Key stages                                                                                                                                                                     |
| ---------------------------------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [`docs.yml`](../../.github/workflows/docs.yml)                               | Docs/README changes on `main` or PRs | Sync docs extras, build HTML docs with warnings as errors, and run linkcheck.                                                                                                  |
| [`process-data.yml`](../../.github/workflows/process-data.yml)               | Push/PR to `main`                    | Full QA matrix (lint, tests, type, security, build), Docker validation, accessibility and mutation suites, fitness functions, artefact publication, and supply-chain evidence. |
| [`codeql.yml`](../../.github/workflows/codeql.yml)                           | Push/PR to `main`                    | GitHub CodeQL analysis for Python.                                                                                                                                             |
| [`secret-scanning.yml`](../../.github/workflows/secret-scanning.yml)         | Push/PR to `main`                    | Runs Gitleaks and uploads SARIF to code scanning.                                                                                                                              |
| [`copilot-setup-steps.yml`](../../.github/workflows/copilot-setup-steps.yml) | Manual or workflow file updates      | Primes uv environment, installs pre-commit, and configures Prefect for local/offline usage.                                                                                    |
| [`zap-baseline.yml`](../../.github/workflows/zap-baseline.yml)               | Manual dispatch                      | Optional Streamlit launch followed by OWASP ZAP baseline scan and report upload.                                                                                               |
