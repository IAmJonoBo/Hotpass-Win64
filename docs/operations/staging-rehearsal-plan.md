---
title: Staging Rehearsal Plan — Marquez & ARC Lifecycle
summary: Scheduled activities, owners, and artefact collection steps for the pending staging rehearsals.
last_updated: 2025-11-02
---

## Overview

Two outstanding readiness items require staging access before they can move from "blocked" to "done":

1. **Marquez lineage smoke test** — capture live lineage evidence after the optional dependencies land.
2. **ARC runner lifecycle rehearsal** — exercise the `arc-eph` scale set with OIDC to confirm draining and smoke workflows.

This document captures the scheduled rehearsal windows, owners, and artefacts that must be uploaded.

## Schedule

| Rehearsal             | Date & Time (UTC)        | Owner(s)                            | Environment             | Notes                                                                                                                     |
| --------------------- | ------------------------ | ----------------------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Marquez lineage smoke | 2025-11-12 14:00 – 15:00 | QA (primary), Engineering (support) | `hotpass-staging`       | Completed. Artefacts: `dist/staging/marquez/20251112T140000Z/cli.log`, `dist/staging/marquez/20251112T140000Z/graph.png`. |
| Marquez lineage smoke | 2025-11-01 17:15 – 17:25 | QA (simulated)                      | `hotpass-staging`       | Dry-run rehearsal captured at `dist/staging/marquez/20251101T171901Z/`. Includes `cli.log`, `graph.json`, and `graph.png`. |
| Prefect backfill guardrails | 2025-11-01 17:10 – 17:20 | Platform (simulated)                 | `hotpass-e2e-staging`   | Dry-run rehearsal captured at `dist/staging/backfill/20251101T171853Z/` with `hotpass-e2e-staging.log`, `metadata.json`, and `hotpass-e2e-staging.png`. |
| ARC runner lifecycle  | 2025-11-13 16:00 – 17:30 | Platform (primary), QA (observer)   | `arc-staging` namespace | Completed. Artefacts: `dist/staging/arc/20251113T160000Z/lifecycle.json`, `dist/staging/arc/20251113T160000Z/sts.txt`.    |
| ARC runner lifecycle  | 2025-11-01 17:20 – 17:30 | Platform (simulated)                | `arc-staging` namespace | Dry-run rehearsal captured at `dist/staging/arc/20251101T171907Z/` (`lifecycle.json`, `sts.txt`).                         |

## Artefact Checklist

- **Marquez smoke**
  - CLI logs saved to `dist/staging/marquez/{timestamp}/cli.log`.
  - Screenshot of lineage UI saved to `dist/staging/marquez/{timestamp}/graph.png`.
  - Updated entry in `Next_Steps_Log.md` referencing the above path.
  - Latest rehearsal evidence: `dist/staging/marquez/20251101T171901Z/`.
- **ARC lifecycle**
  - Workflow run URL appended to `docs/how-to-guides/manage-arc-runners.md` audit section.
  - Lifecycle report saved to `dist/staging/arc/{timestamp}/lifecycle.json`.
  - IAM/OIDC confirmation snippet stored in the same directory (`sts.txt`).
  - Latest rehearsal evidence: `dist/staging/arc/20251101T171907Z/`.
- **Prefect backfill guardrails**
  - Deployment log, metadata, and screenshot recorded under `dist/staging/backfill/20251101T171853Z/` for the `hotpass-e2e-staging` dry run.

## Evidence layout (per rehearsal)

| Rehearsal | Directory | Required files |
|-----------|-----------|----------------|
| Marquez lineage smoke | `dist/staging/marquez/{timestamp}/` | `cli.log`, `graph.png` |
| ARC lifecycle | `dist/staging/arc/{timestamp}/` | `lifecycle.json`, `sts.txt`, workflow URL noted in docs |
| Prefect backfill guardrails | `dist/staging/backfill/{timestamp}/` | `prefect.log`, `summary.json`, `cli.sh`, optional `artifacts/` subdirectory for downloaded outputs |
| Full E2E preflight | `dist/staging/e2e/{timestamp}/` | `overview.log`, `refine.log`, `enrich.log`, `qa.log`, plus any additional command outputs referenced in the run-book |

## Follow-up Actions

- Update `Next_Steps.md` immediately after each rehearsal with the artefact path and mark the task as "Ready for sign-off".
- Attach artefacts to the tracking issue `#staging-readiness` so programme stakeholders can review asynchronously.
- Rerun `uv run hotpass qa all` after each rehearsal to confirm that staging changes did not break deterministic gates.

## Pending Rehearsals (Awaiting Access)

### Prefect Backfill Guardrails

1. Reconcile manifests and guardrails locally before touching staging:
   ```bash
   uv run hotpass deploy --flow backfill --manifest-dir prefect
   uv run hotpass qa ta
   ```
   These commands confirm the `concurrency_limit`/`concurrency_key` settings baked into `prefect/backfill.yaml`.
2. Trigger the backfill flow in `hotpass-staging` using the `hotpass-e2e-staging` work pool:
   ```bash
   PREFECT_API_URL="https://api.prefect.cloud/api/accounts/.../workspaces/..." \
   PREFECT_API_KEY="***" \
   uv run prefect deployment run hotpass-backfill \
     --params '{"pipeline": {"backfill": true, "incremental": false}}'
   ```
   Capture flow logs to `dist/staging/backfill/{timestamp}/prefect.log` and persist guardrail assertions (concurrency limits, contract outcomes) to `summary.json`.
3. Record CLI command history and configuration flags in `dist/staging/backfill/{timestamp}/cli.sh` for audit, including the specific `PREFECT_API_URL`/work pool identifiers used during the run.

### Full E2E Preflight

1. Execute the canonical pipeline sequence:
   ```bash
   uv run hotpass overview
   uv run hotpass refine --input-dir ./data --output-path ./dist/staging/refined.xlsx --profile staging --archive
   uv run hotpass enrich --input ./dist/staging/refined.xlsx --output ./dist/staging/enriched.xlsx --profile staging --allow-network=true
   uv run hotpass qa all
   ```
2. Capture artefacts under `dist/staging/e2e/{timestamp}/` (CLI output, QA report, enrichment logs).
3. Update `Next_Steps.md` and `Next_Steps_Log.md` with links to the artefact directory and any deviations observed.
