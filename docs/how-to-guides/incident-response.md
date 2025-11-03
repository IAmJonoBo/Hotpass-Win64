---
title: How-to — run an incident response on Hotpass
summary: Stabilise a degraded pipeline by capturing evidence, restoring tunnels, and verifying the CLI, Prefect, and enrichment chain.
last_updated: 2025-11-03
---

# Run an incident response

Use this runbook when an operator reports failures in the refinement pipeline, Prefect deployments, or enrichment chain. You triage locally with the CLI, gather evidence for the incident log, and restore service by replaying the affected run.

## 1. Confirm access and tunnels

1. Check whether you already have live tunnels:

   ```bash
   uv run hotpass net status
   ```

2. If the status table is empty or the recorded PIDs are dead, recreate the tunnels. Forward Prefect and Marquez through the staging bastion:

   ```bash
   uv run hotpass net up \
     --via ssh-bastion \
     --host bastion.staging.internal \
     --prefect-host prefect.staging.internal \
     --marquez-host marquez.staging.internal \
     --detach \
     --label incident-$(date -u +%Y%m%dT%H%M%SZ)
   ```

3. Share the output port numbers with the on-call operator so they can inspect the UI. `hotpass net status` shows the local ports (`prefect_port`, `marquez_port`) after the tunnel starts.

## 2. Capture diagnostics

1. Run the doctor command against the reported profile to highlight environment drift:

   ```bash
   uv run hotpass doctor --profile-search-path apps/data-platform/hotpass/profiles --profile aviation
   ```

   Use `--autofix` when you can safely apply governance defaults (for example, missing `dist/` directories).

2. Gather pipeline logs or failing artefacts from the operator. Store copies under `dist/incidents/<ticket-id>/` for audit.

3. If the incident involves enrichment or provenance issues, capture the deterministic run output:

   ```bash
   uv run python ops/quality/run_qg3.py --json > dist/incidents/<ticket-id>/qg3.json
   ```

   The payload lists the enriched workbook path; attach the file to the incident record.

## 3. Reproduce the failure

1. Re-run the refinement pipeline with the profile used in production. Point `--input-dir` at a copy of the offending dataset:

   ```bash
   uv run hotpass refine \
     --profile-search-path apps/data-platform/hotpass/profiles \
     --profile aviation \
     --input-dir data/incidents/<ticket-id>/inputs \
     --output-path dist/incidents/<ticket-id>/refined.xlsx \
     --archive
   ```

   - Check the exit code. Validation or contract errors stop the command with an explanatory message. Document the failing stage in the incident log.

2. If enrichment was implicated, rerun the deterministic chain:

   ```bash
   uv run hotpass enrich \
     --input dist/incidents/<ticket-id>/refined.xlsx \
     --output dist/incidents/<ticket-id>/enriched.xlsx \
     --profile aviation \
     --allow-network=false
   ```

   Confirm the output contains the five provenance columns.

3. For orchestrated failures, inspect the Prefect deployment:

   ```bash
   uv run prefect deployment inspect hotpass-refine --json \
     > dist/incidents/<ticket-id>/prefect.json
   ```

   Verify concurrency limits, work pool binding, and parameters match the expected values in `prefect/deployments/`.

## 4. Restore service

1. Apply the fix (data correction, configuration update, or code patch). If you change configuration, rerun `uv run hotpass doctor --autofix` to ensure defaults and directories align.
2. Replay the affected run:

   ```bash
   uv run hotpass refine \
     --profile-search-path apps/data-platform/hotpass/profiles \
     --profile aviation \
     --input-dir data/incidents/<ticket-id>/inputs \
     --output-path dist/refined.xlsx \
     --archive
   ```

3. When the replay succeeds, hand the new workbook to the operator and upload the artefacts (`refined.xlsx`, `enriched.xlsx`, `prefect.json`, logs) to the shared evidence bucket.

## 5. Document and follow up

- Update `docs/operations/staging-rehearsal-plan.md` if the fix changes guardrails or deployment parameters.
- Add a line to `Next_Steps_Log.md` with the incident ID, owner, root cause, and follow-up checklist.
- File an ADR if you introduce a structural change to the pipeline or observability stack.

Closing the incident requires a green rerun, updated documentation, and recorded evidence. Automate copies of these steps in a GitHub issue template to keep future responses consistent.
