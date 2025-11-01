---
title: Marquez lineage UI quickstart
summary: Run Marquez locally to inspect the OpenLineage events emitted by Hotpass.
last_updated: 2025-12-03
---

The Hotpass pipeline now emits OpenLineage events from the CLI and Prefect
execution paths. Marquez provides a lightweight UI for browsing those events and
verifying dataset relationships end-to-end. This guide walks through running the
stack locally with Docker Compose and highlights what you should see once
lineage starts flowing.

## Bring up the observability stack

Hotpass ships a consolidated Docker Compose bundle under
[`deploy/docker/docker-compose.yml`](../../deploy/docker/docker-compose.yml)
that includes Prefect, Marquez, the backing PostgreSQL database, and the web UI
used in staging rehearsals.

1. Launch the stack from the repository root:

   ```bash
   cd deploy/docker
   docker compose up --build
   # Optional LLM sidecar used by MCP tooling:
   docker compose --profile llm up -d llm
   ```

   The compose file declares health checks for each service so `docker compose
   ps` reports `healthy` once Postgres, Marquez, and Prefect are ready. To stop
   the stack, run `docker compose down` (add `-v` to clear volumes during
   troubleshooting).

2. Open the Marquez UI at [http://localhost:3000](http://localhost:3000) once
   the `marquez` container reports `healthy`. Prefect is available at
   [http://localhost:4200](http://localhost:4200) from the same stack.

`make marquez-up` remains available for lightweight lineage checks. It wraps the
original `infra/marquez/docker-compose.yaml` stack, but the new compose bundle
keeps Prefect and the UI aligned with the evidence captured in
`dist/staging/marquez/` rehearsals.

## Configure Hotpass to emit to Marquez

Hotpass will automatically emit lineage whenever the `openlineage` client is
available. Point the emitter at your local Marquez instance by exporting these
variables before running the CLI or Prefect flows:

```bash
export OPENLINEAGE_URL="http://localhost:5000"
export HOTPASS_LINEAGE_NAMESPACE="hotpass.local"
```

The namespace defaults to `hotpass.local` if unset. Set
`HOTPASS_LINEAGE_PRODUCER` to override the producer URI advertised in events.
When you change the Marquez API port (for example via `MARQUEZ_API_PORT=5500`),
update `OPENLINEAGE_URL` accordingly.

Run a pipeline execution—either directly through the CLI
(`uv run hotpass refine ...`) or by triggering the Prefect deployments started
by the compose stack. Refresh the Marquez UI to explore the captured datasets,
jobs, and runs. The UI surfaces the same events validated by the automated
lineage integration tests.

### Expected datasets and jobs

After a successful refinement run, Marquez should list the following artefacts:

| Component                            | Expected label / pattern                            | Notes |
| ------------------------------------ | --------------------------------------------------- | ----- |
| Job                                  | `hotpass.pipeline.<profile_or_output>`              | Created via `build_pipeline_job_name` in `hotpass.orchestration`. Profile names collapse to lower case (for example `hotpass.pipeline.generic`). |
| Input datasets                       | Absolute paths to the input directory or source files (for example `/workspace/Hotpass-v2/data/aviation/input.xlsx`). | Derived by `discover_input_datasets`, so every `.xlsx`, `.csv`, `.xls`, or `.parquet` file under the input directory appears.
| Output datasets                      | Refined workbook (`dist/refined.xlsx`) and optional archive/snapshots written to `dist/`. | Emitted during `emit_complete`; archives surface when `--archive` is enabled.
| Prefect backfill deployments         | `prefect.flow.hotpass-backfill` and `prefect.flow.hotpass-refinement` | Visible once you trigger deployments from the compose stack; they reuse the same namespace configured via `HOTPASS_LINEAGE_NAMESPACE`.

If you replay archived inputs or run enrichment flows, additional datasets with
matching path prefixes appear in the graph. Use the timeline filter in Marquez
to confirm events land within your rehearsal window.

## Troubleshooting

- **No events appear**: confirm `OPENLINEAGE_URL` points to the running Marquez
  instance, the compose services are healthy, and that `HOTPASS_DISABLE_LINEAGE`
  is not set to `1`.
- **Port conflict**: override the published ports in
  [`deploy/docker/docker-compose.yml`](../../deploy/docker/docker-compose.yml)
  (for example `MARQUEZ_API_PORT=5500`) and restart the stack with
  `docker compose up`.
- **Resetting state**: run `docker compose down -v` from `deploy/docker/` to
  remove the PostgreSQL volume before starting fresh.
- **Debug service start-up**: inspect logs with `docker compose logs -f marquez`
  (or `prefect`, `marquez-db`) to spot authentication or migration errors. When
  using the `make marquez-up` target, the equivalent command is `docker compose
  -f infra/marquez/docker-compose.yaml logs -f`.

Capture screenshots of the datasets/jobs view and store them under
`dist/staging/marquez/<timestamp>/` when rehearsing for staging sign-off. The
compose stack matches the configuration referenced by those evidence bundles.
