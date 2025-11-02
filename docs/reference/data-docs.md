---
title: Data Docs reference
summary: Locations, refresh commands, and consumption tips for the generated Great Expectations Data Docs.
last_updated: 2025-11-02
---

# Data Docs reference

Great Expectations checkpoints publish human-readable HTML reports that summarise
validation runs against the canonical Hotpass datasets. Use this page as a quick
reference for where the artefacts live, how to rebuild them, and how they connect
with the broader governance stack.

## Outputs and locations

- Local builds write to `{project_root}/dist/data-docs/`. Open
  `dist/data-docs/index.html` in a browser to explore the latest run.
- CI pipelines upload `dist/data-docs/` as an artefact so reviewers can inspect
  failures without rerunning validations locally.
- Each checkpoint appends a timestamped run folder under `dist/data-docs/sites/`
  so historical runs remain available during development.

## Refresh the documentation

Two entry points regenerate the Data Docs:

1. Execute validation as part of the refinement pipeline:

   ```bash
   uv run hotpass run --input-dir ./data --output-path ./dist/refined.xlsx --archive
   ```

   When checkpoints execute, the validation service emits the latest HTML
   reports into `dist/data-docs/` automatically.

2. Run the bundled refresh helper to validate against the tracked fixtures:

   ```bash
   uv run python ops/validation/refresh_data_docs.py
   ```

   The helper reads the sample workbooks in `data/` and regenerates the full
   report set. CI uses the same script to confirm suites remain in sync with the
   dataset contracts.

## Where to look for answers

- Consult the [Format and validate how-to](../how-to-guides/format-and-validate.md)
  for step-by-step instructions on running checkpoints during development.
- Review the [Expectation reference](expectations.md) to understand which suites
  and checkpoints contribute to each page in the Data Docs.
- Track roadmap commitments for Data Docs in
  [docs/roadmap.md](../roadmap.md) and the repository-level `ROADMAP.md` file.
- Pair Data Docs with lineage insights from the
  [Marquez quickstart](../observability/marquez.md) to cross-check upstream and
  downstream impacts of failed validations.

## Distribution checklist

Before sharing Data Docs with stakeholders:

- Validate against the latest canonical inputs (`data/` samples or production
  extracts).
- Confirm sensitive values are redacted when exporting artefacts outside the
  organisation.
- Include a short changelog entry or PR link describing the validation context.
