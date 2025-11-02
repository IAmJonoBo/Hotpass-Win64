---
title: Configure Presidio redaction
summary: Enable and tune Presidio-powered redaction for ingestion pipelines.
last_updated: 2025-11-02
---

Hotpass now redacts sensitive content at ingest time using Microsoft Presidio. The
`PipelineConfig` dataclass creates a `PIIRedactionConfig` automatically, so base
pipeline runs scrub PII before persisting refined workbooks or audit logs.

## Runtime configuration

```python
from hotpass import PipelineConfig, PIIRedactionConfig

config = PipelineConfig(
    input_dir=...,  # dataset directory
    output_path=...,  # refined workbook path
    pii_redaction=PIIRedactionConfig(
        columns=(
            "contact_primary_email",
            "contact_primary_phone",
            "notes",
        ),
        operator="replace",
        operator_params={"new_value": "[REDACTED]"},
        score_threshold=0.6,
    ),
)
```

Key options:

- **`columns`** – tuple of dataframe columns to scan.
- **`operator` / `operator_params`** – Presidio anonymizer operator and arguments.
- **`score_threshold`** – minimum confidence required to trigger redaction.
- **`capture_entity_scores`** – store detection scores with audit events.

If Presidio engines fail to initialise (for example because models are missing), the
pipeline logs a warning and continues without redaction. Provide the appropriate
Presidio extras (see `pyproject.toml`) so the Analyzer and Anonymizer engines are
available in production environments.

## Audit trail and metrics

Redaction events are appended to the pipeline audit trail and exposed via
`PipelineResult.pii_redaction_events`. Performance metrics now include a
`redacted_cells` count so dashboards and quality gates can track coverage over time.
Once schema and expectation validation complete, the pipeline re-applies redaction
to the validated dataframe before writing any Parquet/CSV/XLSX artefacts. This
post-validation sweep ensures that derived columns, such as aggregated primary
emails reconstructed during canonicalisation, are also sanitised prior to export.

## Ledger integration

Data acquisition scripts use the new `ops.acquisition` package to enforce
robots.txt/ToS guardrails and append provenance entries containing:

- source URL
- declared licence
- hashed policy identifier
- structured metadata per record

CLI example:

```bash
uv run python ops/acquisition/collect_dataset.py \
  --records data/raw/source.jsonl \
  --source-url https://example.com/dataset \
  --license CC-BY-4.0 \
  --robots policy/providers/example.com/robots.txt \
  --tos-path policy/providers/example.com/tos.txt \
  --ledger data/ledgers/example.jsonl
```

The ledger is append-only: entries are written with `os.O_APPEND` semantics and include
ISO timestamps for evidentiary review.
