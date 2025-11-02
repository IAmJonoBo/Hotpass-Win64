---
title: Establish dataset contracts and regeneration workflow
summary: Define dataset contracts in code, regenerate JSON schemas, and publish reference documentation.
last_updated: 2025-11-02
status: Accepted
---

Hotpass relied on manually curated Frictionless JSON schemas under `schemas/` to
describe upstream workbooks and the refined single source of truth. The schemas
were easy to drift because the authoritative definitions lived outside the
codebase, the JSON lacked shared helpers, and documentation had to be updated by
hand. Tests only asserted against the static files, so developers could not
reason about the contracts programmatically or regenerate the artefacts when
fields changed.

## Decision

We introduced a `hotpass.contracts` module that stores each dataset contract as a
Pydantic row model backed by Pandera dataframe validation. The module exposes a
registry, round-trip helpers, and utilities to regenerate both the JSON schemas
and an auto-generated reference page. Running
`python -m hotpass.contracts.generator` now rewrites `schemas/*.json` and
`docs/reference/schemas.md`, keeping the contract source of truth in code while
ensuring the published artefacts stay synchronised.

## Consequences

- Contracts are expressed once in code, enabling reuse across validation,
  testing, documentation, and orchestration tooling.
- JSON schemas and docs can be regenerated deterministically, eliminating manual
  edits and reducing drift between models and published contracts.
- Tests can round-trip example records through Pydantic, Pandera, and the JSON
  serialisation to guarantee that changes to the registry remain backwards
  compatible.
- Contributors must update the registry and rerun the generator when adding or
  modifying dataset fields, but the workflow is scripted and covered by tests.
