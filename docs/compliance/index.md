---
title: Compliance — framework baseline
summary: Overview of Hotpass compliance frameworks, maturity scoring, evidence mapping, and remediation approach.
last_updated: 2025-11-02
---

# Compliance framework baseline

The Hotpass governance programme spans POPIA, ISO 27001, and SOC 2. This index tracks baseline maturity for each framework, links controls to evidence, and consolidates remediation and verification cadences.

## Framework relationships

```{mermaid}
graph TD
    subgraph "Compliance Frameworks"
        POPIA[POPIA<br/>Data Privacy]
        ISO[ISO 27001<br/>InfoSec Management]
        SOC2[SOC 2<br/>Trust Services]
    end

    subgraph "Hotpass Controls"
        Consent[Consent Validation]
        Access[Access Controls]
        Audit[Audit Logging]
        Encrypt[Encryption]
        DSAR[Data Subject Rights]
        Incident[Incident Response]
        Risk[Risk Management]
    end

    subgraph "Evidence Sources"
        Code[Pipeline Code]
        Configs[Config Files]
        Logs[Audit Logs]
        Docs[Documentation]
        Reports[Quality Reports]
    end

    POPIA --> Consent
    POPIA --> DSAR
    POPIA --> Encrypt

    ISO --> Access
    ISO --> Audit
    ISO --> Risk
    ISO --> Incident

    SOC2 --> Access
    SOC2 --> Audit
    SOC2 --> Encrypt
    SOC2 --> Incident

    Consent --> Code
    Consent --> Logs

    Access --> Configs
    Access --> Docs

    Audit --> Logs
    Audit --> Reports

    DSAR --> Code
    DSAR --> Logs

    Risk --> Docs
    Risk --> Reports

    classDef framework fill:#e1f5ff,stroke:#333,stroke-width:2px
    classDef control fill:#fff3cd,stroke:#333,stroke-width:2px
    classDef evidence fill:#d4edda,stroke:#333,stroke-width:2px

    class POPIA,ISO,SOC2 framework
    class Consent,Access,Audit,Encrypt,DSAR,Incident,Risk control
    class Code,Configs,Logs,Docs,Reports evidence
```

## How maturity scoring works

1. **Evidence-first** — Every control references tangible artefacts such as pipeline configuration, QA outputs, or architecture documentation.
2. **Target alignment** — Each control compares the current state to the desired target and captures the gap narrative plus risk severity.
3. **Actionable backlog** — High-risk gaps feed the [remediation backlog](./remediation-backlog.md) with owners and due dates for audit traceability.
4. **Cadence discipline** — Verification checkpoints and metrics live in the [verification plan](./verification-plan.md) and are captured through the `ops/compliance/run_verification.py` helper to ensure continuous assurance.

## Framework matrices

| Framework | Scope                                                                    | Baseline maturity                                                     | Matrix                                                      |
| --------- | ------------------------------------------------------------------------ | --------------------------------------------------------------------- | ----------------------------------------------------------- |
| POPIA     | Data privacy controls for South African personal information.            | Core processing controls in place; evidence refresh cadence pending.  | [POPIA maturity matrix](./popia/maturity-matrix.md)         |
| ISO 27001 | Information security management system practices.                        | Policies drafted; risk treatment and supplier management gaps remain. | [ISO 27001 maturity matrix](./iso-27001/maturity-matrix.md) |
| SOC 2     | Trust Services Criteria for security, availability, and confidentiality. | Logging and change management strong; incident response still ad hoc. | [SOC 2 maturity matrix](./soc2/maturity-matrix.md)          |

## High-risk gap summary

| Gap ID       | Framework | Control focus                 | Current blockers                                                                | Target outcome                                                           | Evidence pointers                                                                                                                           | Backlog reference                                                                          |
| ------------ | --------- | ----------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| POPIA-001    | POPIA     | Lawful processing enforcement | Consent metadata stored but not enforced programmatically across Prefect runs.  | Runtime consent validation with auditable decision logs.                 | [`apps/data-platform/hotpass/compliance.py`](../../apps/data-platform/hotpass/compliance.py); Prefect flow logs under `data/logs/prefect/`. | [Remediation backlog](./remediation-backlog.md#popia-001-automate-consent-validation)      |
| POPIA-003    | POPIA     | Data subject rights           | DSAR exports lack SLA tracking and completion evidence.                         | Automated DSAR workflow with SLA metrics and retention log.              | [`docs/reference/cli.md`](../reference/cli.md); upcoming DSAR register location (`data/compliance/dsar/`).                                  | [Remediation backlog](./remediation-backlog.md#popia-003-implement-dsar-tracking)          |
| ISO27001-002 | ISO 27001 | Asset management              | Architecture lists assets but no centralised, classified inventory exists.      | Version-controlled asset register with custodianship metadata.           | [`docs/explanations/architecture.md`](../explanations/architecture.md); provisional asset extracts in `data/inventory/`.                    | [Remediation backlog](./remediation-backlog.md#iso27001-002-build-asset-register)          |
| ISO27001-004 | ISO 27001 | Supplier relationships        | Third-party services lack risk scoring and review cadence.                      | Supplier register covering risk ratings, contracts, review dates.        | [`docs/metrics/metrics-plan.md`](../metrics/metrics-plan.md); procurement interviews notes in `docs/governance/`.                           | [Remediation backlog](./remediation-backlog.md#iso27001-004-define-supplier-risk-register) |
| SOC2-002     | SOC 2     | Risk assessment               | Threat model gaps not translated into an actionable risk register.              | Living risk register with scoring, owners, quarterly updates.            | [`docs/security/threat-model.md`](../security/threat-model.md); future register path `docs/security/risk-register.md`.                      | [Remediation backlog](./remediation-backlog.md#soc2-002-maintain-risk-register)            |
| SOC2-005     | SOC 2     | Confidentiality controls      | Export storage relies on manual controls without logging or encryption posture. | Hardened storage with access logs and encryption configuration evidence. | [`docs/explanations/architecture.md`](../explanations/architecture.md); export job logs under `dist/logs/`.                                 | [Remediation backlog](./remediation-backlog.md#soc2-005-harden-confidentiality-controls)   |

## Supporting artefacts

- [Remediation backlog](./remediation-backlog.md) — Prioritised work to close gaps.
- [Evidence catalog](./evidence-catalog.md) — Retrieval instructions and owners for audit artefacts.
- [Verification plan](./verification-plan.md) — Cadence, measurement approach, and tooling alignment per framework.
- [Presidio redaction guide](./presidio-redaction.md) — Runtime options for ingestion-time PII scrubbing and provenance ledgers.

Update these pages whenever controls, evidence sources, or remediation statuses change. Keep `Next_Steps.md` and the [roadmap](../roadmap.md) aligned so compliance remains a first-class workstream.
