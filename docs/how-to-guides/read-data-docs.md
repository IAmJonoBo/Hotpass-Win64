---
title: How-to — read Data Docs
summary: Navigate Great Expectations reports, trace failures, and pair them with lineage and provenance signals.
last_updated: 2025-11-02
---

Great Expectations Data Docs turn validation runs into HTML reports so engineers,
analysts, and auditors can understand data quality at a glance. Use this guide to
open the artefacts, interpret the pages, and triage failures.

## 1. Build or refresh the docs

Run the refinement pipeline or the dedicated refresh helper to generate the
latest reports. Both commands write HTML files under `dist/data-docs/`.

```bash
# Run validations as part of the full pipeline
uv run hotpass run --config ./config/pipeline.quickstart.toml --archive

# Or regenerate from curated fixtures
uv run python ops/validation/refresh_data_docs.py
```

CI pipelines upload the same folder as an artefact so reviewers can inspect
results without running Great Expectations locally.

## 2. Explore the landing page

Open `dist/data-docs/index.html` in your browser. The landing page highlights:

- **Validation status** — overall pass/fail for each checkpoint.
- **Suite navigator** — jump directly to domain-specific suites such as
  `company_master.expectation_suite`.
- **Recent runs** — timestamps and run identifiers so you can correlate changes
  with commits or deployment events.

```bash
open dist/data-docs/index.html
```

## 3. Drill into checkpoints

Select a failing checkpoint to inspect individual expectations. Each page shows:

- The expectation name and description.
- Examples of records that failed validation.
- Links to the underlying dataset, including batch identifiers and timestamps.

Use the batch identifier to locate the matching refined workbook in `dist/` or
the dataset upload captured in the Prefect run metadata.

## 4. Pair with lineage and provenance

When failures surface, combine the Data Docs with the wider observability stack:

- Launch the [Marquez lineage dashboard](../observability/marquez.md) to trace
  upstream sources and downstream consumers affected by the failure.
- Inspect provenance columns directly from the dataset with
  `uv run hotpass explain-provenance --dataset dist/enriched.xlsx --row-id <id>`.
- Review `dist/quality-gates/latest-ta.json` for technical acceptance summaries
  emitted by `uv run hotpass qa ta`.

## Troubleshooting

- **Docs missing** — confirm the commands above ran successfully and that
  `dist/data-docs/` exists; regenerate with the refresh helper if needed.
- **Stale results** — delete `dist/data-docs/` before rerunning to ensure
  checkpoints rebuild from scratch.
- **Sensitive fields** — redact or mask columns before sharing artefacts outside
  the organisation; refer to the compliance guides for approved processes.

```{seealso}
- [Data Docs reference](../reference/data-docs.md)
- [How-to — format and validate data](format-and-validate.md)
- [How-to — run a backfill](run-a-backfill.md)
```
