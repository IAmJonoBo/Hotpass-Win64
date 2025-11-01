# Next Steps

## Tasks
- [ ] Confirm Phase 5 T5.5 completion so roadmap status reflects programme expectations. (owner: Programme, due: backlog)
- [ ] Execute full end-to-end runs with canonical configuration toggles using Prefect deployment `hotpass-e2e-staging`. (owner: QA, due: backlog)
- [ ] Validate Prefect backfill deployment guardrails in staging. (owner: Platform, due: post-1.0)
- [ ] Benchmark `HotpassConfig.merge` on large payloads. (owner: Engineering, due: backlog)
- [ ] Design and implement new CLI surface commands (`hotpass net`, `hotpass aws`, `hotpass ctx`, `hotpass env`). (owner: Engineering & Platform, due: backlog)
- [ ] Document and test the new CLI automation surface once available (README quickstart, `docs/reference/cli.md`, `AGENTS.md`, ARC guide). (owner: Docs & QA, due: backlog)
- [ ] Extend orchestrate/resolve CLI coverage for advanced profiles; reuse CLI stress fixtures and add resolve scenarios in `tests/cli/test_resolve.py`. (owner: QA & Engineering, due: backlog)
  - Progress: Added `tests/cli/test_resolve_profile.py` coverage for profile-driven Splink defaults, explicit disable flags, and Label Studio wiring; orchestrator stress fixtures still pending once staging data is available.
- [ ] Capture staging evidence for Prefect backfill guardrails and ARC runner sign-off once access returns. (owner: Platform & QA, due: post-1.0)
- [ ] Finish Diátaxis navigation uplift in PR `docs/data-governance-nav` follow-on, ensuring governance artefacts are surfaced. (owner: Docs & UX, due: Phase 6)
- [ ] Restore `make qa` baseline; address `ruff format --check` reporting 137 files to avoid mass reformatting before rerunning the gate. Command: `make qa`. (owner: Engineering, due: 2025-11-05)
- [ ] Investigate Prefect deployment registration regression surfaced by `uv run pytest --cov=hotpass --cov=apps --cov-report=term-missing` (`tests/test_deployment_specs.py::test_deploy_pipeline_filters_and_registers`). (owner: Engineering, due: 2025-11-04)
- [ ] Resolve mypy baseline regressions uncovered by `uv run mypy apps/data-platform tests ops` (90 errors across requests/yaml stubs and CLI/MLflow typing). (owner: Engineering & QA, due: backlog)

## Steps
- [ ] Reproduce `tests/test_deployment_specs.py::test_deploy_pipeline_filters_and_registers` with Prefect runner mocks to isolate extra registrations and draft remediation.
- [ ] Outline a targeted formatting plan (e.g., staged module batches) before running `ruff format` so the `make qa` gate can complete without destabilising history.
- [ ] Catalogue missing stub packages and annotate ownership for the 90 mypy diagnostics before planning fixes.

## Deliverables
- Baseline QA run notes (2025-11-01) covering `make qa`, pytest, mypy, and SBOM status.
- Updated dependency matrix (`pyproject.toml`) including `cyclonedx-bom` for supply chain tooling.
- Generated CycloneDX SBOM at `dist/sbom/hotpass-sbom.json` (2025-11-01) for baseline evidence.

## Quality Gates
- tests: **fail** — `uv run pytest --cov=hotpass --cov=apps --cov-report=term-missing` halted with `tests/test_deployment_specs.py::test_deploy_pipeline_filters_and_registers` asserting only selected deployments register. (owner: Engineering)
- linters/formatters: **fail** — `make qa` stopped at `ruff format --check` after 137 files reported pending formatting. (owner: Engineering)
- type-checks: **fail** — `uv run mypy apps/data-platform tests ops` surfaced 90 errors (missing `yaml`, `requests`, `hypothesis` stubs and CLI/MLflow typing gaps). (owner: Engineering & QA)
- security scan: **blocked** — `make qa` exited before Bandit and detect-secrets stages; rerun once formatting remediation plan is approved. (owner: Engineering & Security)
- coverage: **blocked** — coverage summary unavailable because pytest stopped on failure. (owner: QA)
- build: **not run** — defer until functional gates return green. (owner: Engineering)
- docs updated: **pending** — documentation changes contingent on resolving gating regressions. (owner: Docs)
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
- Security gates remain unverified this pass; ensure Bandit/detect-secrets rerun once formatting gate is addressed.
