---
title: Metrics — developer experience audit
summary: SPACE-aligned assessment of Hotpass developer workflows, tooling friction, and improvement backlog hooks.
last_updated: 2025-11-02
---

## Survey insights

| SPACE dimension | Current signal                                                                                       | Pain points                                                                                        | Proposed improvement                                                                                |
| --------------- | ---------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Satisfaction    | Anecdotal feedback highlights strong docs but friction around manual compliance evidence updates.    | Contributors unsure where to log compliance progress; duplication across roadmap and ad-hoc notes. | Centralise compliance artefacts in `docs/compliance/` with linked backlog (complete).               |
| Performance     | QA suite passes locally but adds ~28s per run; optional extras skipped in CI.                        | Waiting on enrichment/geospatial dependency installs blocks enabling full coverage.                | Track dependency enablement under existing QA initiative; explore caching layers for CI.            |
| Activity        | Prefect runs and docs updates tracked, but remediation tasks lacked single backlog.                  | Compliance tasks fell through cracks without dedicated register.                                   | `docs/compliance/remediation-backlog.md` now records owners and due dates.                          |
| Communication   | Roadmap captures initiatives; DSAR and incident comms undefined.                                     | Support lacks visibility into regulatory workflows and escalation contacts.                        | Upcoming POPIA backlog items will add DSAR automation and incident playbook updates.                |
| Efficiency      | Environment setup relies on manual `uv sync` commands; Prefect credentials vary across environments. | Engineers repeat setup steps and manage secrets locally.                                           | Evaluate internal developer platform enhancements (automation, secret management) as tracked below. |

## Platform enhancement backlog

| Initiative                       | Description                                                                      | Owner                | Link                                                        |
| -------------------------------- | -------------------------------------------------------------------------------- | -------------------- | ----------------------------------------------------------- |
| Automated environment bootstrap  | Provide script or make target to configure uv, Prefect, and telemetry defaults.  | Platform Engineering | `Next_Steps.md` (Tasks: DevEx automation)                   |
| Secrets management standard      | Decide approach for registry connectors and telemetry secrets.                   | DevOps               | `Next_Steps.md` (Tasks: Secrets management)                 |
| Dashboard hardening              | Auth + filesystem allowlists implemented; migrate to SSO and audit logging next. | Platform             | `Next_Steps.md` (Tasks: Dashboard controls)                 |
| Compliance telemetry integration | Feed POPIA/ISO/SOC evidence into metrics dashboards for visibility.              | Observability        | [Remediation backlog](../compliance/remediation-backlog.md) |

## Next steps

- Align quarterly SPACE survey with compliance verification cadence to reduce survey fatigue.
- Add DevEx metrics (QA wait time, onboarding duration) to the monthly roadmap summary.
- Evaluate if internal developer platform investments can automate evidence capture (e.g., Prefect log exports) to support compliance.
