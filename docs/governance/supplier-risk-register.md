---
title: Supplier risk register
summary: Inventory and review cadence for key suppliers supporting the Hotpass platform.
last_updated: 2025-11-02
---

# Supplier risk register

| Supplier | Service scope                                  | Classification | Last review | Next review | Notes                                                                            |
| -------- | ---------------------------------------------- | -------------- | ----------- | ----------- | -------------------------------------------------------------------------------- |
| Prefect  | Orchestration platform for scheduled runs      | High           | 2025-10-20  | 2026-01-20  | Tokens rotated monthly; ensure worker nodes restrict egress.                     |
| Slack    | Incident communication and stakeholder updates | Medium         | 2025-10-20  | 2026-01-20  | Confirm workspace retention matches POPIA requirements.                          |
| Vault    | Secrets management for CI and Prefect workers  | High           | 2025-10-20  | 2026-01-20  | Audit logs reviewed quarterly; ensure namespace policies remain least privilege. |
| GitHub   | Source control and CI/CD                       | High           | 2025-10-20  | 2026-01-20  | Actions runners restricted to pinned images; monitor security advisories weekly. |

Document findings from each quarterly verification run by appending rows with review dates
and remediation actions. Link deeper assessments or supplier questionnaires in the notes
column when available.
