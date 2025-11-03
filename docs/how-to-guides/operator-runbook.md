---
title: How-to — operate Hotpass day to day
summary: Run imports, track approvals, and monitor telemetry using the CLI and web surfaces.
last_updated: 2025-11-03
---

# Operate Hotpass day to day

This runbook guides operators through the core workflow: ingesting workbooks, reviewing contracts, and responding to quality signals.

```{mermaid}
graph LR
    A[Prepare workbooks] --> B[uv run hotpass refine]
    B --> C[uv run hotpass enrich]
    C --> D[uv run hotpass contracts]
    C --> E[uv run hotpass qa all]
    D --> F[Contracts / dist/<case-id>/contracts]
    E --> G[Quality reports / dist/<case-id>/reports]
    C --> H[Streamlit dashboard]
    B --> I[Lineage events]

    classDef step fill:#fff3cd,stroke:#333,stroke-width:2px
    classDef artifact fill:#d4edda,stroke:#333,stroke-width:2px

    class A,B,C,D,E,H,I step
    class F,G artifact
```

## 1. Prepare data and profiles

1. Place your workbook(s) under `data/<case-id>/`. Keep only the files you intend to process; the CLI ingests every supported spreadsheet in the target directory.
2. Choose the correct profile. List bundled profiles with:

   ```bash
   ls apps/data-platform/hotpass/profiles
   ```

   Use `generic.yaml` for baseline runs or sector-specific profiles such as `aviation.yaml`.

## 2. Refine the workbook

Run the pipeline with archiving enabled so you have a timestamped package for audits:

```bash
uv run hotpass refine \
  --profile-search-path apps/data-platform/hotpass/profiles \
  --profile aviation \
  --input-dir data/<case-id> \
  --output-path dist/<case-id>/refined.xlsx \
  --archive
```

- Watch the console for validation or contract errors. The pipeline stops on failures and prints the affected sheet or expectation.
- Inspect `dist/<case-id>/reports/` for the Great Expectations summary referenced in QA reviews.
- Hotpass automatically deduplicates primary-key collisions (for example the SACAA workbook) and
  writes the dropped rows to `dist/contract-notices/<run-id>/`. Review the exported CSV and feed
  the corrections back to data owners once the pipeline finishes.

## 3. Enrich deterministically

```bash
uv run hotpass enrich \
  --input dist/<case-id>/refined.xlsx \
  --output dist/<case-id>/enriched.xlsx \
  --profile aviation \
  --allow-network=false
```

- Confirm the provenance columns exist in the enriched workbook. The enrichment gate requires them, and operators rely on the metadata when approving changes.
- Enable network enrichment only after compliance approval:

  ```bash
  export FEATURE_ENABLE_REMOTE_RESEARCH=1
  export ALLOW_NETWORK_RESEARCH=1
  uv run hotpass enrich ... --allow-network=true
  ```

## 4. Review contracts and approvals

- Generate contracts for downstream systems:

  ```bash
  uv run hotpass contracts emit \
    --profile aviation \
    --format yaml \
    --output dist/<case-id>/contracts/aviation.yaml
  ```

- Use the web UI (Contracts Explorer) or open the YAML in your editor to confirm mappings and required fields.
- Record approvals or follow-ups in `docs/governance/data-governance-navigation.md` so the governance ledger stays current.

## 5. Monitor telemetry

1. Establish tunnels to Prefect and Marquez if you do not already have them:

   ```bash
   uv run hotpass net up --via ssh-bastion --host bastion.staging.internal --detach
   ```

2. Open the Streamlit dashboard:

   ```bash
   uv run hotpass dashboard
   ```

   The dashboard reads the artefacts you just generated and highlights QA status, enrichment coverage, and provenance summaries.

3. Inspect lineage in the Marquez UI using the forwarded port printed by `hotpass net status`.

## 6. Respond to quality gates

- Run `uv run hotpass qa all` to confirm CLI integrity, data quality, contracts, and documentation checks remain green. Logs point to failing steps if regressions slip in.
- For incidents, follow `docs/how-to-guides/incident-response.md` and capture artefacts under `dist/incidents/<ticket-id>/`.

## 7. Hand off

- Upload `dist/<case-id>/refined.xlsx`, `.../enriched.xlsx`, generated contracts, and quality reports to the shared evidence bucket.
- Update the release or support ticket with a link to the artefacts; include the CLI commands you ran plus any deviations (for example, enrichment retries).
- Record outstanding issues in `Next_Steps_Log.md`.

Keep this runbook open while you operate. Update it whenever you add a new approval surface, change enrichment policies, or adjust the QA flow.
