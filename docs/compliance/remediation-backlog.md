---
title: Compliance — remediation backlog
summary: Prioritised tasks to close compliance gaps across POPIA, ISO 27001, and SOC 2.
last_updated: 2025-11-02
---

Each backlog item aligns to a control gap in the framework matrices and records ownership, due date, and evidence expectations. High-risk items are marked 🔴.

## POPIA

### POPIA-001 Automate consent validation

- **Risk**: 🔴 High
- **Owner**: Product & Engineering
- **Due**: 2025-11-22
- **Summary**: Enforce consent status at runtime by extending `hotpass.compliance` checks and emitting audit logs when profiles violate lawful processing requirements.
- **Evidence**: Prefect flow logs under `data/logs/prefect/`, updated unit tests covering consent blockers, change log entry referencing consent validation toggle.
- **Status**: ✅ Completed 2025-10-26 — consent enforcement shipped in `hotpass.compliance` with regression tests and documentation updates.

### POPIA-002 Document enrichment minimisation checklists

- **Risk**: 🟡 Medium
- **Owner**: Data Governance
- **Due**: 2025-11-29
- **Summary**: Create dataset-specific minimisation templates signed off before enabling enrichment connectors; store checklists under `docs/compliance/evidence/`.
- **Evidence**: Approved checklist template, pull request linking to matrix update.

### POPIA-003 Implement DSAR tracking

- **Risk**: 🔴 High
- **Owner**: Support & Engineering
- **Due**: 2025-12-06
- **Summary**: Deliver Prefect automation or CLI workflow to log DSAR requests, track SLA clocks, and record completion artefacts.
- **Evidence**: DSAR runbook, Prefect flow logs exported to `data/compliance/dsar/`, dashboard widget or CSV export.

### POPIA-004 Extend incident playbook

- **Risk**: 🟡 Medium
- **Owner**: Security
- **Due**: 2025-11-29
- **Summary**: Update incident response guide with POPIA-specific notification steps, including regulator timelines and communication templates.
- **Evidence**: Incident playbook revision, stakeholder sign-off note.

### POPIA-005 Define transfer controls

- **Risk**: 🟡 Medium
- **Owner**: Platform
- **Due**: 2025-12-13
- **Summary**: Document approved transfer destinations, require encryption for archive exports, and implement access logging for `dist/` artefacts.
- **Evidence**: Configuration updates, logging screenshots, revised architecture notes.

## ISO 27001

### ISO27001-001 Establish policy approval cycle

- **Risk**: 🟡 Medium
- **Owner**: Leadership
- **Due**: 2025-11-15
- **Summary**: Introduce quarterly review calendar with recorded approvals for the governance charter and related policies.
- **Evidence**: Signed approval log, updated charter front matter with version info.

### ISO27001-002 Build asset register

- **Risk**: 🔴 High
- **Owner**: Security & Platform
- **Due**: 2025-11-29
- **Summary**: Centralise asset inventory including classification, location, and custodian; integrate with roadmap quality gates.
- **Evidence**: Asset register manifest committed under `data/inventory/asset-register.yaml`, review sign-off notes stored in `docs/governance/`.
- **Status**: ✅ Completed 2025-10-26 — initial asset register published at `data/inventory/asset-register.yaml` with custodians and classifications.

### ISO27001-003 Extend ops logging

- **Risk**: 🟡 Medium
- **Owner**: Engineering
- **Due**: 2025-11-22
- **Summary**: Capture config doctor decisions and Prefect deployment changes in an append-only log to improve traceability.
- **Evidence**: Logging implementation PR, sample log excerpt, updated matrix entry.

### ISO27001-004 Define supplier risk register

- **Risk**: 🔴 High
- **Owner**: Procurement & Security
- **Due**: 2025-12-06
- **Summary**: Document third-party services with risk ratings, contracts, and review cadence; align with POPIA transfer analysis.
- **Evidence**: Supplier register maintained at `docs/governance/supplier-register.md`, review meeting notes appended per quarter.

### ISO27001-005 Schedule legal reviews

- **Risk**: 🟡 Medium
- **Owner**: Compliance
- **Due**: 2025-12-13
- **Summary**: Set biannual legal review of compliance matrix, capturing scope changes and regulatory updates.
- **Evidence**: Review calendar invite, annotated matrix revisions.

## SOC 2

### SOC2-001 Publish code of conduct

- **Risk**: 🟡 Medium
- **Owner**: Leadership & People Ops
- **Due**: 2025-11-15
- **Summary**: Draft and distribute operator code of conduct with acknowledgement workflow integrated into onboarding.
- **Evidence**: Code of conduct document, acknowledgement tracker.

### SOC2-002 Maintain risk register

- **Risk**: 🔴 High
- **Owner**: Security
- **Due**: 2025-11-22
- **Summary**: Convert threat model findings into a living risk register with scoring, mitigation status, and links back to controls.
- **Evidence**: Risk register maintained in `docs/security/risk-register.md`, update log appended per review, linkage to threat model revisions.
- **Status**: ✅ Completed 2025-10-26 — baseline SOC 2 risk register created in `docs/security/risk-register.md` with scoring and mitigation owners.

### SOC2-003 Enhance change records

- **Risk**: 🟡 Medium
- **Owner**: Engineering
- **Due**: 2025-11-29
- **Summary**: Extend PR template or automation to capture reviewer approvals, deployment outcomes, and rollback decisions.
- **Evidence**: Updated PR template, sample completed record.

### SOC2-004 Define alert thresholds

- **Risk**: 🟡 Medium
- **Owner**: Observability
- **Due**: 2025-11-29
- **Summary**: Specify alert thresholds, escalation steps, and capture runbooks for Prefect/OpenTelemetry signals.
- **Evidence**: Alert catalog doc, runbook links, monitoring configuration screenshot.

### SOC2-005 Harden confidentiality controls

- **Risk**: 🔴 High
- **Owner**: Platform
- **Due**: 2025-12-13
- **Summary**: Implement access-controlled storage, encryption at rest, and audit logging for refined data exports.
- **Evidence**: Storage configuration captured under `docs/explanations/architecture.md`, access log samples archived in `dist/logs/access/`, updated architecture diagram.

Track progress here and mirror high-risk milestones in `Next_Steps.md` under Quality Gates.
