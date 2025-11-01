---
title: Hotpass roadmap
summary: Status of the Hotpass modernisation programme, quality gates, and follow-up work.
owner: n00tropic
last_updated: 2025-10-31
---

This roadmap is the single source of truth for the Hotpass programme. It captures the active plan, guardrails, acceptance criteria, and the mapping of work to the repository layout so that changes are incremental, reversible, and observable.

## Executive summary

Focus areas for the upcoming iterations:

- **Contracts & validation**: canonical dataset models (Pydantic/Pandera), JSON Schemas in `schemas/`, and Great Expectations (GX) gates that block publishes on failure.
- **Pipelines**: Prefect 3 deployments with idempotent/resumable runs and explicit `backfill` / `incremental` parameters; OpenLineage emission with a local Marquez viewer; refined outputs written as Parquet with data versioning.
- **CI/CD & runners**: uv-based quality gates (ruff, mypy, pytest+coverage, SARIF), CodeQL/detect-secrets/bandit, Docker buildx with cache, SBOM + SLSA attestations, and ephemeral self-hosted runners via Actions Runner Controller (ARC) with OIDC→AWS.
- **Docs & UX**: Diátaxis structure enforced; add `hotpass doctor` and `hotpass init` to streamline onboarding and troubleshooting.
- **Governance artefacts**: Landing page now links to Data Docs, Marquez lineage, and schema export references so reviewers can jump straight to validation context while triaging pull requests.
- **Performance baselines**: `ops/benchmarks/hotpass_config_merge.py` now measures canonical config merges; baseline results are stored under `dist/benchmarks/` and feed into preflight reviews.

### Current blockers

- **Staging rehearsals** (Prefect backfill guardrails, full E2E pipeline replay, ARC lifecycle rerun) remain on hold pending restored access to `hotpass-staging`. Tracking instructions live in `docs/operations/staging-rehearsal-plan.md`.
- **Docs Diátaxis uplift** is still underway; tutorials/how-tos are being updated incrementally alongside feature work.

## Iteration plan (date-free)

### Iteration A – safety rails first

1. Phase 2 tasks (contracts, GX, property tests).
2. Phase 5 tasks T5.1–T5.4 (quality CI, security, build, provenance).
3. Phase 6 task T6.1 (docs skeleton and links).

### Iteration B – orchestration, observability, and data versioning

1. Phase 3 tasks (Prefect deployments, OpenLineage/Marquez, Parquet + DVC).
2. Phase 5 tasks T5.5–T5.6 (ephemeral runners + OpenTelemetry instrumentation).
3. Phase 6 task T6.2 (CLI UX: `doctor` and `init`).
4. **Phase 4 completed**: MLflow tracking, model registry, and promotion workflow fully implemented with comprehensive testing.

---

## Phase 1 — Foundation alignment

- [x] **T1.1 Programme guardrails**
  - [x] Establish roadmap, governance charter, and evidence ledger updates to
        anchor future phases.
  - [x] Publish the Phase 1 retrospective plan in
        [`docs/operations/foundation-retro.md`](operations/foundation-retro.md).
  - **Acceptance:** retro agenda agreed, navigation to governance artefacts
    captured for Programme stakeholders.

- [x] **T1.2 Operational readiness**
  - [x] Land Prefect bootstrap, telemetry instrumentation, and ARC lifecycle
        verification helpers with snapshot support so Platform can rehearse runner
        rollouts ahead of Phase 5.
  - **Acceptance:** lifecycle verifier executable via snapshot file;
    documentation added to the ARC runner how-to.

## Phase 2 — Contracts, validation, and data hygiene

- [x] **T2.1 Canonical dataset contracts**
  - [x] Add row-level models with **Pydantic** under `contracts/<dataset>.py`. Optionally add table-level **Pandera** `DataFrameModel`s for whole-table checks.
  - [x] Export **JSON Schema** files to `schemas/<dataset>.schema.json` for every canonical dataset.
  - [x] Autogenerate `docs/reference/schemas.md` with a field table per dataset.
  - **Acceptance:** sample records validate; schemas exist under `schemas/`; the reference page builds and links correctly.

- [x] **T2.2 Great Expectations gates**
  - [x] Create **Expectation Suites** per dataset and store under `data_expectations/`.
  - [x] Add **Checkpoints** that run before publish steps; failing validation must block publish.
  - [x] Render **Data Docs** to `dist/data-docs/` and link from `docs/index`.
  - [x] Publish the governance navigation guide at
        [`docs/governance/data-governance-navigation.md`](governance/data-governance-navigation.md)
        so reviewers can trace artefacts quickly.
  - **Acceptance:** CI job runs checkpoints; failures fail the job; `dist/data-docs/`
    artefacts are published and linked from the navigation guide.

- [x] **T2.3 Property-based tests (Hypothesis)**
  - [x] Create `tests/property/` for edge cases: encodings, date formats, missing/extra columns, duplicate headers.
  - [x] Add idempotency tests (same inputs → same outputs) for core transforms.
  - Implemented via `tests/property/test_ingestion_properties.py`, which hardens ingestion deduplication/normalisation and exercises slug/province transformations across messy Unicode payloads.
  - **Acceptance:** CI passes property-based tests; any discovered regressions include minimal repro data in `tests/data/`.

## Phase 3 — Pipelines (ingest, backfill, refine, publish)

- [x] **T3.1 Prefect 3 deployments**
  - [x] Add `prefect.yaml` defining per-flow deployments, schedules, and tags.
  - [x] Define parameters `backfill: bool`, `incremental: bool`, `since: datetime|None` and ensure flows are idempotent and resumable.
    - Verified via automated coverage in `tests/cli/test_deploy_command.py` and `tests/test_orchestration.py`.
  - **Acceptance:** `prefect deploy` produces deployments; the UI shows schedules; re-running is idempotent.

- [ ] **T3.2 OpenLineage + Marquez**
  - [ ] Add `infra/marquez/docker-compose.yml` to run Marquez locally; document `make marquez-up`.
  - [ ] Emit **OpenLineage** events from flows; record datasets/jobs/runs; link the UI from docs.
  - **Acceptance:** lineage appears in Marquez for a demo flow; screenshot in PR.

- [x] **T3.3 Persist refined outputs + data versioning**
  - [x] Persist refined outputs as **Parquet** under `dist/refined/` with explicit schema and compression.
  - [x] Adopt **DVC** to version refined data and backfill snapshots.
  - [x] Add `hotpass version` CLI command for version management.
  - [x] Create `docs/how-to-guides/manage-data-versions.md` documentation.
  - [x] Update roadmap to track DVC integration progress.
  - **Acceptance:** `hotpass version --status` works; version bumping functional; docs guide users through setup and recovery workflows.

## Phase 4 — ML lifecycle (conditional)

- [x] **T4.1 MLflow tracking + registry**
  - [x] Run MLflow Tracking with a DB backend (SQLite for dev, configurable for production); log code, params, metrics, and artefacts.
  - [x] Create a Model Registry with stage gates ("None" → "Staging" → "Production" → "Archived"); document promotion policy.
  - [x] Integrate tracking into `train_lead_scoring_model` with `enable_mlflow` flag.
  - [x] Add comprehensive tests (12 tests, 86% coverage) with in-memory SQLite.
  - **Acceptance:** Training runs logged to MLflow; models registered and promotable through stages; ADR 0006 committed; how-to guide available at `docs/how-to-guides/model-lifecycle-mlflow.md`.

## Phase 5 — CI/CD & ephemeral runners

- [x] **T5.1 `ci.yml` – quality gates**
  - [x] Use **uv** with caching; run **ruff**, **mypy**, **pytest** with coverage gates; upload SARIF where applicable.【F:.github/workflows/quality-gates.yml†L1-L110】
  - **Acceptance:** CI green; coverage ≥ baseline via the quality-gates workflow aggregating QG-1→QG-5 outputs.【F:ops/quality/run_all_gates.py†L1-L200】

- [x] **T5.2 `security.yml` – CodeQL, secrets, Bandit**
  - [x] Enable **CodeQL**; run **detect-secrets** in diff mode; run **bandit**.【F:.github/workflows/codeql.yml†L1-L40】【F:.github/workflows/secret-scanning.yml†L1-L40】【F:.github/workflows/process-data.yml†L25-L140】
  - **Acceptance:** CodeQL and Gitleaks SARIF upload to code scanning, while detect-secrets/Bandit execute on every push through the process-data pipeline.【F:.github/workflows/process-data.yml†L25-L140】

- [x] **T5.3 `build.yml` – Docker buildx + cache**
  - [x] Use `docker/build-push-action` with `cache-from/to: gha`; publish image artefacts.【F:.github/workflows/docker-cache.yml†L1-L60】
  - **Acceptance:** cache warming workflow in place; monitor cache hit ratio once adopted by primary CI builds.

- [x] **T5.4 `provenance.yml` – SBOM + SLSA**
  - [x] Generate **SBOM** via Syft; add **build-provenance** attestations.【F:.github/workflows/process-data.yml†L180-L260】【F:ops/supply_chain/generate_sbom.py†L1-L120】【F:ops/supply_chain/generate_provenance.py†L1-L160】
  - **Acceptance:** SBOM and provenance artefacts uploaded with checksums for audit consumption.【F:.github/workflows/process-data.yml†L200-L260】

- [ ] **T5.5 Ephemeral runners – ARC + OIDC→AWS**
  - [ ] Commit `infra/arc/` manifests for **Actions Runner Controller** runner scale sets; default to ephemeral pods.
  - [ ] Configure **OIDC** → AWS roles for temporary credentials (no long-lived secrets).
  - **Acceptance:** workflows execute on ephemeral runners; AWS access uses OIDC.

- [x] **T5.6 Telemetry – OpenTelemetry**
  - [x] Initialise OTel in the CLI and flows with OTLP exporters; set `OTEL_EXPORTER_OTLP_ENDPOINT` in CI/dev.【F:apps/data-platform/hotpass/cli/commands/run.py†L156-L531】
  - **Acceptance:** Telemetry bootstrap now emits traces/metrics via `apps/data-platform/hotpass/telemetry/bootstrap.py`; CLI carries resource/endpoint flags for demo validation.【F:apps/data-platform/hotpass/telemetry/bootstrap.py†L1-L200】

## Phase 6 — Documentation & UX

- [ ] **T6.1 Diátaxis docs structure**
  - [ ] Ensure `docs/` uses Tutorials, How‑tos, Reference, and Explanations; link Data Docs and the lineage UI from the docs home.
  - **Progress:** Tutorials/how-tos are being updated incrementally (for example, staging rehearsal guidance now lives in `docs/operations/staging-rehearsal-plan.md`); landing page uplift still pending.
  - **Acceptance:** landing page shows the four doc types; "How‑to: run a backfill" and "How‑to: read Data Docs" exist.

- [ ] **T6.2 CLI UX – `hotpass doctor` and `hotpass init`**
  - [ ] `doctor`: environment check (Python, uv, Prefect profile, OTel vars) and dataset sample validation.
  - [ ] `init`: generate config, sample data, and one‑shot bootstrap.
  - **Progress:** CLI verbs ship and are covered in `docs/reference/cli.md`; further UX polish (walkthroughs, troubleshooting) deferred until staging rehearsals conclude.
  - **Acceptance:** both commands succeed from a fresh checkout and provide actionable remediation hints on failure.

---

## Per‑PR acceptance criteria (applies to all changes)

- CI and security green; coverage not lower than baseline; docs build passes.
- **Data changes:** updated GX suites; validation passing; Data Docs refreshed.
- **Pipelines:** OpenLineage events visible in Marquez; flows have deployments and schedules.
- **CI:** SBOM artefacts and provenance attestations present; CodeQL uploaded.
- **Runners:** ARC manifests used; jobs execute on ephemeral runners with OIDC; Docker builds hit cache.

## Outputs

- ADRs under `docs/adr/NNN-*.md` (MADR‑style).
- Docs site navigation updated with direct entry points to Data Docs, schema exports, and the Marquez lineage UI.
- `ROADMAP.md` checklist tying issues/PRs to phases with labels `phase:2`…`phase:6`.
- Reference pages for Data Docs and schema exports live under `docs/reference/` to support governance handoffs.

## Guardrails

- **Avoid scope creep (YAGNI):** if an integration isn’t required within the next two iterations, stub the interface and stop.
- **Prefer small, fast iterations;** never land a PR that reduces observability or reversibility.
