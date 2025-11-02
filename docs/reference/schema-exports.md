---
title: Schema export reference
summary: JSON Schema artefacts generated from the dataset contract registry.
last_updated: 2025-11-02
---

# Schema export reference

Hotpass publishes JSON Schema files alongside the Pydantic contract models so
consumers can validate payloads outside the Python runtime. This reference
summarises where the artefacts live, how to regenerate them, and how downstream
teams can integrate the schemas into their quality gates.

## Artefact layout

- Schemas live under `schemas/` with the naming convention `<dataset>.schema.json`.
- Each file reflects the canonical contract defined in
  `apps/data-platform/hotpass/contracts/datasets.py`.
- The [Dataset schemas reference](schemas.md) renders a human-friendly table for
  each dataset using the same source registry.

## Regenerate the exports

Run the contract generator after updating contract models or the source data
examples:

```bash
uv run python -m hotpass.contracts.generator
```

The generator refreshes both the JSON Schema artefacts and the documentation page
under `docs/reference/schemas.md`. Commit regenerated files with the change so the
registry, docs, and exported contracts stay aligned.

## Consuming schemas downstream

- **Application integrations:** import the JSON Schema into client validation
  pipelines (for example, Node.js or Go services) to reject malformed payloads
  before they enter Hotpass.
- **Data quality tooling:** wire the schema into Great Expectations or other
  validation frameworks to mirror the canonical rules.
- **Change management:** include schema diffs in pull requests so reviewers can
  verify breaking changes and coordinate deployments.

## Related reading

- [Data Docs reference](data-docs.md) — browse validation output generated from
  the expectation suites that enforce these contracts.
- [Roadmap](../roadmap.md) — track the contract and validation milestones by
  programme phase.
