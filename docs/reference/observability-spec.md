---
title: Reference — observability specification
summary: Configure tracing, metrics, lineage, and dashboards for Hotpass runs across local and orchestrated environments.
last_updated: 2025-11-03
---

# Observability specification

Hotpass instruments every refinement run so you can trace pipeline stages, record metrics, and inspect lineage. Use this reference when you wire the platform into staging or production monitoring stacks.

## Components

- **OpenTelemetry instrumentation** lives in `apps/data-platform/hotpass/telemetry/`. The helper in `observability.initialize_observability()` builds the tracer and meter using `TelemetryRegistry`.
- **CLI flags** (`apps/data-platform/hotpass/cli/shared.py`) expose telemetry settings for every command:  
  - `--telemetry-exporter {console,otlp,noop}` (repeatable)  
  - `--telemetry-otlp-endpoint` and `--telemetry-otlp-metrics-endpoint`  
  - `--telemetry-otlp-header KEY=VALUE` (repeatable)  
  - `--telemetry-otlp-insecure` / `--telemetry-otlp-secure`  
  - `--telemetry-resource-attr KEY=VALUE` to tag runs with workspace metadata.
- **Metrics** stream through `PipelineMetrics` (`telemetry/metrics.py`) and include record counts, quality scores, and stage durations (`load_seconds`, `aggregation_seconds`, `expectations_seconds`, `write_seconds`).
- **Trace spans** wrap ingestion through export. `pipeline/base.py` publishes structured events (`PIPELINE_EVENT_*`) so traces correlate with CLI console output.
- **Lineage**: `apps/data-platform/hotpass/lineage.py` emits OpenLineage events consumed by Marquez. The CLI enables it automatically when you pass `--observability` or when the profile sets `observability: true`.
- **Dashboards**: `apps/data-platform/hotpass/dashboard.py` renders the Streamlit control panel backed by artefacts in `dist/` (quality reports, coverage, enriched outputs).

## Local setup

1. **Console exporters**

   ```bash
   uv run hotpass refine \
     --telemetry-exporter console \
     --telemetry-resource-attr run.kind=local-test \
     --profile-search-path apps/data-platform/hotpass/profiles \
     --profile aviation \
     --input-dir data \
     --output-path dist/refined-local.xlsx
   ```

   The command writes spans to stdout and records metrics in-memory. Use this mode when you only need quick feedback.

2. **OpenTelemetry collector**

   ```bash
   uv run hotpass enrich \
     --telemetry-exporter otlp \
     --telemetry-otlp-endpoint localhost:4317 \
     --telemetry-otlp-metrics-endpoint localhost:4317 \
     --telemetry-resource-attr env=staging team=platform \
     --profile-search-path apps/data-platform/hotpass/profiles \
     --profile aviation \
     --allow-network=false \
     --input dist/refined.xlsx \
     --output dist/enriched.xlsx
   ```

   Run an OTLP collector locally (`docker run otel/opentelemetry-collector`) or point to your staging collector. Add `--telemetry-otlp-header authorization=Bearer <token>` if the collector requires auth.

3. **Shutdown**

   When you embed Hotpass in long-running services, call `hotpass.observability.shutdown_observability()` at shutdown so exporters flush buffered spans and metrics.

## Production wiring checklist

| Surface | Recommended exporter | Notes |
| ------- | -------------------- | ----- |
| CLI workers | `otlp` | Forward to the shared collector; set `--telemetry-environment production`. |
| Prefect deployments | `otlp` + `resource_attr` | Use deployment-specific attributes (`deploy.refine=true`). Configure via profile `options.telemetry_exporters`. |
| Streamlit dashboard | `console` | The dashboard reads artefacts from `dist/`, so tracing is optional. Focus on occupancy metrics delivered by Prefect. |
| Agents (MCP server) | `noop` | MCP tools run inside hosted sandboxes; disable exporters unless the provider guarantees outbound OTLP connectivity. |

## Marquez lineage

- Start the Docker compose stack (`make marquez-up`), which publishes Marquez on port 5000.
- Enable lineage in your profile (`features.observability = true`) or pass `--observability`.
- Each pipeline run writes OpenLineage events to the configured endpoint. Inspect the run via `apps/data-platform/hotpass/cli/commands/lineage.py` or open the Marquez UI through the `hotpass net` tunnel.

## Dashboards and alerts

- `apps/data-platform/hotpass/dashboard.py` reads refined outputs, quality reports, and enrichment artefacts from `dist/`. It mirrors the CLI run results, so ensure your incident response process copies artefacts there.
- Expose key ratios (records processed, quality score mean, intent signal count) via OTLP metrics and ship them into your APM:

  ```python
  from hotpass.observability import get_pipeline_metrics

  metrics = get_pipeline_metrics()
  metrics.record_records_processed(len(result.refined), source="base_pipeline")
  metrics.update_quality_score(result.quality_report.data_quality_distribution["mean"])
  ```

## Operational guardrails

- Profiles can disable observability explicitly (`observability: false`), which is useful in air-gapped environments.
- `ops/net/tunnels.py` stores active tunnel metadata under `~/.config/hotpass/tunnels.json`. Clean up stale sessions with `uv run hotpass net down --all` once you close your investigation.
- The docs build checks for stale diagrams and references; update `docs/reference/observability-spec.md` whenever you add a new exporter or change telemetry defaults.

With these settings in place you can trace every refinement, follow lineage relationships in Marquez, and monitor key metrics through your collector of choice.
