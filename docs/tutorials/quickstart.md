---
title: Quickstart — refine a workbook in minutes
summary: Run the core Hotpass pipeline end-to-end using sample data and explore the generated outputs.
last_updated: 2025-11-03
---

# Quickstart

This tutorial shows you how to install Hotpass, validate a spreadsheet, and publish a refined workbook with quality insights. It assumes you are comfortable with Python tooling but new to the Hotpass platform.

## Workflow overview

```{mermaid}
flowchart LR
    Setup[1. Bootstrap workspace] --> Sample[2. Load sample workbook]
    Sample --> Doctor[3. Run doctor]
    Doctor --> Run[4. Refine data]
    Run --> Review[5. Review & interpret]
    Review --> Extend[6. Optional: extend]

    classDef step fill:#fff3cd,stroke:#333,stroke-width:2px
    class Setup,Sample,Doctor,Run,Review,Extend step
```

## 1. Install the tooling

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if it is not already available. Clone the repository and create a virtual environment with the documentation and development extras:

```bash
uv venv
uv sync --extra dev --extra docs
uv run pre-commit install
```

Add orchestration or enrichment extras up front if you plan to use them in this session:

```bash
uv sync --extra dev --extra orchestration --extra enrichment --extra geospatial --extra dashboards
```

## 2. Bootstrap a workspace

Create a clean project directory with sample configuration:

```bash
uv run hotpass init --path ./quickstart-workspace
cd quickstart-workspace
```

The bootstrap step creates configuration, profile, and Prefect deployment templates under `./config/` and `./prefect/`. You can run the tutorial inside this directory without touching the main repository tree.

## 3. Load a sample workbook

Copy one anonymised fixture from the repository root into `data/`. The Reachout workbook produces a full successful run:

```bash
cp ../data/'Reachout Database.xlsx' data/
```

> **Troubleshooting:** If you copy `SACAA Flight Schools - Refined copy__CLEANED.xlsx` you will trigger a Frictionless contract failure because the sheet contains duplicate rows (positions 15, 43, and 71). The CLI stops with a helpful error so you can remove duplicates or update the schema contract before rerunning.

Peek at the spreadsheet so you recognise columns such as `organization_name`, `contact_primary_email`, and `status` before the pipeline rewrites them.

## 4. Run the doctor

Check that the environment and configuration are ready:

```bash
uv run hotpass doctor --config ./config/pipeline.quickstart.toml
```

```
Environment diagnostics
[PASS] environment.python_version: Python 3.13 detected
[PASS] environment.input_dir: Input directory ready: data
Configuration diagnostics
[PASS] governance.data_owner: Data owner registered as 'Data Governance'.
```

## 5. Run the pipeline

Refine the workbook, package the outputs, and print a machine-readable summary:

```bash
uv run hotpass refine \
  --profile quickstart \
  --profile-search-path ./config/profiles \
  --config ./config/pipeline.quickstart.toml \
  --log-format json
```

```
{"event": "pipeline.summary", "data": {"total_records": 1033,
 "invalid_records": 0, "source_breakdown": {"Reachout Database": 1034},
 "recommendations": ["CRITICAL: Average data quality score is below 50%. Review data sources and validation rules."],
 "performance_metrics": {"total_seconds": 4.31}}}
```

The CLI writes:

- `dist/refined.xlsx` — cleaned workbook with harmonised columns.
- `dist/refined.parquet` — analytics-friendly export.
- `dist/refined-data-<timestamp>.zip` — archived source files when `archive = true`.

## 6. Review the results

Open the refined workbook to see the normalised columns and conflict resolutions. Notice the recommendation in the pipeline summary: the average data-quality score is below 50%. Investigate the low-scoring rows before sharing the output. When Hotpass drops duplicate primary keys it also exports them to `dist/contract-notices/<run-id>/` so you can triage the upstream source.

Need Great Expectations Data Docs? Run `uv run hotpass qa all` after the pipeline: the command prints the path to the regenerated docs (for example `dist/quality-gates/qg2-data-quality/<timestamp>/data-docs`).

To capture a JSON log for automation, repeat the refine command with `--log-format json` (already shown) and redirect stdout to a file.

## 7. Extend the experience

Once you are comfortable with the basics, explore the advanced tutorial to orchestrate the pipeline and stream telemetry with Prefect and OpenTelemetry.

```{seealso}
The [Enhanced pipeline tutorial](./enhanced-pipeline.md) continues the journey by enabling orchestration, enrichment, and monitoring features.
```
