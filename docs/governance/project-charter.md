---
title: Governance — project charter
summary: Mission, personas, guardrails, and governance rhythms for the Hotpass modernisation programme.
owner: n00tropic
last_updated: 2025-11-02
---

Hotpass ingests spreadsheet workbooks (primarily XLSX) alongside orchestrated research crawlers, cleans and backfills the data, maps relationships, and publishes analysis-ready intelligence that operators steer through the CLI and MCP-managed automations. This charter links the programme mission to the personas we serve, the constraints we must respect, and the boundaries we will not cross.

## Mission

- Deliver a governed, industry-ready ingestion and analysis platform that coordinates spreadsheet loading, crawler-led research, relationship mapping, and refinement while preserving compliance and operational readiness.
- Shorten the time from ingesting messy source files or crawler payloads to publishing connected, trustworthy outputs for downstream analysis.
- Embed observability, documentation, and quality gates so humans and Copilot automations can ship deeper investigations safely and auditably.

## Strategic context

- **Problem statement**: Organisations rely on ad-hoc spreadsheets and scattered research crawlers that duplicate entities, leave gaps, and lack observability. Manual cleanup, backfilling, and relationship tracking are error-prone and slow.
- **Opportunity**: Hotpass coordinates spreadsheet ingestion with orchestrated crawlers, configurable validation, enrichment, and relationship mapping so refinements, backfills, and deeper analysis remain repeatable and traceable.
- **Value hypothesis**: Teams that standardise on Hotpass will reduce refinement cycle time by 60%, surface compliance and coverage gaps before downstream systems ingest data, and unlock connected insights for investigations and operations.

## Stewardship and licensing

- **Steward**: n00tropic curates the canonical Hotpass distribution, documentation, and automation guardrails. Governance, roadmap, and security escalations are channelled through `security@n00tropic.example`.
- **Dual licensing**: Source code ships under the Business Source License 1.1 with a commercial license option (`LICENSES/COMMERCIAL-LICENSE.md`) for production workloads that exceed the Additional Use Grant. On the Change Date the code reverts to Apache 2.0, ensuring long-term openness while allowing n00tropic to offer supported tiers.

## Personas and needs

| Persona              | Needs                                                                           | Success signals                                                                                     |
| -------------------- | ------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Data operations lead | Reliable, repeatable pipeline runs with transparent quality reporting.          | Flow runtimes stable, dashboards highlight fewer untriaged failures per release.                    |
| Compliance officer   | Evidence of POPIA adherence, audit-friendly provenance, and redaction controls. | Quality reports flag zero high-severity unresolved compliance issues per run.                       |
| Data engineer        | Extendable pipeline with clear contracts, tests, and observability hooks.       | Onboarding new profiles or connectors requires ≤ 2 PRs and passes automated gates on first attempt. |
| Product analyst      | Self-service access to refined datasets and dashboards.                         | Streamlit dashboard uptime ≥ 99% during business hours, with fresh exports after each pipeline run. |

## Constraints and operating assumptions

- Preserve CLI and Prefect interfaces; downstream teams now use the unified `hotpass` command while the deprecated `hotpass-enhanced` shim delegates for backwards compatibility.
- Optional extras (enrichment, geospatial, dashboards) may not install in restricted CI environments—tests and telemetry must tolerate feature flags.
- Datasets contain POPIA-sensitive information; artefacts must avoid exposing raw PII and respect retention policies.
- Sandbox environments lack outbound internet access; enrichment connectors require controlled fallbacks and cached fixtures.
- Docker image publication workflow remains under construction; deployment guidance assumes manual promotion until CI validation lands.

## “Do-not” boundaries

- Do not break backward compatibility for exported schemas or CLI arguments without a documented migration plan and 2 release windows’ notice.
- Do not ingest or emit datasets without provenance metadata or quality scores.
- Do not enable external telemetry exporters that exfiltrate data outside approved observability endpoints.
- Do not merge changes that bypass automated QA gates (tests, lint, type checks, security scans, docs build) without formal risk acceptance.

## Governance cadence and artefacts

- **Roadmap stewardship**: Update [docs/roadmap.md](../roadmap.md) after major scope, risk, or milestone changes.
- **Metrics reviews**: Track DORA and SPACE targets per the [metrics plan](../metrics/metrics-plan.md); review monthly with engineering and product leads.
- **Quality gates**: Maintain ≥ 80% coverage, green lint/type/security/build checks, and document waivers in `Next_Steps.md` when temporary exceptions are approved.
- **Telemetry posture**: Validate instrumentation changes in staging before production rollout; log assumptions in the metrics plan and revisit quarterly.

## Decision logging

- Capture architectural or governance-impacting decisions as ADRs under `docs/explanations/` or new governance records when material changes occur.
- Record open risks, mitigation owners, and due dates in `Next_Steps.md` to preserve a single source of truth for follow-up work.

## Change management checklist

1. Confirm alignment with mission, personas, and constraints before accepting roadmap adjustments.
2. Document feature flags, rollout plans, and rollback procedures in the relevant pull request and governance notes.
3. Ensure support teams (Data Ops, Compliance, Observability) acknowledge changes affecting their runbooks prior to release.
