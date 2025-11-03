---
title: Operator hub
toc_hide: true
summary: End-user guide for running Hotpass pipelines, reviewing outputs, and responding to quality signals.
last_updated: 2025-11-03
---

# Operator hub

Hotpass operators can jump in via these entry points:

- **Import & refinement** – how to prepare workbooks, run Smart Import, and monitor Live Processing.
- **Governance & contracts** – review generated contracts, approvals, and lineage.
- **Quality signals** – understand dashboards, telemetry, and when to escalate.

```text
[Profile & data prep]
        |
        v
[hotpass refine / Smart Import] --> [Refined workbook] --> [Contracts explorer]
        |
        v
[QA & approvals panel] --> [Lineage telemetry] --> [Operator escalation]
```

```{toctree}
:maxdepth: 1
:hidden:

Quickstart tutorial </tutorials/quickstart>
Smart import playbook </how-to-guides/dependency-profiles>
Dataset import panel </how-to-guides/format-and-validate>
Contracts and governance </reference/smart-import-plan>
Approvals & HIL workflow </how-to-guides/agentic-orchestration>
Dashboards & telemetry </observability/index>
Lineage troubleshooting </operations/lineage-smoke-tests>
Support & escalation </governance/data-governance-navigation>
```

## Start here

1. Follow the [quickstart tutorial](/tutorials/quickstart.md) to ingest your first workbook.
2. Use the [Smart Import dependency profiles](/how-to-guides/dependency-profiles.md) to select the correct pipeline behaviour.
3. Monitor progress with the [dashboard widgets](/observability/index.md) and [Lineage smoke tests](/operations/lineage-smoke-tests.md).

## Contracts & approvals

- The [Contracts explorer](/reference/smart-import-plan.md) surfaces YAML/JSON contracts in `dist/contracts`.
- Approvals and HIL workflows are documented in [Agentic orchestration](/how-to-guides/agentic-orchestration.md).
- When quality gates fail, check the [QA runbooks](/operations/prefect-backfill-guardrails.md) before escalating.

## Support

Escalate operational issues in `#hotpass-support` and follow the [data governance navigation guide](/governance/data-governance-navigation.md)
for ownership maps. For compliance-specific questions, reach out via the contacts in [compliance/remediation-backlog.md](/compliance/remediation-backlog.md).
