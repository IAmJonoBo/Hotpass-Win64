# Next Steps

## Tasks
- [ ] Execute full end-to-end runs with canonical configuration toggles using Prefect deployment `hotpass-e2e-staging`. (owner: QA, due: backlog)
- [ ] Validate Prefect backfill deployment guardrails in staging. (owner: Platform, due: post-1.0)
- [ ] Design and implement new CLI surface commands (`hotpass net`, `hotpass aws`, `hotpass ctx`, `hotpass env`). (owner: Engineering & Platform, due: backlog)
- [ ] Document and test the new CLI automation surface once available (README quickstart, `docs/reference/cli.md`, `AGENTS.md`, ARC guide). (owner: Docs & QA, due: backlog)
- [ ] Extend orchestrate/resolve CLI coverage for advanced profiles; reuse CLI stress fixtures and add resolve scenarios in `tests/cli/test_resolve.py`. (owner: QA & Engineering, due: backlog)
  - Progress: Added `tests/cli/test_resolve_profile.py` coverage for profile-driven Splink defaults, explicit disable flags, and Label Studio wiring; orchestrator stress fixtures still pending once staging data is available.
- [ ] Capture staging evidence for Prefect backfill guardrails and ARC runner sign-off once access returns. (owner: Platform & QA, due: post-1.0)
- [x] Finish Diátaxis navigation uplift in PR `docs/data-governance-nav` follow-on, ensuring governance artefacts are surfaced. (owner: Docs & UX, due: Phase 6) — Added backfill/Data Docs how-to guides and refreshed the landing page navigation.
- [ ] Restore `make qa` baseline; address `ruff format --check` reporting 137 files to avoid mass reformatting before rerunning the gate. Command: `make qa`. (owner: Engineering, due: 2025-11-05)
- [ ] Investigate Prefect deployment registration regression surfaced by `uv run pytest --cov=hotpass --cov=apps --cov-report=term-missing` (`tests/test_deployment_specs.py::test_deploy_pipeline_filters_and_registers`). (owner: Engineering, due: 2025-11-04)
- [ ] Resolve mypy baseline regressions uncovered by `uv run mypy apps/data-platform tests ops` (44 errors across requests/yaml stubs, scrapy dependencies, and CLI typing). (owner: Engineering & QA, due: backlog)
- [ ] Reduce `uv run ruff check` baseline failures (52 violations as of 2025-11-04) without mass reformatting. (owner: Engineering, due: backlog)

## Steps
- [ ] Restore packaging build path by adding the `build` module or alternative to the dev extras before rerunning `uv run python -m build`.
- [ ] Reproduce `tests/test_deployment_specs.py::test_deploy_pipeline_filters_and_registers` with Prefect runner mocks to isolate extra registrations and draft remediation.
- [ ] Outline a targeted formatting plan (e.g., staged module batches) before running `ruff format` so the `make qa` gate can complete without destabilising history.
- [ ] Catalogue missing stub packages and annotate ownership for the 90 mypy diagnostics before planning fixes.
- [ ] Document a staged fix strategy for the 52 `ruff check` violations and schedule remediation runs.
- [ ] Re-run `uv run pytest tests` to capture a clean baseline (2025-11-02 manual interruption stopped the session at ~43 tests; reschedule full suite once resources allow).
- [x] Break the `pip-audit`/`cyclonedx-python-lib` resolver conflict so `uv run hotpass explain-provenance` succeeds during pytest runs; track candidate pin overrides in `pyproject.toml` extras. — Updated the `ci` extra to require `cyclonedx-python-lib[validation]>=9,<10`, regenerated `uv.lock`, and re-synced the environment (`pip check` now clean).

## Deliverables
- Baseline QA run notes (2025-11-01) covering `make qa`, pytest, mypy, and SBOM status.
- Updated dependency matrix (`pyproject.toml`) including `cyclonedx-bom` for supply chain tooling.
- Generated CycloneDX SBOM at `dist/sbom/hotpass-sbom.json` (2025-11-01) for baseline evidence.
- Benchmark evidence stored at `dist/benchmarks/hotpass_config_merge.json` (2025-11-01) for HotpassConfig merge profiling.
- Simulated staging artefacts at `dist/staging/backfill/20251101T171853Z/` and `dist/staging/marquez/20251101T171901Z/` pending live access.

## Quality Gates
- tests: **partial** — Targeted suites (`tests/cli/test_explain_provenance.py`, `tests/cli/test_doctor_command.py`, `tests/cli/test_init_command.py`, `tests/pipeline/test_pipeline_smoke.py`) pass after resolving the cyclonedx/pip-audit pins; schedule a full `pytest tests` run to capture updated coverage. (owner: Engineering)
- linters/formatters: **blocked** — `scripts/testing/trunk_check.sh` still flags 200+ pre-existing diffs (e.g. `tests/conftest.py`, `tests/test_pipeline_enhancements_exports.py`) when comparing against `origin/main`; no changes were applied to avoid clobbering user work. (owner: Engineering)
- type-checks: **blocked** — `mypy apps/data-platform tests ops` reports 30 errors (missing stubs for requests/yaml/hypothesis, scrapy imports). (owner: Engineering & QA)
- security scan: **warning** — `bandit -r apps/data-platform ops` flagged existing subprocess usage (B404/B603) in CLI helpers; detect-secrets produced no findings. (owner: Engineering & Security)
- coverage: **partial** — Latest full-suite run reported 72% line coverage; current attempt blocked by resolver failure preventing new coverage delta capture. (owner: QA)
- build: **pass** — `python -m build` now succeeds after installing `build` into the local venv (artifacts generated under `dist/`). (owner: Engineering)
- docs updated: **pass** — Phase 6 navigation uplift landed (`run-a-backfill`, `read-data-docs`) and ROADMAP/Diátaxis checkpoints refreshed. (owner: Docs)
- supply chain: **pass** — `uv run python ops/supply_chain/generate_sbom.py --output dist/sbom/hotpass-sbom.json` completed after installing `cyclonedx-bom`; artifact stored under `dist/sbom/hotpass-sbom.json`. (owner: Platform)

## Links
- `tests/test_deployment_specs.py` — Prefect deployment registration expectations.
- `ops/supply_chain/generate_sbom.py` — SBOM generation helper.
- `Makefile` — `make qa` orchestration including lint/type/security gates.
- `docs/architecture/repo-restructure-plan.md` — canonical layout reference for ongoing engineering tasks.

## Risks/Notes
- Prefect deployment registration guardrails are failing locally; align with Platform owners before rerunning staging backfills.
- Mass reformatting triggered by `ruff format --check` would touch 137 files; coordinate staged formatting or config adjustments to prevent destabilising diffs.
- Adding `cyclonedx-bom` to core dependencies increases the default environment footprint; monitor installation times and adjust extras if necessary.
- Missing stub packages (`types-requests`, `types-PyYAML`, `types-urllib3`, `hypothesis` stubs) continue to block strict mypy adoption; catalogue owners for remediation.
- Security gates now run cleanly via `uv run` commands; automation remains gated on resolving the trunk formatting backlog to re-enable `make qa`/`make qa-full`.
