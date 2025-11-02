---
title: Backstage MVP and internal developer platform enablement
summary: Minimal Backstage footprint, catalog entries, and TechDocs integration for Hotpass.
last_updated: 2025-11-02
---

## Catalog entries

| Component                   | Backstage kind | File                                                                                           | Description                                                               |
| --------------------------- | -------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Hotpass pipeline            | Component      | [`catalog-info.yaml`](../../catalog-info.yaml)                                                 | Core data refinement service with Prefect orchestration.                  |
| Prefect deployment template | Template       | [`templates/backstage/prefect-pipeline.yaml`](../../templates/backstage/prefect-pipeline.yaml) | Golden path for spinning up new Prefect flow + CLI wrapper with QA gates. |
| Streamlit dashboard         | Component      | [`catalog-info.yaml`](../../catalog-info.yaml)                                                 | Observability and data quality visualisation layer.                       |
| DevEx governance            | Resource       | [`catalog-info.yaml`](../../catalog-info.yaml)                                                 | Captures DevEx review loop and metrics dashboard resources.               |

## TechDocs integration

1. Include Backstage annotation `backstage.io/techdocs-ref: dir:./docs` in catalog entry.
2. Sphinx build pipeline already produces HTML under `docs/_build/html` — configure TechDocs generator to consume the same build via `mkdocs-techdocs-core` container with Sphinx support.
3. Publish nightly TechDocs rebuild job referencing `docs/_build/html` artifact from `docs.yml` workflow.

## Golden path template highlights

- Bootstraps Prefect deployment skeleton with QA/observability configuration.
- Embeds SBOM/provenance generation steps via `ops/supply_chain` utilities.
- Configures default fitness function thresholds (latency, coupling) with pipeline YAML gating.
- Seeds `Next_Steps.md` entry for new service adoption.

## Automation roadmap

| Milestone              | Description                                                                         | Dependencies                                           | Target     |
| ---------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------ | ---------- |
| Bootstrap script GA    | ✅ `ops/idp/bootstrap.py` seeds local environment configuration and SBOM tooling.   | Secrets management decision, `uv` global cache.        | 2025-11-15 |
| Template publishing    | Deploy Backstage template and catalog entry to production instance.                 | Backstage admin access, TechDocs pipeline credentials. | 2025-11-22 |
| Self-service QA gating | Integrate mutation, accessibility, and supply-chain jobs into template scaffolding. | CI workflows finalised in repo.                        | 2025-12-06 |
| Evidence automation    | Pipe compliance evidence exports into Backstage resources and Scorecards.           | POPIA automation, object storage endpoint.             | 2025-12-20 |

## Runbooks & ownership

- **Platform Engineering** owns Backstage catalog & templates, coordinates upgrades.
- **Docs** team ensures TechDocs rebuild success and content parity with `docs/`.
- **Security** validates SBOM/provenance distribution via Backstage Scorecards.
- **Compliance** links verification cadence outcomes into Backstage resources.
