---
title: How-to — run the Hotpass E2E pipeline
summary: Offline-first walkthrough covering refinement, enrichment, QA, lineage review, and Prefect orchestration.
last_updated: 2025-11-07
---

Follow this guide to execute the canonical Hotpass workflow end-to-end on your laptop. The sequence mirrors the staging rehearsals and keeps everything self-hosted unless you explicitly enable network access.

## 0. Prerequisites

1. Install uv, docker, docker compose, and Prefect 3 CLI.
2. Clone the repository and create the sample Reachout workbook for offline testing:

   ```bash
   git clone https://github.com/IAmJonoBo/Hotpass.git
   cd Hotpass
   ```

3. Bring up the local infrastructure stack:

   ```bash
   cd deploy/docker
   docker compose up -d --build
   docker compose --profile llm up -d           # optional Ollama sidecar
   cd ../..
   ```

4. Import the ready-made Prefect profile:

   ```bash
   prefect profile import prefect/profiles/local.toml
   prefect profile use hotpass-local
   ```

5. Generate a local `.env` file:

   ```bash
   uv run hotpass env --target local \
     --prefect-url http://127.0.0.1:4200/api \
     --openlineage-url http://127.0.0.1:5002/api/v1 \
     --include-credentials --force
   ```

Source the file before running the steps below (`set -a; source .env.local; set +a`).

## 1. Refinement pipeline

```bash
uv run hotpass refine \
  --input-dir ./data/e2e \
  --output-path ./dist/e2e/refined.xlsx \
  --profile generic \
  --expectation-suite reachout_organisation \
  --archive
```

Outputs:
- `dist/e2e/refined.xlsx` — clean workbook.
- `dist/data-docs/index.html` — Great Expectations artifacts.
- `dist/e2e/refined-*.zip` — archived bundle.

## 2. Deterministic enrichment (offline)

```bash
uv run hotpass enrich \
  --input ./dist/e2e/refined.xlsx \
  --output ./dist/e2e/enriched.xlsx \
  --profile generic \
  --allow-network=false
```

This stage adds lookup-based metadata and keeps provenance in the workbook without touching the network.

## 3. Research planning (optional network)

```bash
uv run hotpass plan research \
  --dataset ./dist/e2e/refined.xlsx \
  --row-id 0 \
  --json \
  --output ./dist/e2e/plan.json \
  --allow-network=false
```

When you are ready to leverage SearXNG or other providers, set `--allow-network=true` and ensure `FEATURE_ENABLE_REMOTE_RESEARCH=1` is exported.

## 4. QA gates

```bash
uv run hotpass qa all \
  --profile generic \
  --output ./dist/e2e/qa-summary.json
```

Review the rendered Data Docs at `http://127.0.0.1:3001/data-docs/index.html` through the web UI’s **Data Docs** card.

## 5. Prefect orchestration smoke

Use the sample manifests against the local Prefect server:

```bash
uv run hotpass deploy --flow refinement --manifest-dir prefect --no-upload --dry-run
uv run hotpass deploy --flow backfill --manifest-dir prefect --no-upload --dry-run
```

Trigger a manual run if desired:

```bash
uv run prefect deployment run hotpass-refinement --params '{"since": null}'
```

The run appears instantly inside the local Prefect UI (`http://127.0.0.1:4200`).

## 6. Clean up

```bash
cd deploy/docker
docker compose down -v
```

Keep the `.env.local`, Prefect profile, and `dist/e2e/` outputs for future rehearsals. When staging access becomes available, rerun the same sequence with remote endpoints by overriding the environment variables in `.env.<target>`.
