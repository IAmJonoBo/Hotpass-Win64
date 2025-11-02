---
title: Compliance — evidence catalog
summary: Inventory of audit evidence sources, locations, and retention guidance supporting compliance controls.
last_updated: 2025-11-02
---

# Compliance — evidence catalog

| Evidence source                         | Location                                                                                 | Owner                  | Retention        | Notes                                                                                                 |
| --------------------------------------- | ---------------------------------------------------------------------------------------- | ---------------------- | ---------------- | ----------------------------------------------------------------------------------------------------- |
| QA command history                      | `Next_Steps.md` and GitHub Actions `process-data.yml` logs                               | Engineering            | 1 year           | Capture command outputs in release notes per run; export workflow logs quarterly.                     |
| Prefect flow run logs                   | Prefect Orion API (`refinement_pipeline_flow`)                                           | Engineering            | 1 year rolling   | Configure automated export to object storage; include consent validation events once POPIA-001 lands. |
| Threat model                            | [`docs/security/threat-model.md`](../security/threat-model.md)                           | Security               | Update on change | Serves as input to ISO27001-002 asset register and SOC2-002 risk register.                            |
| Architecture diagrams                   | [`docs/architecture/hotpass-architecture.dsl`](../architecture/hotpass-architecture.dsl) | Architecture           | Update on change | Provide trust boundaries for POPIA transfer analysis and SOC 2 confidentiality controls.              |
| Metrics dashboards                      | Four Keys / SPACE exports (planned)                                                      | Observability          | TBD              | TODO: Define export pipeline once metrics automation is enabled.                                      |
| DSAR runbook & logs                     | `data/compliance/dsar/`                                                                  | Support & Engineering  | 1 year           | Prefect consent validation exports land here; mirror summaries in quarterly verification reports.     |
| Supplier risk register                  | `docs/governance/supplier-risk-register.md`                                              | Procurement & Security | Update on change | Tracks onboarding decisions and review cadence aligned to ISO27001-004.                               |
| Incident response playbook              | [`docs/security/threat-model.md`](../security/threat-model.md) & future incident guide   | Security               | Update on change | Update with POPIA escalation steps per POPIA-004; archive historical versions.                        |
| Data export access logs                 | `dist/logs/access/`                                                                      | Platform               | 1 year           | Access manifests produced after each refined export, hashed and rotated quarterly.                    |
| Acquisition telemetry + provider policy | `policy/acquisition/providers.json` and OTEL span exports (`acquisition.*`)              | Platform & Compliance  | Update on change | Archive telemetry with onboarding approvals and refresh allowlist metadata quarterly.                 |

Review evidence completeness during each verification cycle and update retention guidance as storage or regulatory requirements evolve.
