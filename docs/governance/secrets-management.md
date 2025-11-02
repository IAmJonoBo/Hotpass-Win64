---
title: Governance — secrets management strategy
summary: Decision record and implementation plan for Hotpass secrets across CLI, Prefect, and telemetry components.
last_updated: 2025-11-02
---

Hotpass processes regulated datasets and depends on registry APIs, Prefect deployments, and telemetry exporters that all require credentials. This document captures the selected platform for managing those secrets, the evaluation of alternatives, and the rollout plan.

## Decision summary

- **Chosen platform:** HashiCorp Vault, operated in high-availability mode with GitHub OIDC integration for CI and workload identity federation for Prefect workers.
- **Scope:** Registry API keys, Prefect service account tokens, Streamlit dashboard passwords, telemetry exporters (OpenTelemetry collector, Slack webhooks), and downstream data access credentials.
- **Why now:** POPIA remediation item [POPIA-001](../compliance/remediation-backlog.md#popia-001-automate-consent-validation) requires auditable consent enforcement and the backlog flagged secrets drift as a critical risk. Aligning on a single platform unblocks automation work and upcoming compliance audits.

## Options considered

| Option                            | Summary                                                                                       | Pros                                                                                    | Cons                                                                                                                                            |
| --------------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| **HashiCorp Vault (self-hosted)** | Deploy Vault with integrated storage, namespace per environment, and GitHub OIDC auth method. | Fine-grained policies, audit logging, dynamic secrets engines, broad ecosystem support. | Operational overhead (HA cluster, unseal process), requires platform ownership.                                                                 |
| **AWS Secrets Manager**           | Use managed service with IAM roles and rotation workflows.                                    | Fully managed, integrates with AWS workloads, built-in rotation helpers.                | Locks platform to AWS (current roadmap keeps Hotpass cloud-agnostic), GitHub OIDC support requires additional plumbing, higher per-secret cost. |
| **SOPS + Git-backed storage**     | Encrypt secrets in git using KMS-managed keys.                                                | Simple tooling, works offline, minimal infrastructure.                                  | Requires CI bootstrap secrets, limited auditability, slower revocation/rotation, high risk of merge conflicts for frequently rotated secrets.   |

Vault best satisfies the audit and automation requirements: policies map directly to POPIA/ISO controls, audit devices cover regulator evidence, and GitHub OIDC removes long-lived CI tokens.

## Architecture

- **Control plane:** Vault HA cluster (raft storage) with auto-unseal via cloud KMS; two nodes per environment behind a load balancer.
- **Authentication:**
  - GitHub Actions authenticate via OIDC; workflows request short-lived tokens scoped to build, release, and docs jobs.
  - Prefect workers use JWT auth (Kubernetes service accounts or VM workload identities) to request dynamic credentials before triggering flows.
  - Developers use CLI login tied to SSO and enforced MFA.
- **Secrets engines:**
  - `kv-v2` for registry API keys, Streamlit dashboard credentials, and Slack webhooks.
  - Database secrets engine for future managed Postgres cache.
  - PKI engine for signing provenance manifests and CLI binaries.
- **Audit:** Enable integrated audit device streaming to object storage with 1-year retention, hashed values, and tamper-evident logs referenced in [compliance evidence catalog](../compliance/evidence-catalog.md).

## Implementation plan

1. **Provision Vault cluster** — Platform team deploys HA Vault with terraform, enabling auto-unseal and audit logging. Target completion: 2025-11-05.
2. **Bootstrap authentication** — Configure GitHub OIDC roles per workflow, Prefect worker roles per environment, and developer SSO integration. Provide runbooks for token retrieval.
3. **Migrate secrets** — Move existing environment variables into Vault paths (`hotpass/registry`, `hotpass/prefect`, `hotpass/telemetry`). Replace CI environment secrets with dynamic lookups and update documentation.
4. **Rotate credentials** — Generate new Streamlit dashboard password, registry keys, and Prefect service tokens via Vault. Store rotation evidence alongside the asset register.
5. **Enable policy enforcement** — Apply Vault policies that restrict access to least privilege and configure automated alerts when unauthorised attempts occur. Integrate alerts into the observability stack.
6. **Retire legacy storage** — Remove ad-hoc `.env` handling and ensure detect-secrets baseline stays clean. Archive proof of destruction where required.

## Integration guidance

- Update Prefect deployment blocks to fetch secrets at runtime via the `vault` block (or environment variables injected by Vault Agent).
- Streamlit dashboard reads its password from Vault during startup when running in hosted environments; document fallback for local development in [`docs/how-to-guides/configure-pipeline.md`](../how-to-guides/configure-pipeline.md).
- CI workflows authenticate using `vault write auth/github/login` with the JWT provided by GitHub OIDC and request scoped tokens for each job step. Persist generated tokens only in memory.

## Risks and mitigations

| Risk                                         | Impact                                            | Mitigation                                                                                                     |
| -------------------------------------------- | ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Vault outage blocks deployments              | Pipeline and dashboard cannot access credentials. | Run HA cluster with health checks, enable auto-unseal, and document manual recovery.                           |
| Misconfigured policies leak secrets          | POPIA breach and SOC 2 finding.                   | Peer-review policy changes, run automated integration tests, and audit logs daily.                             |
| Migration stalls due to teams lacking access | Secrets continue living in `.env` files.          | Provide onboarding sessions, automate bootstrap scripts, and make Vault access part of the platform checklist. |

## Next steps

- Track migration progress in `Next_Steps.md` under the DevOps workstream.
- Update Prefect deployment templates to demonstrate Vault integration.
- Review audit logs during the first compliance verification cadence to confirm evidence capture.
