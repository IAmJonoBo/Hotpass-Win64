---
title: Explanation — platform scope and gaps
summary: Current capabilities, limitations, and investment themes guiding Hotpass development.
last_updated: 2025-11-02
---

Hotpass continues to evolve from a spreadsheet normaliser into an end-to-end data refinement platform. This page highlights what is currently in place and what remains under active development.

## Delivered capabilities

- **Industry-agnostic profiles**: Configurable synonyms, validation thresholds, and contact preferences for aviation and generic business use cases.
- **Enhanced pipeline**: Entity resolution, enrichment connectors, compliance checks, geospatial processing, and observability hooks.
- **Operational tooling**: Prefect orchestration, Streamlit dashboard, configuration doctor, and automated quality reporting.

## Known gaps

- **External registry integrations**: Connectors for CIPC, SACAA, and other registries are scaffolded but not yet production hardened.
- **Advanced ML scoring**: LightGBM- or XGBoost-based prioritisation remains on the roadmap.
- **Offline observability**: OpenTelemetry exporters still log warnings when endpoints are unreachable.
- **Docker publishing**: CI validation exists, but the release pipeline does not yet publish container images.

## Investment themes

1. **Coverage & enrichment**: Expand connectors and caching to improve data completeness.
2. **Resilience & automation**: Harden orchestration, add retries/backoff, and reduce manual intervention.
3. **User experience**: Simplify configuration, improve documentation, and add dashboards for non-technical stakeholders.

See the [roadmap](../roadmap.md) for detailed milestones and owners.
