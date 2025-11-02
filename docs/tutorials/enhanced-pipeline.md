---
title: Tutorial — orchestrate the enhanced pipeline
summary: Enable Hotpass orchestration, enrichment, and observability features using Prefect and OpenTelemetry.
last_updated: 2025-11-02
---

Follow this tutorial to move from the single-command pipeline to a production-ready deployment that orchestrates flows, enriches records, and publishes telemetry. You should complete the [quickstart tutorial](./quickstart.md) first.

## 1. Install the enhanced extras

Install the feature extras that power orchestration, enrichment, compliance, and dashboards.

```bash
uv sync --extra dev --extra docs --extra orchestration --extra enrichment --extra geospatial --extra compliance --extra dashboards
```

Verify that Prefect and OpenTelemetry imports succeed:

```bash
uv run python -c "import prefect, opentelemetry"
```

## 2. Configure an orchestration profile

1. Duplicate `config/pipeline.example.yaml` to `config/pipeline.prefect.yaml`.
2. Update the file with:
   - `profile: aviation` or another industry profile.
   - `orchestration.enabled: true`.
   - Storage paths for `dist_dir` and `archive_dir` if you run from CI.

```yaml
orchestration:
  enabled: true
  prefect:
    flow_name: hotpass
    work_pool: default-agent-pool
    description: Nightly SSOT refresh
```

## 3. Register the flow with Prefect

```bash
uv run hotpass deploy --name hotpass-prod --profile aviation --schedule "0 2 * * *"
```

The deploy command:

- Creates a Prefect deployment with retries and logging preconfigured.
- Packages the project using the local repository as the source.
- Schedules nightly runs at 02:00 UTC.

Confirm the deployment in the Prefect UI and trigger a manual run to validate connectivity.

## 4. Stream telemetry

Hotpass emits OpenTelemetry metrics and traces when observability is enabled.

```bash
uv run hotpass orchestrate --profile aviation --enable-observability
```

By default the exporter writes to stdout. To ship metrics to another backend, set environment variables before the run:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="https://otel-gateway.example.com"
export PREFECT_LOGGING_EXTRA_LOGGERS="hotpass"
```

## 5. Enrich and deduplicate data

Augment the orchestration run with enrichment and entity-resolution capabilities:

```bash
uv run hotpass orchestrate \
  --profile aviation \
  --enable-entity-resolution \
  --enable-enrichment \
  --enable-geospatial \
  --archive
```

The flow injects Splink-based deduplication, enrichment connectors, and geospatial clustering in the correct sequence. Review the Prefect task logs and the generated quality report to confirm each stage executed as expected.

```{tip}
Use the Prefect UI to compare runtime, row counts, and validation failures across runs. This makes it easy to detect regression when enabling new enrichment connectors.
```

## 6. Monitor the dashboard

Launch the Streamlit dashboard locally to visualise pipeline health:

```bash
uv run hotpass dashboard --port 8501
```

The dashboard surfaces throughput, error rates, and enrichment coverage so stakeholders can assess data quality without reading logs.

You now have an orchestrated workflow with observability and enrichment. Continue with the how-to guides to configure validation thresholds and formatting rules for your organisation.
