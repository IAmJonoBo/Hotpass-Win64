---
title: Hotpass upgrade final report
summary: Consolidated critical-reasoning checks and delivery package for the Hotpass frontier upgrade initiative.
last_updated: 2025-11-02
---

## 1. Critical-reasoning checks

### 1.1 Pre-mortem

If the upgrade initiative fails, the most plausible narrative begins with incomplete secrets management. Without an approved platform, teams keep embedding ad-hoc credentials in Prefect deployments and dashboard configs. A minor contractor breach exposes POPIA-regulated data, prompting an emergency shutdown of enrichment features. Incident response diverts engineering, stalling the observability rollout. Meanwhile, backlog pressure forces shortcuts: pipeline changes ship without the agreed control matrix, and DX guardrails regress. Stakeholders lose trust, the roadmap slips by two quarters, and compliance debt spikes because evidence cannot be produced during audits.

### 1.2 Failure Modes and Effects Analysis (FMEA)

| Failure mode                       | Effect                                                                   | Severity (1-10) | Occurrence (1-10) | Detection (1-10) | RPN | Mitigations                                                                                                        |
| ---------------------------------- | ------------------------------------------------------------------------ | --------------- | ----------------- | ---------------- | --- | ------------------------------------------------------------------------------------------------------------------ |
| Secrets platform decision stalls   | Manual credential handling persists, increasing leak risk                | 9               | 6                 | 6                | 324 | Secure owner decision by sprint end, prototype Vault vs SOPS, enforce interim detect-secrets and rotation playbook |
| Dashboard auth uplift pending      | Shared-secret gate live, but lack of SSO/auditing risks credential reuse | 6               | 4                 | 5                | 120 | Maintain secret rotation, add access logging, and scope SSO rollout via reverse proxy                              |
| Supply-chain gates drift           | Provenance/SBOM scripts unused, blocking SLSA uplift                     | 7               | 4                 | 6                | 168 | Automate in CI, publish attestation storage policy, rotate signing keys                                            |
| Prefect policy enforcement delayed | Misconfigured flows bypass validation causing runtime failures           | 6               | 5                 | 4                | 120 | Add policy-as-code checks, integrate with deployment templates, simulate failure                                   |
| Quality reporting stagnates        | Stakeholders lose confidence in data trustworthiness                     | 6               | 4                 | 5                | 120 | Automate briefing dashboards, add regression tests for CLI reports, embed in release checklist                     |

### 1.3 Attacker and chaos opportunities

- **Pipeline configuration injection**: Prefect deployments pull parameters from environment variables without full validation. An attacker with CI access can insert malicious expectation suites that exfiltrate refined data.
- **Dashboard shared-secret exposure**: The Streamlit dashboard now requires a password, but leaked secrets or absent session logging could still expose data when shared broadly. Prioritise SSO or identity-aware proxy hardening.
- **Dependency poisoning window**: Renovate automation exists but commits are unsigned; a compromised dependency mirror can inject modified wheels before provenance scripts run.
- **Observability exporter defaults**: Tracing endpoints default to public URLs. Misconfigured collectors could leak metadata to untrusted networks.
- **Backstage template drift**: Scaffolding scripts might skip latest security additions, enabling new services without SBOM/policy hooks.

### 1.4 Unknown catalog

| Unknown                            | Evidence required                                                                    | Owner       | Due        | Status |
| ---------------------------------- | ------------------------------------------------------------------------------------ | ----------- | ---------- | ------ |
| Preferred secrets management stack | Comparative analysis of Vault, AWS Secrets Manager, SOPS; cost and compliance review | DevOps      | 2025-11-22 | Open   |
| Dashboard hosting constraints      | Platform decision on internal vs external exposure, TLS termination details          | Platform    | 2025-11-22 | Open   |
| Prefect policy enforcement scope   | Confirmation of parameters requiring validation, mapping to compliance controls      | Engineering | 2025-11-22 | Open   |
| Provenance storage location        | Decision on artifact repository with immutability and access auditing                | Security    | 2025-11-29 | Open   |
| Semgrep trust chain fix            | Trusted root store or offline ruleset plan enabling CI runs                          | DevOps      | 2025-11-29 | Open   |

## 2. Executive summary

### 2.1 Top risks, impacts, quick wins

1. **Secrets migration execution** → POPIA breach potential → Deliver Vault rollout plan, migrate credentials, and monitor audit trail per governance strategy.
2. **Dashboard auth uplift** → Shared secret may leak without rotation/logging → Add access logging and move to SSO-backed proxy.
3. **Supply-chain drift** → Attestation gaps undermine SLSA targets → Wire SBOM/provenance scripts into CI with policy enforcement.
4. **Prefect policy lag** → Runtime instabilities → Implement validation hooks and dry-run suite before promotion.
5. **Quality signal decay** → Stakeholder trust erosion → Automate report generation and embed acceptance metrics into release sign-off.

### 2.2 Maturity snapshot

| Framework         | Current                      | Target   | Gap focus                                                            |
| ----------------- | ---------------------------- | -------- | -------------------------------------------------------------------- |
| NIST SSDF v1.1    | Baseline                     | Advanced | Formalize secrets governance, automate verification                  |
| OWASP SAMM        | Managed-Ad Hoc mix           | Managed  | Institutionalize security testing cadence, document metrics          |
| OWASP ASVS        | Level 1+                     | Level 2  | Close auth, input validation, and logging controls for CLI/dashboard |
| SLSA              | Level 1                      | Level 2  | Continuous attestations, isolated builds                             |
| OpenSSF Scorecard | 6.5 (est.)                   | ≥7.5     | Strengthen dependency, CI, and review signals                        |
| ISO/IEC 25010     | Maint., Reliability moderate | High     | Observability/SLOs, UX validation                                    |
| ISO/IEC 5055      | Emerging                     | Managed  | Reduce structural debt in pipeline modules                           |

## 3. Findings

Each finding lists **Title • Severity • Confidence • Evidence • Affected assets** followed by remediation guidance.

1. **Secrets management undecided • High • Medium • evidence: roadmap and Next_Steps owner backlog • Assets: Prefect deployments, connectors**. _Residual risk_: exposure of regulated data. _Standards_: {SSDF: PO.3, PW.4 | SAMM: S3-B | ASVS: 2.1.1 | ISO 25010: Security}. _Actions_: finalize platform selection, implement rotation policy, integrate with deployment templates. _Trade-offs_: additional infra overhead vs compliance readiness. _Exposure_: reduced once platform live and audit logging enabled.
2. **Dashboard auth uplift • Medium • Medium • evidence: shared-secret gate shipped; `Next_Steps.md` backlog • Assets: Streamlit dashboard**. _Standards_: {SSDF: PW.8 | SAMM: OE2 | ASVS: 2.1.2, 4.1.3 | ISO 25010: Security, Usability}. _Actions_: rotate shared secret, add access logging, implement SSO-backed proxy. _Residual risk_: reduced but present until SSO live.
3. **Supply-chain automation manual • Medium • Medium • evidence: SBOM/provenance scripts require CI wiring • Assets: build pipeline, artifacts**. _Standards_: {SSDF: PS.3, PO.5 | SLSA: 2 | Scorecard: SAST, Signed Releases | ISO 5055: Reliability}. _Actions_: integrate scripts, add policy gate, publish attestation storage location. _Exposure_: tampering risk until automation complete.
4. **Prefect policy enforcement pending • Medium • Medium • evidence: Next_Steps tasks • Assets: Orchestration runtime**. _Standards_: {SSDF: PW.1, PW.9 | SAMM: OE1 | ASVS: 1.9.1}. _Actions_: define validation rules, implement tests, tie to deployment CLI. _Residual risk_: misconfigured flows causing outages.
5. **Quality report automation incomplete • Medium • Low • evidence: coverage results and Next_Steps**. _Standards_: {SSDF: RV.1 | ISO 25010: Quality in use}. _Actions_: maintain tests, schedule report generation, integrate dashboards. _Residual risk_: stakeholder communication gap.

## 4. Supply-chain posture

Hotpass generates CycloneDX SBOMs and provenance statements via scripts in `ops/supply_chain/`, but execution depends on manual invocation. GitHub Actions lacks enforced signing, and dependencies rely on Renovate without commit verification. Advancing to SLSA Level 2 requires CI-integrated SBOM/provenance publication, signing keys managed via KMS, artifact retention policies, and Scorecard-aligned workflows (dependency update freshness, branch protection, CodeQL/Semgrep once trust store resolved).

## 5. Delivery, DX, and UX narrative

Developer experience audits (`docs/metrics/devex-audit.md`) highlight improved tooling yet underscore secrets, telemetry, and compliance follow-ups. SPACE metrics remain partially manual; instrumentation via Prefect/OpenTelemetry must stabilize before automation. UX reviews (`docs/ux/heuristic-review.md`) confirm alignment with Nielsen heuristics but call for authenticated previews and accessibility automation. Establishing quarterly DevEx reviews and automated accessibility scans keeps ISO 9241-210 objectives in view.

### 5.1 Governance workflow telemetry (2025-10-28)

- **commitlint** (`run 18875044612`) — success in 20 s for PR #101 (`codex/implement-github-actions-enhancements`); no manual label adjustments were required before merge.
- **pr-labeler** (`run 18875148327`) — success in 8 s after label seeding; repository labels now include `type:*`, `scope:dependencies`, `scope:governance`, `prefect`, `uv`, `skip-changelog`, and `breaking-change` as confirmed via `gh label list`.
- **release-drafter** (`run 18875134498`) — success in 96 s on push `121cbe6753e0e5a4017baaf82bcc21fccfca67bb` (merge of PR #101); release draft reflects automated taxonomy with no manual notes needed.

## 6. PR-ready artefacts

```text
hotpass/
└── docs/governance/upgrade-final-report.md
```

```diff
+++ docs/governance/upgrade-final-report.md
@@
+# Hotpass upgrade final report
+...
```

## 7. 30/60/90 roadmap

| Horizon | Item                                             | Owner role            | Effort | Risk reduction           | Dependencies                              | Verification                                        |
| ------- | ------------------------------------------------ | --------------------- | ------ | ------------------------ | ----------------------------------------- | --------------------------------------------------- |
| 30      | Choose secrets platform and pilot integration    | DevOps + Security     | M      | High (breach prevention) | Infra budget, compliance review           | Successful pilot in staging, audit log sample       |
| 30      | Add dashboard access logging & scope SSO rollout | Platform              | S      | High (access control)    | Secrets platform decision                 | Shared-secret rotation runbook, proxy plan approved |
| 60      | Automate SBOM & provenance in CI                 | DevOps                | M      | Medium (supply-chain)    | Secrets platform, artifact repo           | Signed attestation in CI run                        |
| 60      | Prefect deployment policy checks                 | Engineering           | M      | Medium (reliability)     | Config schema update                      | QA suite run with failing policies                  |
| 90      | Automate quality report distribution             | Product + Engineering | S      | Medium (trust)           | Prefect policies, telemetry stabilization | Acceptance report delivered post-release            |
| 90      | Implement Semgrep with trusted root              | Security              | S      | Medium (SAST coverage)   | Root store fix                            | Passing Semgrep pipeline                            |

## 8. Assumptions & unknowns

- Secrets platform funding and approval will be available this quarter.
- CI runners can access signing infrastructure once configured.
- Stakeholders accept staged rollout for dashboard auth, with downtime window for cutover.
- Semgrep issue stems from sandbox trust chain, not rule incompatibility.

## 9. Appendix

- Validation commands:
  - `uv run pytest --cov=src --cov=tests --cov-report=term-missing`
  - `uv run ruff check`
  - `uv run mypy src tests scripts`
  - `uv run bandit -r src scripts`
- `uv run detect-secrets scan src tests scripts`
- `uv run uv build`
- CI enhancements to pursue: CodeQL/Semgrep once SSL fixed, provenance attestation upload jobs, dashboard accessibility tests, scheduled `uv run pre-commit run mypy --all-files` via `mypy-audit` workflow with automatic issue creation when dependency resolution fails.

## 10. Dependency & tooling matrix

| Recommendation             | Dependencies               | Tooling                                | Target versions     | Ownership           | Integration points                | Lifecycle health                           | References                                 |
| -------------------------- | -------------------------- | -------------------------------------- | ------------------- | ------------------- | --------------------------------- | ------------------------------------------ | ------------------------------------------ |
| Secrets platform rollout   | Prefect, Streamlit, CI     | HashiCorp Vault or AWS Secrets Manager | n/a                 | DevOps/Security     | Deployment templates, env loaders | Active release cadence, enterprise support | Vendor docs (to be captured post decision) |
| Dashboard auth             | Streamlit, Reverse proxy   | Traefik/NGINX + OIDC                   | Latest LTS          | Platform            | Deployment helm/docker configs    | Wide community support                     | Streamlit auth guides                      |
| Supply-chain automation    | GitHub Actions, uv         | `ops/supply_chain/*`                   | Python 3.13         | DevOps              | CI workflows                      | Maintained (weekly commits)                | CycloneDX, Sigstore docs                   |
| Prefect policy enforcement | Prefect CLI, Config doctor | Custom validation scripts              | n/a                 | Engineering         | Prefect deployment definitions    | Prefect 3 active                           | Prefect deployment policy API              |
| Quality report automation  | Prefect flows, CLI         | Great Expectations, Pandas             | Latest per lockfile | Product/Engineering | Release checklist                 | Active                                     | Great Expectations docs                    |

## 11. Research log

No new external research was required in this pass; prior references from architecture, security, and compliance documentation remain valid.

## 12. Control traceability matrix

| Control                      | Safeguards                                         | Evidence artefact                           | Verification cadence |
| ---------------------------- | -------------------------------------------------- | ------------------------------------------- | -------------------- |
| SSDF PO.3                    | Secrets platform decision, detect-secrets scanning | Next_Steps tasks, scripts/supply_chain docs | Monthly              |
| SSDF PW.8                    | Dashboard auth enforcement                         | Deployment runbook, access logs             | Release              |
| SLSA L2                      | SBOM + provenance automation                       | CI job logs, attestation storage            | Per build            |
| OWASP ASVS 2.1               | Authenticated dashboard                            | Access tests, PR checklist                  | Each deploy          |
| ISO/IEC 25010 Reliability    | Prefect policies, observability instrumentation    | QA runs, metrics plan                       | Sprint               |
| ISO/IEC 5055 Maintainability | Fitness functions, module length checks            | ops/quality/fitness_functions.py            | Per PR               |

## 13. Agent runbook & handover

1. **Bootstrap**: Review this report, `Next_Steps.md`, and roadmap updates. Confirm baseline QA suite status.
2. **Secrets track**: Execute platform evaluation, document decision, integrate into deployment templates, and update evidence catalog.
3. **Supply-chain track**: Wire SBOM/provenance scripts into CI, configure signing, and document attestations.
4. **Observability & reliability**: Implement Prefect policy checks, extend fitness functions if thresholds change, ensure telemetry configuration is version-controlled.
5. **UX & communications**: Enforce dashboard auth, schedule accessibility scans, automate quality report distribution, brief stakeholders via release notes.
6. **Validation & handover**: Re-run QA suite, update Next_Steps and roadmap artefacts, prepare PR summary referencing this report, highlight residual risks and rollback steps.
