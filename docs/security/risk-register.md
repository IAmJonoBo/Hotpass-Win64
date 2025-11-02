---
title: Security — risk register
summary: Baseline SOC 2-aligned risk register derived from the Hotpass threat model with scoring, owners, and treatments.
last_updated: 2025-11-02
---

This register translates the Hotpass threat model into SOC 2-aligned risks with likelihood, impact, and mitigation tracking. Scores use a 1–5 scale (5 = highest).

## Risk scoring legend

- **Impact** — Severity if the risk materialises.
- **Likelihood** — Probability based on current controls.
- **Exposure** — Impact × Likelihood.
- **Status** — Current treatment state (Open, In progress, Mitigated).

## Risks

| ID    | Description                                                                        | Surface / Assets                                            | Impact | Likelihood | Exposure | Owner                 | Status      | Mitigation / Notes                                                                                                             |
| ----- | ---------------------------------------------------------------------------------- | ----------------------------------------------------------- | ------ | ---------- | -------- | --------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------ |
| R-001 | Dashboard shared-secret leaked or reused broadly, granting unauthorised access.    | Streamlit dashboard, refined exports, audit logs.           | 4      | 3          | 12       | Platform              | In progress | Vault-managed password rotation, planned SSO proxy, access logging backlog (SOC2-005).                                         |
| R-002 | Prefect credentials abused to run malicious flows or exfiltrate data.              | Prefect work pool tokens, refinement pipeline.              | 5      | 2          | 10       | Engineering           | In progress | Vault-issued short-lived tokens, Prefect deployment policies, monitoring of unusual flow executions.                           |
| R-003 | Consent validation bypass leads to unlawful processing of personal data.           | Compliance module, raw/refined datasets.                    | 5      | 2          | 10       | Product & Engineering | Mitigated   | Automated consent enforcement in `hotpass.compliance`, audit logs retained under `data/logs/prefect/`, quarterly verification. |
| R-004 | Supply-chain compromise through unsigned GitHub Actions or dependencies.           | CI pipelines, release artifacts.                            | 4      | 3          | 12       | DevOps                | Open        | Pin GitHub Actions to SHAs, publish artifact checksums, integrate Sigstore once trust chain issues resolved.                   |
| R-005 | Secrets sprawl results in credential leakage from local environments.              | Registry API keys, telemetry webhooks, dashboard passwords. | 5      | 2          | 10       | DevOps                | In progress | Vault strategy approved; migrate secrets, enable audit logging, retire ad-hoc `.env` files.                                    |
| R-006 | Enrichment cache stores outdated or ungoverned data, breaching retention policies. | `data/.cache/enrichment.db`, enrichment connectors.         | 3      | 3          | 9        | Engineering           | Open        | Implement purge schedule tied to retention matrix, evaluate managed datastore with Vault credentials.                          |

## Review cadence

- Update this register during the quarterly compliance verification window and after material architecture or threat model changes.
- Reference mitigation evidence in [`docs/compliance/evidence-catalog.md`](../compliance/evidence-catalog.md) and `Next_Steps.md`.
- Archive prior versions in `docs/security/risk-register/` if risk scoring shifts significantly.
