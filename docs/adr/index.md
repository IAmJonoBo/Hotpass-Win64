---
title: Architecture decisions index
summary: Status snapshot for the MADR catalogue and how the documentation strategy maps to each decision.
last_updated: 2025-11-02
---

# Architecture decisions index

The Hotpass ADRs capture architectural and governance decisions using the MADR
format. This index highlights the current state of each decision and how the
latest documentation work (including the refreshed Data Docs and lineage
navigation) keeps the guidance actionable.

## Documentation strategy alignment

- **Diátaxis enforcement:** The landing page now exposes governance artefacts
  (Data Docs, schema exports, Marquez quickstart) up front, satisfying the
  visibility goals from [ADR-0002](0002-governance-automation.md) and the
  documentation commitments in [ADR-0004](0004-checkpoint-validation-strategy.md).
- **Telemetry bootstrap coverage:** Updates remain consistent with
  [ADR-0006](0006-telemetry-bootstrap.md) by linking observability material from
  the same hub.
- **Future work:** Planned PRs for `hotpass doctor` / `init` will close the loop
  on the UX guarantees described in [docs/roadmap.md](../roadmap.md) and surfaced
  in the repository-level `ROADMAP.md`.
- **CLI onboarding:** `hotpass init` and `hotpass doctor` now land as part of the
  quickstart workflow, addressing the UX commitments captured in ROADMAP.md.

## Decision catalogue

| ADR                                            | Title                          | Status   | Notes                                                                                            |
| ---------------------------------------------- | ------------------------------ | -------- | ------------------------------------------------------------------------------------------------ |
| [0001](0001-qa-tooling.md)                     | QA tooling guardrails          | Accepted | Defines the consolidated QA suite referenced in the README preflight checks.                     |
| [0002](0002-governance-automation.md)          | Governance automation          | Accepted | Establishes Data Docs + lineage requirements; the updated navigation surfaces both deliverables. |
| [0003](0003-data-contracts.md)                 | Data contracts                 | Accepted | Contracts and schema exports remain in sync via the generator noted in the schema reference.     |
| [0004](0004-checkpoint-validation-strategy.md) | Checkpoint validation strategy | Accepted | Documentation now links directly to Data Docs and refresh tooling.                               |
| [0005](0005-prefect-deployment-manifests.md)   | Prefect deployment manifests   | Proposed | Pending PR `prefect/deployment-manifests`; status tracked in ROADMAP.md.                         |
| [0006](0006-telemetry-bootstrap.md)            | Telemetry bootstrap            | Accepted | Observability docs and quickstarts align with the bootstrap decision.                            |
| [0006B](0006-mlflow-lifecycle-strategy.md)     | MLflow lifecycle strategy      | Accepted | Continues to guide MLflow references in tutorials/how-tos.                                       |
| [0007](0007-cli-onboarding.md)                 | CLI onboarding commands        | Accepted | Establishes `hotpass init` / `doctor` workflow and docs coverage.                                |

## How to contribute

- When drafting new ADRs, add them to this index with a short status summary.
- Update the "Documentation strategy alignment" section whenever the landing
  page or governance artefacts shift so consumers know where to look first.
- Reference relevant ADRs from pull requests to maintain traceability between
  code, docs, and decisions.
