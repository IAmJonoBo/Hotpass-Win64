---
title: Resilience and observability enhancements
summary: Guardrails for SLOs, chaos experiments, and observability improvements.
last_updated: 2025-11-02
---

## SLOs and error budgets

| Service                | SLI                   | Target  | Error budget       | Measurement                       |
| ---------------------- | --------------------- | ------- | ------------------ | --------------------------------- |
| Pipeline execution     | P95 completion time   | ≤ 120s  | 5% of monthly runs | Prefect metrics exported via OTLP |
| Quality accuracy       | Valid records / total | ≥ 95%   | 5%                 | Quality report metrics            |
| Dashboard availability | Uptime                | ≥ 99.5% | 0.5%               | Uptime robot / synthetic checks   |

## Observability roadmap

- Expand OpenTelemetry collector config to export metrics/traces/logs to Grafana Tempo/Loki.
- Annotate Prefect tasks with `hotpass.dataset` attribute for filtering.
- Instrument CLI with structured logging and PII redaction (complete; configurable masks redact emails, phone numbers, and other sensitive fields in structured logs).【F:apps/data-platform/hotpass/cli.py†L33-L356】
- Streamlit dashboard enforces password-gated access and filesystem allowlists before executing pipelines, containing blast radius for misconfigurations.【F:apps/data-platform/hotpass/dashboard.py†L44-L220】【F:tests/test_dashboard.py†L120-L216】
- Publish SLO dashboard referencing metrics above.

## Chaos and resilience

- Quarterly chaos day simulating:
  - Prefect API outage (expect graceful retry/backoff).
  - Downstream enrichment API latency spikes.
  - Streamlit hosting failure (ensure dashboard degrade gracefully).
- Capture hypotheses, blast radius, and mitigations in chaos runbook (to be authored).

## Service contracts

- Maintain CLI contract in [`contracts/hotpass-cli-contract.yaml`](../../contracts/hotpass-cli-contract.yaml).
- Version Prefect deployment YAML and share across teams via Backstage template.
- Update ADRs to reference control contracts and associated fitness functions.

## Future work

- Integrate anomaly detection (Prometheus + Alertmanager) to enforce error budgets.
- Automate rollback toggles (feature flags) for risky pipeline steps.
- Expand provenance integration into dashboard to surface run digests.
