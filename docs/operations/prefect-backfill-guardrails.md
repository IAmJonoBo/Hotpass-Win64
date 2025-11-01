---
title: Prefect backfill guardrail runbook
summary: Exercise the `hotpass-backfill` deployment, confirm concurrency guardrails, and capture evidence for staging rehearsals.
last_updated: 2025-12-03
---

## Purpose

This runbook describes how to rehearse the Prefect backfill deployment prior to
a release. The goal is to prove that concurrency guardrails hold, work-pool
limits remain in effect, and staging evidence under
`dist/staging/backfill/<timestamp>/` is complete before sign-off.

## Prerequisites

- Prefect CLI authenticated against the staging server (`PREFECT_API_URL` set to
  the forwarded endpoint or the compose stack's Prefect service).
- Access to the `hotpass-e2e-staging` deployment and its work pool.
- Local checkout of the repository to run `uv` commands and collect evidence.
- Permission to upload artefacts to the shared staging evidence location
  (`dist/staging/backfill/`).

## Step-by-step rehearsal

1. **Render manifests** – ensure the latest manifests are applied. If staging
   deviates from the repo defaults, render the manifests locally to audit
   changes:

   ```bash
   uv run hotpass deploy --manifest-dir prefect/staging --flow backfill --no-upload --dry-run
   ```

2. **Inspect guardrails** – confirm the deployment still advertises the
   expected concurrency limits and parameters:

   ```bash
   uv run prefect deployment inspect hotpass-backfill --json > dist/staging/backfill/$(date -u +%Y%m%dT%H%M%SZ)/deployment.json
   ```

   Verify `concurrency_limit`, `concurrency_key`, and `parameters.pipeline.backfill`
   are unchanged. If deviations are intentional, document them in `notes.md`
   alongside the evidence export.

3. **Trigger a rehearsal run** – execute the deployment with a bounded date
   range so the guardrails engage:

   ```bash
   uv run prefect deployment run hotpass-backfill \
     --params '{"since": "2024-01-01", "until": "2024-01-07"}' \
     --watch > dist/staging/backfill/$(date -u +%Y%m%dT%H%M%SZ)/hotpass-e2e-staging.log
   ```

   Use `--work-queue` if rehearsing against a dedicated queue. The `--watch`
   flag captures the run timeline directly in the log file.

4. **Capture Prefect state** – export the run metadata and any concurrent task
   activity once the job completes:

   ```bash
   uv run prefect flow-run inspect <flow_run_id> --json \
     > dist/staging/backfill/<timestamp>/metadata.json
   ```

   Replace `<flow_run_id>` with the identifier emitted in the log. For visual
   confirmation, take a screenshot of the Prefect UI backfill run and store it as
   `dist/staging/backfill/<timestamp>/hotpass-e2e-staging.png`.

5. **Validate concurrency** – confirm only the allowed number of runs executed
   in parallel by checking the work pool history:

   ```bash
   uv run prefect work-pool inspect hotpass-backfill-pool --json \
     > dist/staging/backfill/<timestamp>/work-pool.json
   ```

   If Prefect reports queued runs beyond the configured limit, halt the release
   and raise a task in `Next_Steps.md`.

6. **Upload and log** – push the populated evidence directory (log, metadata,
   screenshot, JSON exports) to the shared repository path or evidence bucket
   and link it from `docs/operations/staging-rehearsal-plan.md`. Record the
   rehearsal details in `Next_Steps_Log.md`.

## Troubleshooting

- **Runs queue indefinitely** – verify the backfill work pool has a live worker
  and that the concurrency key is not already locked by an earlier rehearsal.
- **Concurrency exceeds limit** – update `prefect/deployments/hotpass-backfill.yaml`
  to restore guardrail values and rerun the rehearsal. Document the corrective
  action in the evidence bundle.
- **No lineage events** – ensure the Marquez stack is running (see
  [lineage smoke test runbook](lineage-smoke-tests.md)) so the backfill run emits
  OpenLineage events alongside the Prefect metadata.
