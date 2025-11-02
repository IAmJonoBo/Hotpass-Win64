---
title: Developer experience baseline
summary: Personas, workflows, and SPACE-aligned friction points captured from stakeholder interviews.
last_updated: 2025-11-02
---

## Personas and context

| Persona                   | Team                  | Motivations                                                                            | Friction points                                                                                                     | Critical workflows                                                                         |
| ------------------------- | --------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Data reliability engineer | Platform              | Ensure refined datasets land in downstream analytics systems with verified provenance. | Manual Prefect credential bootstrapping, uncertainty around SBOM availability during incident reviews.              | Hotpass CLI orchestration, Prefect deployment promotion, compliance evidence export.       |
| Compliance analyst        | Security & Compliance | Prove POPIA/ISO adherence with auditable artefacts.                                    | Evidence scattered across notebooks and ad-hoc folders, no automated reminder for quarterly verification cadence.   | Reviewing remediation backlog, exporting audit trails, compiling DSAR responses.           |
| Insights developer        | Data & Analytics      | Prototype enrichments and measure data quality improvements.                           | Local setup requires repeated `uv sync` runs and manual feature flagging, lack of self-service Backstage templates. | Creating new enrichment flows, adding expectations, iterating on dashboard visualisations. |
| Product manager           | Product               | Communicate delivery health and risk posture to leadership.                            | No single source for SPACE metrics or DevEx experiment status, limited visibility into supply-chain guardrails.     | Reviewing roadmap, preparing quarterly business reviews, triaging backlog trade-offs.      |

## Current developer journey

1. Clone repository and run `uv sync --extra dev --extra docs` to obtain tooling.
2. Follow README to execute CLI locally; opt into extras manually.
3. Update Prefect/Streamlit secrets via ad-hoc environment variables.
4. Run pytest, lint, type-check, and security scan suites sequentially.
5. Manually update `Next_Steps.md`, compliance backlog, and roadmap entries.

Average onboarding time: **2.5 hours** for experienced contributors, **~1 day** for new joiners coordinating secrets access. QA iteration averages **28 minutes** due to sequential gating and optional dependency toggling.

## Instrumentation plan

- **SPACE metrics** — Extend `docs/metrics/metrics-plan.md` with DevEx dashboard cards (QA cycle time, onboarding duration, cognitive load) instrumented via Prefect task metadata and survey tooling.
- **Telemetry hooks** — Capture Prefect flow wait times, CLI runtimes, and compliance evidence submission timestamps. Export to OpenTelemetry, ingest into Four Keys dashboards.
- **Feedback loops** — Publish quarterly DevEx pulse survey (5-point Likert) tied to roadmap milestones; synthesise learnings in DevEx review loop (see [review cadence](./review-loop.md)).

## Baseline capabilities

- Prefect and CLI orchestration stable but lack automated bootstrap.
- Observability instrumentation present yet missing user journey metrics.
- Documentation complete and curated under Diátaxis.
- Compliance backlog tracked yet manual evidence upload persists.

## Improvement opportunities

- Automate environment bootstrap and secrets provisioning through internal developer platform (IDP) scripts.
- Integrate SBOM and provenance outputs into Prefect deployments for faster audit response.
- Provide Backstage templates for new flows and dashboard modules with built-in quality gates.
- Establish shared telemetry dashboards combining SPACE, DORA, and compliance indicators.
