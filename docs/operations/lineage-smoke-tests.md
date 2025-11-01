---
title: Lineage smoke test runbook
summary: Validate Marquez ingestion, Prefect linkage, and evidence capture for OpenLineage rehearsals.
last_updated: 2025-12-03
---

## Purpose

Use this runbook to verify that lineage signals flow end-to-end after a deploy.
The checks cover the Docker Compose workflow, CLI lineage emission, and Prefect
integration so operators can prove Marquez reflects the latest runs.

## Prerequisites

- Docker Desktop or a compatible engine with Compose v2 support.
- Local checkout of the repository to access
  [`deploy/docker/docker-compose.yml`](../../deploy/docker/docker-compose.yml).
- Ability to run `uv` commands and the Hotpass CLI locally.
- Permission to update the `dist/staging/marquez/` evidence directory.

## Step-by-step smoke test

1. **Start the stack** – launch the Prefect + Marquez stack with Docker Compose:

   ```bash
   cd deploy/docker
   docker compose up --build -d prefect marquez hotpass-web
   ```

   Wait until `docker compose ps` marks the `marquez` and `prefect` services as
   `healthy`.

2. **Seed lineage via CLI** – in a separate shell, emit a refinement run:

   ```bash
   export OPENLINEAGE_URL="http://localhost:5000"
   export HOTPASS_LINEAGE_NAMESPACE="hotpass.local"
   uv run hotpass refine \
     --input-dir ./data \
     --output-path ./dist/refined.xlsx \
     --profile generic \
     --archive
   ```

   Confirm the command exits with `0` and that `dist/refined.xlsx` exists.

3. **Trigger Prefect linkage** – optionally run the refinement deployment from
   the compose stack to confirm Prefect also emits lineage:

   ```bash
   uv run prefect deployment run hotpass-refinement --watch
   ```

   Record the flow run identifier for evidence capture.

4. **Capture Marquez artefacts** – browse to
   [http://localhost:3000](http://localhost:3000) and record the following under
   `dist/staging/marquez/<timestamp>/`:

   - `graph.png` – screenshot of the jobs/datasets graph showing the
     `hotpass.pipeline.generic` job and the input/output nodes.
   - `runs.json` – export of `GET /api/v1/namespaces/hotpass.local/jobs/hotpass.pipeline.generic/runs`.
   - `datasets.json` – export of `GET /api/v1/namespaces/hotpass.local/datasets`.
   - `notes.md` – include the CLI command hashes and flow run identifiers used.

   Use `curl` to capture the API payloads:

   ```bash
   curl -s http://localhost:5000/api/v1/namespaces/hotpass.local/jobs/hotpass.pipeline.generic/runs \
     > dist/staging/marquez/<timestamp>/runs.json
   curl -s http://localhost:5000/api/v1/namespaces/hotpass.local/datasets \
     > dist/staging/marquez/<timestamp>/datasets.json
   ```

5. **Archive logs** – store `docker compose logs --no-color marquez` and
   `prefect` output in the same evidence directory for troubleshooting.

6. **Upload and log** – push the populated evidence directory to the shared
   repository path or evidence bucket and reference it from
   `docs/operations/staging-rehearsal-plan.md`. Capture a summary line in
   `Next_Steps_Log.md` once reviewed.

## Troubleshooting

- **Missing jobs** – ensure the CLI run completed without errors and that the
  namespace matches `HOTPASS_LINEAGE_NAMESPACE`.
- **Prefect runs absent** – the compose stack starts Prefect without
  authentication. Verify the deployment exists with `uv run prefect deployment ls`
  and rerun step 3.
- **API errors** – check `docker compose logs marquez` for database migrations or
  schema errors. Reset volumes with `docker compose down -v` if needed.
