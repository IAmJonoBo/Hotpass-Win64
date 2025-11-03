---
title: Hotpass documentation
summary: Learn how to install, operate, and extend the Hotpass data refinement platform.
owner: n00tropic
last_updated: 2025-11-18
---

Welcome to the Hotpass knowledge base. The navigation is organised around three pillars:

1. **Overview** — orient yourself with system diagrams, platform scope, and the documentation architecture itself.
2. **In-depth guides** — follow tutorials, how-to recipes, and operational runbooks that keep the pipelines and orchestration
   platform healthy.
3. **API & automation reference** — consult CLI verbs, Smart Import workflows, schema contracts, governance artefacts, and
   compliance playbooks.

Use the sections below to reach the material that matches your task. Each toctree exposes the same structure surfaced in
[`architecture/documentation-architecture.md`](architecture/documentation-architecture.md).

```{toctree}
:maxdepth: 1
:caption: Overview

/architecture/documentation-architecture
/explanations/architecture
/explanations/platform-scope
/explanations/data-quality-strategy
```

```{toctree}
:maxdepth: 1
:caption: Tutorials & quickstarts

/tutorials/quickstart
/tutorials/enhanced-pipeline
```

```{toctree}
:maxdepth: 1
:caption: Implementation guides & operations

/how-to-guides/configure-pipeline
/how-to-guides/format-and-validate
/how-to-guides/orchestrate-and-observe
/how-to-guides/run-a-backfill
/how-to-guides/read-data-docs
/how-to-guides/agentic-orchestration
/how-to-guides/bootstrap-execute-mode
/how-to-guides/dependency-profiles
/how-to-guides/manage-prefect-deployments
/how-to-guides/manage-arc-runners
/how-to-guides/manage-data-versions
/how-to-guides/model-lifecycle-mlflow
/operations/prefect-backfill-guardrails
/operations/lineage-smoke-tests
/operations/staging-rehearsal-plan
/operations/foundation-retro
/observability/index
```

```{toctree}
:maxdepth: 1
:caption: API & automation reference

/reference/cli
/reference/mcp-tools
/reference/data-model
/reference/profiles
/reference/expectations
/reference/smart-import-plan
/reference/repo-inventory
/reference/source-mapping
/reference/research-log
/reference/data-docs
/reference/schema-exports
/reference/schemas
```

```{toctree}
:maxdepth: 1
:caption: Governance, metrics, and audits

/governance/gap-analysis
/governance/audit-baseline
/governance/project-charter
/governance/pr-playbook
/governance/upgrade-final-report
/governance/supplier-risk-register
/governance/secrets-management
/governance/data-governance-navigation
/DOCUMENTATION_AUDIT_2025-11-02
/DOCUMENTATION_AUDIT_2025-11-18
/metrics/metrics-plan
/metrics/devex-audit
/metrics/forecast
/roadmap
/roadmap/30-60-90
/roadmap/dependency-matrix
/roadmap/deployment-notes
/platform/tech-radar
```

```{toctree}
:maxdepth: 1
:caption: Compliance & security

/compliance/index
/compliance/popia/maturity-matrix
/compliance/iso-27001/maturity-matrix
/compliance/soc2/maturity-matrix
/compliance/verification-plan
/compliance/remediation-backlog
/compliance/evidence-catalog
/compliance/presidio-redaction
/security/quality-gates
/security/risk-register
/security/supply-chain-plan
/security/threat-model
/security/tooling
```

```{toctree}
:maxdepth: 1
:caption: Developer experience & UX

/CONTRIBUTING
/CONTRIBUTING 2
/README
/style
/devex/baseline
/devex/experiments
/devex/review-loop
/devex/backstage-mvp
/ux/heuristic-review
/ux/accessibility-checklist
/ux/accessibility-testing
```

For additional lineage and provenance insight, launch the [Marquez lineage UI](observability/marquez.md) and pair the output with
[Data Docs](reference/data-docs.md) while triaging validation issues.
