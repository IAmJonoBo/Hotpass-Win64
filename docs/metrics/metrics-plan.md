---
title: Metrics — delivery and DevEx plan
summary: Definitions, targets, and instrumentation approach for Hotpass DORA and SPACE metrics.
last_updated: 2025-11-02
---

This plan defines how Hotpass will measure delivery performance and developer experience using the DORA Four Keys and the SPACE framework. It also records telemetry tooling, integrations, and open assumptions that require validation before rollout.

## Measurement principles

- Reuse existing CI/CD logs, Prefect run metadata, and observability signals before introducing new agents.
- Automate metric capture and dashboards so that manual data entry is a last resort.
- Triangulate quantitative signals with lightweight developer feedback surveys each quarter.
- Store metric definitions and ownership in version control for transparency and auditability.

## DORA metrics

| Metric                      | Definition                                                                                 | Target band                                                     | Instrumentation                                                                                                                                                                            |
| --------------------------- | ------------------------------------------------------------------------------------------ | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Deployment frequency        | Count of production data refreshes (CLI or Prefect flow) promoted to downstream consumers. | 3–5 deployments per week with surge tolerance for urgent fixes. | Tag Prefect `refinement_pipeline_flow` runs with environment metadata; aggregate successful runs from Prefect Orion API or CLI and align with GitHub Actions `process-data.yml` successes. |
| Lead time for changes       | Time from merge to production run completion for code affecting pipeline or docs.          | ≤ 24 hours p50, ≤ 72 hours p90.                                 | Capture commit timestamps via GitHub API, pair with Prefect flow completion events; store aggregates in Four Keys BigQuery dataset or lightweight DuckDB file.                             |
| Change failure rate         | Percentage of deployments that require rollback, hotfix, or generate Sev1/Sev2 incidents.  | ≤ 10% of deployments per rolling 4 weeks.                       | Label Prefect runs with result status; log incident tickets in `Next_Steps.md` and incident tracker. Automate failure tagging via Prefect result state and GitHub issue labels.            |
| Mean time to recover (MTTR) | Time between detection of a failed deployment and restoration of healthy state.            | ≤ 4 hours p90.                                                  | Leverage Prefect failure alerts and Ops Slack notifications; capture recovery timestamps when successful rerun completes. Log incidents in shared runbook for audit.                       |

## SPACE metrics

| Dimension                     | Signal                                                                               | Target band                                                   | Instrumentation                                                                                                                                         |
| ----------------------------- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Satisfaction & well-being     | Quarterly Developer Satisfaction pulse (Likert 1–5) covering docs, tooling, support. | Average ≥ 4 with ≤ 10% reporting 2 or below.                  | Send survey via Google Forms or Typeform to engineering and docs contributors; store anonymised results in shared drive referenced in governance notes. |
| Performance                   | Lead time p50/p90 (shared with DORA), plus automated QA pass rate on first attempt.  | ≥ 80% of PRs pass QA suite without re-run.                    | Parse GitHub Actions logs for `process-data.yml` outcomes; feed into Four Keys dataset and weekly summary.                                              |
| Activity                      | Number of merged PRs, docs updates, and Prefect flow runs per contributor.           | Contextual; monitor for sudden drop-offs.                     | Use GitHub GraphQL API to export merged PR counts; correlate with Prefect run data.                                                                     |
| Communication & collaboration | Review turnaround time and Slack triage response.                                    | First-response SLA ≤ 4 working hours in Slack/issue comments. | Track via Slack analytics export (manual monthly) and GitHub review timestamps; document deltas in `Next_Steps.md`.                                     |
| Efficiency & flow             | Time spent waiting on dependencies/tooling vs active development (self-reported).    | Reduce reported blocked time by 20% quarter-over-quarter.     | Include flow-efficiency question in quarterly survey; triangulate with CI queue time from GitHub Actions metrics API.                                   |

## Instrumentation roadmap

1. **Baseline extraction (Week 0–2)**
   - Enable Prefect Orion API for local telemetry; confirm authentication approach for CI runners.
   - Configure GitHub Actions workflow run exports to BigQuery or DuckDB via scheduled job.
   - Stand up temporary spreadsheet summarising manual metrics until automation is verified.
   - Adopt the telemetry registry in CLI/Prefect code paths so all spans and histograms include service, environment, and exporter metadata. See [observability registry and policy](../observability/index.md) for configuration details.
2. **Automation (Week 3–6)**
   - Deploy the [Four Keys](https://github.com/GoogleCloudPlatform/fourkeys) stack via Terraform or Docker Compose; feed GitHub and Prefect event streams.
   - Configure Prefect `result_storage` to emit JSON logs with run metadata (status, runtime, owner) to object storage for ingestion.
   - Add instrumentation hooks in `apps/data-platform/hotpass/orchestration.py` to push structured logs when flows start/finish.
3. **Feedback loops (Week 7+)**
   - Launch quarterly Developer Experience survey (SPACE satisfaction and flow questions) via Typeform; automate reminders.
   - Review metrics with engineering + product monthly; capture actions in `Next_Steps.md` and update [docs/roadmap.md](../roadmap.md).

## Tooling matrix

| Need              | Recommended tooling                                                     | Notes                                                                                                              |
| ----------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| DORA aggregation  | Google Four Keys (BigQuery + Data Studio) or open-source DuckDB fork.   | Confirm access to Google Cloud or self-hosted alternative; ensure service account secrets managed via GitHub OIDC. |
| Flow telemetry    | Prefect Orion API & serverless storage (S3/GCS/Azure Blob).             | Verify network egress permissions from CI; fallback to local SQLite for air-gapped runs.                           |
| Metrics warehouse | DuckDB files stored in `data/metrics/` or managed warehouse (BigQuery). | Validate concurrency and retention requirements; define rotation policy.                                           |
| Dashboards        | Looker Studio (if GCP) or Metabase/Grafana.                             | Align with security team on single sign-on and access logging.                                                     |
| DevEx surveys     | Typeform or Google Forms with anonymised exports.                       | Confirm data residency and POPIA compliance before collecting responses.                                           |
| Alerting          | Slack notifications via Prefect automations and GitHub Actions.         | Validate Slack webhook secrets in GitHub and rotation cadence.                                                     |

## Integration assumptions to validate

- Prefect server endpoints are reachable from GitHub-hosted runners; if not, mirror event data via S3 uploads.
- Organisation approves use of Google Cloud for Four Keys; otherwise evaluate self-hosted Postgres + Metabase stack.
- Slack workspace allows incoming webhooks or app-based notifications for metric breaches.
- POPIA compliance review confirms storing anonymised survey results in external SaaS (Typeform/Google) is acceptable; otherwise host on internal survey tool.
- Logging of DORA events must avoid including sensitive data (PII, customer-specific identifiers); update logging filters before enabling exporters.

## Operating cadence

- Publish monthly DORA/SPACE snapshot in the roadmap Executive Summary.
- Revisit target bands every quarter based on trend analysis and risk appetite.
- Maintain raw metric exports under version control or controlled storage; document schema in `docs/reference/data-model.md` when finalised.
- Track remediation actions and instrumentation gaps in `Next_Steps.md` with owners and due dates.
