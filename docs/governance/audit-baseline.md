---
title: Governance audit baseline
summary: Catalog of Hotpass 2.0 configuration defaults, quality expectations, feature toggles, and compliance artefacts.
last_updated: 2025-11-02
---

Hotpass 2.0 treats the orchestrator's default bundle as the authoritative execution contract. Use this
checklist when verifying a deployment, refreshing evidence, or onboarding a new data provider.

## Baseline execution contract

- **Configuration entrypoint** — `PipelineConfig` in [`apps/data-platform/hotpass/pipeline/base.py`](../../apps/data-platform/hotpass/pipeline/base.py)
  defines the canonical orchestration order (acquisition → ingest → enrichment → validation → publish).
- **Default feature bundle** — [`default_feature_bundle`](../../apps/data-platform/hotpass/pipeline/base.py) enables entity
  resolution, geospatial, enrichment, and compliance features; opt-outs must be tracked in `Next_Steps.md`.
- **Acquisition plan** — when `[pipeline.acquisition]` is omitted, the orchestrator still executes baseline
  spreadsheet loaders; enabling the plan runs `AcquisitionManager` ahead of ingestion and feeds telemetry spans.
- **Intent plan** — `[pipeline.intent]` toggles collectors and digest exports; the orchestrator records intent
  summaries even when no targets match to keep downstream automation deterministic.

## Feature toggles and defaults

| Toggle                         | Location                                                                                      | Default                                                 | Notes                                                               |
| ------------------------------ | --------------------------------------------------------------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------- |
| `pipeline.acquisition.enabled` | `hotpass.toml` / `PipelineConfig`                                                             | `false`                                                 | Enable to run agent-based acquisition before spreadsheet ingestion. |
| `pipeline.intent.enabled`      | `hotpass.toml` / `PipelineConfig`                                                             | `false`                                                 | Controls daily intent digests and SSOT enrichment columns.          |
| `features` bundle              | [`default_feature_bundle`](../../apps/data-platform/hotpass/pipeline/base.py)                 | `entity_resolution, geospatial, enrichment, compliance` | Adjust with care; document deviations in `Next_Steps.md`.           |
| CLI progress JSON logging      | `--json-logs` flag (`apps/data-platform/hotpass/cli/commands/run.py`)                         | `false`                                                 | Emits structured `pipeline.*` and `intent.digest` events.           |
| Observability exporters        | [`observability.initialize_observability`](../../apps/data-platform/hotpass/observability.py) | `console`                                               | Use environment variables or config to swap OTLP/OTLPg exporters.   |

## Expectation suites

| Dataset                | Suite path                                        | Purpose                                                    |
| ---------------------- | ------------------------------------------------- | ---------------------------------------------------------- |
| Contact capture        | `data_expectations/contact/capture.json`          | Structural validation for ingestion CSV/Excel inputs.      |
| Contact organisation   | `data_expectations/contact/company_contacts.json` | Ensures enriched contacts meet minimum field completeness. |
| Reachout organisation  | `data_expectations/reachout/organisation.json`    | Governs outbound-ready datasets published to partners.     |
| SACAA cleaned registry | `data_expectations/sacaa/cleaned.json`            | Validates registry cleanses before compliance export.      |

Update suites when schemas change and re-run `uv run pytest --cov=src --cov=tests --cov-report=term-missing`
to capture expectation coverage in the quality report.

## Compliance artefacts and provenance

- **Acquisition provider policy** — [`policy/acquisition/providers.json`](../../policy/acquisition/providers.json)
  enumerates allowlisted providers, collection basis, and PII handling notes. Guard script consumers should
  call `ProviderPolicy.ensure_allowed` before instantiating a provider.
- **Terms of service snapshots** — store hashes via `TermsOfServicePolicy` (see `ops/acquisition/guardrails.py`)
  and append fetch events to the provenance ledger at `dist/provenance/*.jsonl`.
- **Evidence catalog** — keep [`docs/compliance/evidence-catalog.md`](../compliance/evidence-catalog.md)
  updated after every quarterly verification and when new data sources are introduced.
- **Telemetry audit trail** — the acquisition manager now emits `acquisition.plan`, `acquisition.agent`, and
  `acquisition.provider` spans, plus acquisition metrics (`hotpass.acquisition.*`). These feed the OpenTelemetry
  registry and allow SOC 2 collection of data lineage events.

## Verification steps

1. Run `uv run hotpass refine --input-dir data --output-path dist/refined.xlsx --profile generic --archive` with the default bundle
   and confirm acquisition spans/metrics appear in the telemetry exporter (console in sandbox environments).
2. Regenerate provenance ledgers via `ops/acquisition/collect_dataset.py` when onboarding a new provider and
   store the resulting JSONL artefact under `dist/provenance/` for compliance review.
3. Audit `Next_Steps.md` to ensure any temporary deviations from the defaults above include an owner, due date,
   and rollback trigger.
