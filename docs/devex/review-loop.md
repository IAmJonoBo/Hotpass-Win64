---
title: Developer experience review cadence
summary: Governance process for monitoring DevEx metrics, experiments, and platform enablement.
last_updated: 2025-11-02
---

## Quarterly governance forum

| Cadence                                                 | Participants                                              | Agenda                                                                                   | Inputs                                                                                       | Outputs                                                                                                 |
| ------------------------------------------------------- | --------------------------------------------------------- | ---------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Quarterly (aligned with compliance verification window) | Platform Engineering, QA, Compliance, Product, DX sponsor | SPACE/DORA metrics review, experiment status, backlog reprioritisation, risk assessment. | Metrics dashboard, experiment retros, Next_Steps quality gates, compliance evidence refresh. | Updated experiment backlog, action items with owners/dates, roadmap adjustments, risk register updates. |

## Monthly sync

- **Focus** — Track active experiments, unblock platform automation work, surface telemetry anomalies.
- **Artefacts** — Experiment scorecards, pipeline health (Prefect runs), SBOM/provenance distribution metrics.
- **Decisions** — Adjust feature flags, escalate infrastructure dependencies, update IDP backlog.

## Async rituals

- **DevEx pulse survey** — 5 question Likert + free-text, distributed monthly.
- **Metrics digest** — Automated Slack summary linking to Grafana/Four Keys dashboards.
- **Runbook updates** — Documented in `docs/metrics/devex-audit.md` and cross-linked here.

## Escalation path

1. Record blocker or risk in `Next_Steps.md` (Risks/Notes).
2. Notify owners in Slack `#hotpass-devex`.
3. If unresolved within two working days, escalate to platform steering committee (chaired by DX sponsor).

## Success measures

- Onboarding duration ≤ **90 minutes** by 2025-12-31.
- QA feedback loop ≤ **20 minutes** median by 2025-12-31.
- Quarterly SPACE satisfaction score ≥ **4/5**.
- ≥ **80%** of remediation backlog items automatically synced to evidence catalog.
