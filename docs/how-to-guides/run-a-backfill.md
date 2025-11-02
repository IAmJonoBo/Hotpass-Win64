---
title: How-to — run a backfill
summary: Replay archived spreadsheets through Hotpass while respecting Prefect guardrails and provenance auditing.
last_updated: 2025-11-02
---

Running a backfill lets you rebuild history after schema changes, late-arriving
spreadsheets, or governance fixes. The Hotpass CLI orchestrates the entire flow
so you can hydrate archives, restore inputs, and publish refreshed outputs with
the same observability emitted by scheduled runs.

## Prerequisites

- Install the orchestration extras before you begin:

  ```bash
  HOTPASS_UV_EXTRAS="dev orchestration" bash ops/uv_sync_extras.sh
  ```

- Ensure the archives you plan to replay are stored in a predictable structure
  (for example `dist/input-archives/<date>/<bundle>.zip`) and that your profile
  populates `orchestrator.backfill.archive_pattern` accordingly.
- Confirm Prefect work pools are reachable if you expect the flow to distribute
  work across workers. When running offline, Hotpass automatically falls back to
  sequential execution.

## 1. Stage the input archives

Store historical spreadsheets as zipped bundles that mirror how production runs
archive inputs. Provide meaningful version identifiers so provenance audits can
tie refreshed datasets back to the original capture.

```bash
mkdir -p dist/input-archives/2025-10-01
zip dist/input-archives/2025-10-01/hotpass-inputs-v1.zip data/raw/2025-10-01/*.xlsx
```

## 2. Launch the backfill

Run the CLI command with explicit archive and restore locations. The example
below replays two historical versions and writes refined outputs under
`/tmp/hotpass/backfill/outputs/`.

```bash
uv run hotpass backfill \
  --config ./config/pipeline.production.toml \
  --start-date 2025-09-29 \
  --end-date 2025-10-01 \
  --version v1 \
  --version v2 \
  --archive-root ./dist/input-archives \
  --restore-root /tmp/hotpass/backfill \
  --profile aviation \
  --archive
```

Hotpass extracts each bundle into
`<restore-root>/<date>--<version>/`, replays the pipeline with the selected
profile, and emits OpenTelemetry signals plus Prefect task metadata. The CLI
reports a summary for every run and returns a non-zero exit code when any replay
fails validation.

## 3. Review outputs and artefacts

- Refined workbooks land in `<restore-root>/outputs/`.
- Prefect flow runs appear in the configured work pool, inheriting concurrency
  constraints from `orchestrator.backfill.concurrency_limit`.
- Observability sinks (Grafana, Datadog, etc.) display the same metrics emitted
  by scheduled runs (for example `hotpass.pipeline.duration`).

```bash
ls -R /tmp/hotpass/backfill/outputs
open dist/data-docs/index.html
```

Archive the refreshed outputs (for example by re-zipping them) if you need to
preserve artefacts for audits.

## Troubleshooting

- **Archive not found** — confirm the naming pattern matches
  `orchestrator.backfill.archive_pattern` or pass `--archive-pattern`.
- **Sequential execution** — when Prefect workers are unavailable the CLI falls
  back to synchronous runs; look for warnings in the console output.
- **Validation failures** — inspect `dist/data-docs/` and rerun the pipeline on
  the affected slice with `uv run hotpass refine` to iterate quickly.
- **Rate limits** — respect provider SLAs by tuning the profile-level
  `research_rate_limit` block; the orchestrator enforces both burst and steady
  states for network-backed enrichment.

```{seealso}
- [How-to — orchestrate and observe pipelines](orchestrate-and-observe.md)
- [Prefect backfill guardrails](../operations/prefect-backfill-guardrails.md)
- [Hotpass reference — Data Docs](../reference/data-docs.md)
```
