---
title: Fitness functions and architectural guardrails
summary: Automated checks safeguarding Hotpass architecture characteristics.
last_updated: 2025-11-02
---

## Active fitness functions

| ID   | Scenario                                 | Guardrail                                                   | Implementation                     | Threshold |
| ---- | ---------------------------------------- | ----------------------------------------------------------- | ---------------------------------- | --------- |
| FF-1 | Prevent runaway pipeline complexity      | `apps/data-platform/hotpass/pipeline.py` ≤ 1200 LOC         | `ops/quality/fitness_functions.py` | Pass/fail |
| FF-2 | Ensure enhanced pipeline remains modular | `apps/data-platform/hotpass/pipeline_enhanced.py` ≤ 200 LOC | Same script                        | Pass/fail |
| FF-3 | Preserve observability instrumentation   | `BatchSpanProcessor` import required                        | Same script                        | Presence  |
| FF-4 | Guarantee public API completeness        | `__all__` exposes `run_pipeline`, `PipelineConfig`          | Same script                        | Presence  |

## Planned functions

- **Latency SLO** — Hook into Prefect metrics to ensure pipeline execution ≤ 120 seconds P95.
- **Error budget** — Track `result.quality_report.invalid_records` ratio ≤ 5% per run.
- **Coupling limit** — Use `import-linter` contract to prevent CLI modules depending on geospatial extras.
- **Chaos tolerance** — Re-run orchestrations with network faults using `pytest` + `chaoslib`.

## Execution

- Run via `.github/workflows/process-data.yml` `fitness-functions` job.
- Locally execute with `uv run python ops/quality/fitness_functions.py`.
- Raise failures as build blockers; log remediation tasks in `Next_Steps.md`.

## Governance

- Architecture board reviews thresholds quarterly.
- ADR updates to include reference to associated fitness function IDs.
- Maintain change history within this document.
