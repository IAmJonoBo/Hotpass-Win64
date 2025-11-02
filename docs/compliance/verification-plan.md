---
title: Compliance — verification plan
summary: Review cadence, trigger events, and measurement approach for each compliance framework.
last_updated: 2025-11-02
---

## Cadence overview

| Framework | Routine cadence                                            | Trigger-based checks                                   | Measurement approach                                                                     | Tooling                                                      |
| --------- | ---------------------------------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| POPIA     | Quarterly evidence refresh and DSAR SLA review.            | Breach events, enrichment changes, DSAR escalations.   | Sample DSAR tickets, confirm consent enforcement logs, verify incident playbook updates. | Prefect run logs, DSAR register, incident playbook.          |
| ISO 27001 | Quarterly ISMS review; biannual legal update.              | Supplier onboarding, significant architecture changes. | Review asset register deltas, supplier risk ratings, policy approval log.                | Asset register, supplier register, policy approval workflow. |
| SOC 2     | Quarterly control testing; monthly monitoring calibration. | New service launch, major deployment pipeline change.  | Validate change records, alert thresholds, confidentiality controls.                     | GitHub PR records, monitoring alerts, storage access logs.   |

## Verification steps

## Automation support

- Run `uv run python ops/compliance/run_verification.py --reviewer "<name>" --notes "<summary>"` after each cadence.
- The helper updates `data/compliance/verification-log.json` and writes optional summaries for evidence packs.
- Use the generated log when refreshing the [evidence catalog](./evidence-catalog.md) and supplier register entries.

### POPIA

- Confirm POPIA matrix entries align with latest consent rules in [`apps/data-platform/hotpass/compliance.py`](../../apps/data-platform/hotpass/compliance.py) and profile templates.
- Review DSAR automation reports to ensure SLA adherence and evidence retention matches [`docs/compliance/evidence-catalog.md`](./evidence-catalog.md).
- Simulate breach notification workflow annually to verify contact chains and regulator templates per POPIA-004.

### ISO 27001

- Reconcile asset register contents against [`docs/explanations/architecture.md`](../explanations/architecture.md) and Prefect deployment inventory.
- Validate supplier risk assessments include Prefect, Slack, and survey tools identified in [`docs/metrics/metrics-plan.md`](../metrics/metrics-plan.md).
- Ensure policy approval log reflects quarterly reviews and captures leadership sign-off.

### SOC 2

- Sample change records to confirm reviewer approvals, QA evidence, and deployment outcomes are stored per SOC2-003.
- Review monitoring alert thresholds and escalation evidence; align with Prefect/OpenTelemetry configuration.
- Inspect confidentiality controls for refined data exports, verifying access logs and encryption posture.

## Metrics and reporting

- Publish compliance summary alongside DORA/SPACE metrics during monthly roadmap reviews.
- Track remediation backlog progress in `Next_Steps.md` and highlight overdue 🔴 items to leadership.
- Maintain audit trail of verification sessions (date, participants, findings) within each framework matrix via change logs or appended notes.
