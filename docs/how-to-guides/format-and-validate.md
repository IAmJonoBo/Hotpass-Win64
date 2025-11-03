---
title: How-to — format outputs and enforce validation rules
summary: Apply professional styling, govern ingest schemas, and surface parquet/CSVW artefacts for downstream tooling.
last_updated: 2025-12-26
---

Follow this guide when stakeholders expect polished deliverables and tailored quality gates.

## Enable premium formatting

```python
from pathlib import Path
from hotpass import PipelineConfig, OutputFormat, run_pipeline

formatting = OutputFormat(
    header_bg_color="366092",
    header_font_color="FFFFFF",
    zebra_striping=True,
    auto_size_columns=True,
    freeze_header_row=True,
    add_filters=True,
)

config = PipelineConfig(
    input_dir=Path("data"),
    output_path=Path("dist/refined.xlsx"),
    enable_formatting=True,
    output_format=formatting,
)
run_pipeline(config)
```

Key options:

- `header_bg_color` and `header_font_color` use hex RGB strings.
- `zebra_striping` alternates row colours for better readability.
- `add_filters` adds Excel auto-filters to every column.

## Govern ingest schemas and expectations

Every workbook consumed by the pipeline carries a Frictionless Table Schema contract under `schemas/` and a matching Great Expectations suite under `data_expectations/suites/`. Contracts ship with the package and are exercised automatically during `ingest_sources()`.

### Directory structure

```text
data_expectations/
├── suites/           # Canonical expectation suite definitions
│   ├── reachout_organisation.json
│   ├── reachout_contact_info.json
│   ├── sacaa_cleaned.json
│   ├── contact_company_cat.json
│   ├── contact_company_contacts.json
│   ├── contact_company_addresses.json
│   └── contact_capture.json
└── checkpoints/      # Checkpoint configurations
    ├── reachout_organisation.json
    ├── reachout_contact_info.json
    └── ...
```

### Using checkpoints with Data Docs

The new checkpoint-based validation infrastructure enables automated Data Docs generation:

```python
from pathlib import Path
import pandas as pd

from hotpass.validation import run_checkpoint

frame = pd.read_excel(Path("data/Reachout Database.xlsx"), sheet_name="Organisation")

# Run checkpoint with Data Docs generation
result = run_checkpoint(
    frame,
    checkpoint_name="reachout_organisation",
    source_file="Reachout Database.xlsx#Organisation",
    data_docs_dir=Path("dist/data-docs"),
)

# Access validation results
print(f"Validation successful: {result.success}")
print(f"Data Docs published to: dist/data-docs/")
```

Data Docs provide an interactive HTML view of validation results, making it easy to explore failures and understand data quality issues.

### Legacy validation API

For backward compatibility, the original validation API remains available:

```python
from hotpass.validation import validate_with_expectations

validate_with_expectations(
    frame,
    suite_descriptor="reachout_organisation.json",
    source_file="Reachout Database.xlsx#Organisation",
)
```

### Adding new validation suites

To introduce a new sheet, add both the schema and expectation suite:

```bash
# Create new suite
cp data_expectations/suites/reachout_organisation.json \
   data_expectations/suites/my_feed.json

# Create checkpoint configuration
cp data_expectations/checkpoints/reachout_organisation.json \
   data_expectations/checkpoints/my_feed.json
```

Update the suite and checkpoint files with your dataset name and column expectations, then reference them from a data source loader. If the workbook drifts from the schema, `DataContractError` raises with the missing/extra fields and blocks the run.

## Customise validation thresholds

Profiles still define the SSOT quality tolerances. Override them for specific deployments:

```yaml
validation:
  email_validity: 0.9
  phone_validity: 0.85
  website_validity: 0.75
  duplicate_threshold: 0.1
```

Lower thresholds make the pipeline more permissive for exploratory analysis. Higher thresholds (≥0.95) are recommended for production datasets.

## Capture governed artefacts (Parquet, DuckDB, CSVW)

Validated outputs are now materialised as Polars-backed Parquet snapshots and queried via DuckDB before the final export. After every run you will find:

- A Parquet file beside your chosen output (`refined.xlsx → refined.parquet`) containing the DuckDB ordered dataset.
- Optional CSV exports accompanied by a CSVW sidecar (`refined.csv-metadata.json`) whose table schema is sourced from `schemas/ssot.schema.json`.

You can inspect the Parquet snapshot directly with DuckDB for ad-hoc SQL:

```python
import duckdb

with duckdb.connect() as conn:
    df = conn.execute(
        "SELECT organization_name, data_quality_score FROM read_parquet('dist/refined.parquet') ORDER BY data_quality_score DESC"
    ).fetch_df()
```

Re-running `run_pipeline` will refresh both the parquet snapshot and any CSVW metadata automatically.

## Secrets scanning guardrail

Hotpass ships a curated `detect-secrets` baseline, but full-repository sweeps remain part of the handover checklist. To avoid
high-entropy fixtures such as `pnpm-lock.yaml` or curated sample archives from dominating the results, target the tracked source
directories with the shared exclude pattern:

```bash
uv run python -m detect_secrets scan \
  --exclude-files '(pnpm-lock\.yaml$|scancode-sample\.json$)' \
  apps docs infra ops scripts src tests tools
```

The shortened path list keeps runtime under 20 seconds on ARC runners while still covering the Python, Terraform, and
documentation surfaces that ship with orchestration changes. The same command is wired into `scripts/testing/full.sh` so CI and
local quality gates stay in sync. When you deliberately embed placeholder credentials (for example `PLACEHOLDER_REPLACE_WITH_SOPS_REFERENCE`),
add an inline `# pragma: allowlist secret` comment so the scan remains clean without muting the rule globally.

## Monitor validation feedback

After each run, inspect the generated quality report:

```python
from hotpass.quality import load_quality_report

report = load_quality_report(Path("dist/quality-report.json"))
print(report.summary())
```

Combine the structured report with the Markdown export to share remediation tasks with stakeholders.

## Troubleshooting

- **Excel formatting not applied**: Ensure `enable_formatting=True` and install the `dashboards` extra for the required libraries.
- **Frictionless or Great Expectations failures**: Compare the failure payload in the raised `DataContractError` with the schema/expectation JSON files. Align the workbook headers (case-sensitive) or extend the contract as needed.
- **Large Excel files**: Disable conditional formatting for columns with more than 50,000 rows to speed up exports.
- **Missing CSVW sidecar**: Confirm the target filename ends with `.csv`; other extensions bypass CSVW generation.
