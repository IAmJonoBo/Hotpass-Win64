# Next Steps

## Tasks

- [ ] **Programme** — Confirm Phase 5 T5.5 completion so roadmap status reflects programme expectations.
- [ ] **QA** — Execute full E2E runs with canonical configuration toggles ; reuse Prefect deployment `hotpass-e2e-staging`).
- [ ] **Platform** — Validate Prefect backfill deployment guardrails in staging.
- [ ] **Engineering** — Benchmark `HotpassConfig.merge` on large payloads.
- [ ] **Engineering & Platform** — Design and implement new CLI surface commands (`hotpass net`, `hotpass aws`, `hotpass ctx`, `hotpass env`) that wrap tunnel setup, AWS identity checks, Prefect/kube context configuration, and environment drafting.
- [ ] **Docs & QA** — Document and test the new CLI automation surface once available (README quickstart, `docs/reference/cli.md`, `AGENTS.md`, and ARC how-to guide).
- [ ] **QA & Engineering** — Extend orchestrate/resolve CLI coverage for advanced profiles (reuse CLI stress fixtures and add resolve scenarios in `tests/cli/test_resolve.py`).
  - **Progress:** Added `tests/cli/test_resolve_profile.py` coverage for profile-driven Splink defaults, explicit disable flags, and Label Studio wiring; orchestrator stress fixtures still pending once staging data is available.
- [ ] **Platform & QA** — Capture staging evidence for Prefect backfill guardrails and ARC runner sign-off once access returns _(post-1.0)_.
- [ ] **Docs & UX (Phase 6)** — Finish Diátaxis navigation uplift in PR `docs/data-governance-nav` follow-on, ensuring governance artefacts surfaced (owner: Docs & UX).

## Steps

- [ ] Reconfirm post-PR hygiene: ensure `Next_Steps.md` updated alongside each PR hand-off as per contributing guide (rolling reminder for all owners).【2ed7b7†L71-L71】
- [ ] Schedule Marquez lineage smoke against `observability/marquez-bootstrap` follow-up once optional dependencies land (target 2025-11-29) using the quickstart workflow.【d9a97b†L24-L29】【b3de0d†L1-L42】
- [ ] Document expected staging artefacts for Prefect backfill guardrails and ARC runner sign-off runs so evidence drops into `dist/staging/backfill/` and `dist/staging/arc/` when access resumes (owner: Platform & QA, _(post-1.0)_).
- [ ] Continue migrating orchestration pytest assertions to `expect()` helper outside touched scenarios (owner: QA & Engineering).
  - **Progress:** test_error_handling.py completed (46 assertions migrated); compliance verification + enrichment suites migrated to `expect()`; agentic orchestration coverage converted 2025-10-31. Remaining bare-assert files: 31.
- [ ] Audit remaining telemetry/CLI modules for strict mypy readiness and convert outstanding bare assertions (owner: Engineering & QA).
  - **Progress:** `uv run mypy apps/data-platform tests ops` on 2025-10-31 reports 0 errors (down from 197 baseline). Remaining follow-up: monitor new suites for decorator regressions.
- [ ] Review and adopt the repository restructure guidance in `docs/architecture/repo-restructure-plan.md` as the canonical layout reference (owners: Engineering & Docs).

## Deliverables


## Quality Gates

  - [ ] Infrastructure — `uv run python ops/arc/verify_runner_lifecycle.py --owner ...` to capture lifecycle report for ARC runners (blocked awaiting staging access).【73fd99†L41-L55】
  - [x] Tests — Baseline `uv run pytest --cov=hotpass --cov=apps --cov-report=term-missing` failures resolved (CLI parser conflict, handler signatures, and lineage stub facets). Targeted suites `tests/cli/test_new_commands.py tests/cli/test_backfill.py tests/cli/test_run_lineage_integration.py` now green; schedule full-suite run when time budget allows; owner: Engineering.
  - [ ] Lint — `uv run ruff check` fails under ruff 0.12.11 because import ordering rules (`I001`) and upgrade helpers (`UP038`) now flag legacy modules; owner: Engineering.
  - [ ] Types — `uv run mypy apps/data-platform tests ops` reports missing stub packages (`yaml`, `requests`, `hypothesis`) and signature issues in automation/linkage modules; owner: Engineering.
  - [ ] Supply chain — `uv run python ops/supply_chain/generate_sbom.py --output dist/sbom/hotpass-sbom.json` fails (missing `cyclonedx_py` module inside repo venv); owner: Platform.
  - [ ] Security — `uv run detect-secrets scan --all-files` interrupted locally (KeyboardInterrupt) after multi-process heuristics stalled on large files; confirm baseline runtime or scope reduction with Security owners.

## Links

- `schemas/` — current frictionless contracts to be regenerated.
- `apps/data-platform/hotpass/orchestration.py` — pipeline payload helpers requiring baseline fix.
- `docs/architecture/repo-restructure-plan.md` — canonical mapping for the apps/ops separation and follow-up actions.
- `docs/architecture/cli-expansion-plan.md` — design blueprint for the upcoming CLI automation verbs.
- `docs/index.md` — landing page now surfacing governance artefacts; monitor follow-up requests.
- `docs/reference/data-docs.md` & `docs/reference/schema-exports.md` — new reference pages for Data Docs + JSON Schema consumers.
- `docs/governance/data-governance-navigation.md` — consolidated navigation across governance artefacts.
- `docs/operations/foundation-retro.md` — Phase 1 retro agenda and scope reconciliation.
- `ops/arc/examples/hotpass_arc_idle.json` — reusable snapshot for lifecycle rehearsal.
- `docs/adr/index.md` — documentation strategy alignment summary.
- `prefect/` — manifest library consumed by the revamped deployment loader.
- `docs/adr/0007-cli-onboarding.md` — decision record for CLI doctor/init onboarding workflow.
- `docs/reference/cli.md` / `docs/tutorials/quickstart.md` — updated references introducing doctor/init usage.

## Risks/Notes

- Keep this file actionable: move completed checklist items to `Next_Steps_Log.md` whenever tasks close so future updates remain focused on open work.
- Prefect pipeline task payload fix merged; continue monitoring downstream Prefect deployments for regressions when toggling `backfill`/`incremental` flags.
- Ingestion now normalises column headers and restores missing optional fields before slug/province transforms; monitor downstream consumers for assumptions about duplicate column names.
- Ruff baseline drift: format gate was green after the prior repo restore, but ruff 0.12.11 now reports import ordering and upgrade helper findings—coordinate with maintainers before applying repo-wide fixes.
- Bandit reports tolerated `try/except/pass`; confirm acceptable risk or remediate while touching orchestration.
- Watch list: monitor uv core build availability and Semgrep CA bundle rollout for future updates (owners retained from prior plan).
- Marquez compose stack introduced for lineage verification; automated tests now guard compose configuration and lineage environment variables while we schedule live smoke tests for CLI + Prefect flows.
- ARC lifecycle verification rehearsed via snapshot; continue tracking live staging access to close the infrastructure gate.
