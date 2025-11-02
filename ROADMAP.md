# Hotpass delivery roadmap

This file complements [`docs/roadmap.md`](docs/roadmap.md) with a quick view of
open checklist items and the pull requests planned to address them. Use it as the
entry point during triage so upcoming work stays aligned with the programme
phases and governance gates.

## Phase 1 — Foundation alignment

- [x] **T1.1 Programme guardrails** — Roadmap, governance charter, and evidence
      ledger refreshed; retro plan captured in
      [`docs/operations/foundation-retro.md`](docs/operations/foundation-retro.md) to
      guide the upcoming Programme review.
- [x] **T1.2 Operational readiness** — Prefect bootstrap, telemetry wiring, and
      ARC lifecycle verifier (with snapshot mode) prepared Platform for the staged
      runner rollout documented in the ARC how-to guide.

## Phase 2 — Contracts, validation, and data hygiene

- [x] **T2.1 Canonical dataset contracts** — Pandera table models, JSON Schema
      exports, and the regenerated documentation set are live. Round-trip tests
      exercise the contract registry so new datasets remain governed.
  - Delivered via `contracts/new-dataset-schemas`; follow-up PRs will extend the
    contract catalogue as new workbooks arrive.
- [x] **T2.2 Great Expectations gates** — Keep checkpoints and Data Docs in
      sync, ensuring the docs landing page points to the validation artefacts.
  - Delivered via `docs/data-governance-nav`: the new
    [`docs/governance/data-governance-navigation.md`](docs/governance/data-governance-navigation.md)
    page surfaces Data Docs, schema exports, lineage, and evidence packs from the
    docs landing page.
- [x] **T2.3 Property-based tests** — Expand Hypothesis coverage for ingestion
      and export idempotency scenarios.
  - Delivered via `tests/property/test_ingestion_properties.py`, reinforcing
    ingestion deduplication, Unicode handling, and deterministic slugs/provinces.

## Phase 3 — Pipelines (ingest, backfill, refine, publish)

- [x] **T3.1 Prefect 3 deployments** — Commit deployment manifests and ensure
      `prefect deploy` produces idempotent schedules.
  - Verified in-repo via CLI integration tests (`tests/cli/test_deploy_command.py`) and Prefect flow overrides (`tests/test_orchestration.py`).
- [ ] **T3.2 OpenLineage + Marquez** — Harden lineage emission and document the
      local Marquez stack.
  - Completed PR: `observability/marquez-bootstrap` (2025-10-28) introduced the
    compose stack and quickstart guide; ongoing maintenance tasks live in
    `docs/roadmap.md`.
- [x] **T3.3 Persist refined outputs + data versioning** — Parquet outputs and
      DVC snapshots are live with CLI support.

## Phase 4 — ML lifecycle (conditional)

- [x] **T4.1 MLflow tracking + registry** — Tracking, registry, and promotion
      workflows are merged with comprehensive coverage.

## Phase 5 — CI/CD & ephemeral runners

- [x] **T5.1 Quality gates** — Migrate the GitHub Actions QA workflow to uv and
      enforce coverage thresholds.
  - Delivered via `.github/workflows/quality-gates.yml` orchestrating QG-1→QG-5 and coverage instrumentation with the `ops/quality/run_qg*.py` helpers.【F:.github/workflows/quality-gates.yml†L1-L110】【F:ops/quality/run_all_gates.py†L1-L200】
- [x] **T5.2 Security scanning** — Codify CodeQL, detect-secrets diff mode, and
      Bandit SARIF uploads.
  - `.github/workflows/codeql.yml` and `.github/workflows/secret-scanning.yml` now run on every push/PR, while the `Process and Refine Data` workflow executes detect-secrets and Bandit checks in-line.【F:.github/workflows/codeql.yml†L1-L40】【F:.github/workflows/secret-scanning.yml†L1-L40】【F:.github/workflows/process-data.yml†L25-L140】
- [x] **T5.3 Docker buildx cache** — Enable cache reuse across PR builds.
  - Implemented via `.github/workflows/docker-cache.yml` hydrating BuildKit caches through `docker/build-push-action` with GitHub Actions cache scopes.【F:.github/workflows/docker-cache.yml†L1-L60】
- [x] **T5.4 Provenance** — Generate SBOMs and SLSA attestations.
  - The `supply-chain` job in `.github/workflows/process-data.yml` invokes `ops/supply_chain/generate_sbom.py` and `generate_provenance.py`, publishing artefacts and checksums for audits.【F:.github/workflows/process-data.yml†L180-L260】【F:ops/supply_chain/generate_sbom.py†L1-L120】【F:ops/supply_chain/generate_provenance.py†L1-L160】
- [x] **T5.5 Ephemeral runners** — Roll out ARC manifests and AWS OIDC wiring (programme expectations confirmed in 2025-11-02 release).
  - Completed via updated ARC smoke workflow and lifecycle verifier that now confirm AWS role assumptions alongside runner drain; staging rollout follows the refreshed runbook and workflow configuration.【F:ops/arc/verify_runner_lifecycle.py†L1-L210】【F:.github/workflows/arc-ephemeral-runner.yml†L1-L60】【F:docs/how-to-guides/manage-arc-runners.md†L1-L110】
  - Release evidence: `dist/staging/backfill/20251101T171853Z/` rehearsal logs and `dist/staging/marquez/20251101T171901Z/cli.log` captured in the 2025-11-02 changelog entry.【F:docs/CHANGELOG.md†L1-L23】
- [x] **T5.6 Telemetry instrumentation** — Propagate OpenTelemetry exporters
      through CLI and Prefect.
  - Completed via `telemetry/bootstrap` integrating `TelemetryBootstrapOptions` into CLI entry points and Prefect flows; follow-up docs remain tracked separately.【F:apps/data-platform/hotpass/cli/commands/run.py†L156-L531】【F:apps/data-platform/hotpass/telemetry/bootstrap.py†L1-L200】

## Phase 6 — Documentation & UX

- [ ] **T6.1 Diátaxis docs structure** — Maintain the Tutorials/How-to/Reference/
      Explanations balance and surface governance artefacts from the landing page.
  - In flight: `docs/data-governance-nav` (this PR) and follow-on PRs for the
    `hotpass doctor` quickstart once the CLI work lands.
- [ ] **T6.2 CLI UX (`hotpass doctor` / `hotpass init`)** — Introduce guided
      onboarding and diagnostics commands.
  - Upcoming PR: `cli/doctor-and-init` (design pending from product UX).

## Quick links

- Full programme context: [`docs/roadmap.md`](docs/roadmap.md)
- Governance assets: [`docs/reference/data-docs.md`](docs/reference/data-docs.md),
  [`docs/reference/schema-exports.md`](docs/reference/schema-exports.md),
  [`docs/observability/marquez.md`](docs/observability/marquez.md)
- Contribution workflow: [`README.md`](README.md),
  [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md)
