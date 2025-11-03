# Release Readiness — 2025-11-03

## Baseline tooling results

| Command | Status | Notes |
| --- | --- | --- |
| `TRUNK_SKIP_TRUNK=1 scripts/testing/full.sh` | ⚠️ Timed out after ~225s | Pytest xdist run completed successfully (565 tests, coverage XML generated). Remaining post-processing steps were executed manually (see below). Consider raising the automation timeout to ≥6 min if we keep the full suite in one shell. |
| `uv run coverage html` / `uv run python tools/coverage/report_low_coverage.py ...` | ✅ | HTML report at `htmlcov/`; all modules meet configured thresholds. |
| `uv run mypy apps/data-platform/hotpass/pipeline/config.py ...` | ✅ | No type errors. |
| `uv run bandit -r apps/data-platform ops` | ✅ | No high/medium findings (only previously allow-listed low-confidence warnings). |
| `uv run python -m detect_secrets scan ...` | ✅ | Clean run with pnpm lockfile excluded per policy. |
| `uv run pre-commit run --all-files` | ✅ | All hooks green after removing `ruff-format` duplication. |
| `uv run python -m build` | ✅ | Wheel + sdist emitted under `dist/`. |
| `npm run lint` | ✅ | ESLint passes with React Compiler optimisations intact. |
| `npm run test:unit` | ✅ | Vitest suite (34 tests) with coverage 88.5% statements. |
| `npx playwright test` | ✅ | Accessibility suite clean on `/`, `/lineage`, `/admin`, `/assistant`. |

## Required CI checks / branch protection inputs

Suggested required status checks for `main` and release branches:

1. `pre-commit` (or the individual GitHub Actions job that runs `uv run pre-commit run --all-files`).
2. `pytest` (ensure the job exports coverage XML for archival).
3. `npm run lint` (front-end lint job).
4. `npm run test:unit` (vitest).
5. `npx playwright test` (accessibility + smoke).
6. `build` (invokes `uv run python -m build` and uploads wheels/sdist).
7. `detect-secrets` (optional but recommended for supply-chain posture).

Confirm in GitHub branch protection rules that:

- `Require a pull request before merging` is enabled with code owner review.
- Above checks are listed under “Require status checks to pass before merging.”
- Force pushes and deletions are disabled for protected branches.

## SBOM and release automation

- `.github/workflows/process-data.yml` generates `dist/reports/sbom.json` via `uv run cyclonedx-bom ...`. Verify the artifact is uploaded (search for the “SBOM” artifact in the workflow run) and retained per compliance policy.
- `release-drafter.yml` is present and up to date. Confirm the Release Drafter GitHub Action references the labels introduced in the governance ADR.
- Ensure the supply-chain workflow (CycloneDX + provenance) feeds the same storage bucket documented in `docs/governance/upgrade-final-report.md`.

## Release checklist (to execute for 0.2.x hotfix)

1. Create a release branch `release/0.2.x`.
2. Run the baseline tooling matrix above (or trigger the composite GitHub workflow). Archive the `htmlcov/`, `coverage.xml`, `dist/`, and SBOM artifacts.
3. Update `docs/CHANGELOG.md` (done in this pass) and prepare user-facing notes using `docs/docs/templates/ReleaseNotes.md`.
4. Draft the Git tag (`git tag v0.2.x && git push origin v0.2.x`) once QA sign-off is complete.
5. Publish the GitHub Release using Release Drafter output; attach SBOM and provenance artifacts.
6. Notify support and platform channels with deployment window and rollback hooks.

> **Link for release ticket**: Include this document when drafting the release issue so the owning team has a single source of truth.

## Rollback plan

1. Trigger the deployment pipeline with the previous known-good tag (`v0.2.0`) using the release automation job (`.github/workflows/release.yml`).
2. Revert the `main` branch release commit if necessary (`git revert <merge_sha>`), push, and let CI confirm baseline status.
3. Restore `dist/contracts`, `dist/refined.xlsx`, and other operator artifacts from the most recent S3 snapshot (`s3://hotpass-artifacts/releases/v0.2.0/`).
4. Rotate any API tokens generated during the failed rollout and clear worker queues via Prefect/Kubernetes dashboards to avoid partial replays.
5. Communicate rollback completion and next steps in `#hotpass-ops` and update the incident log.

## Onboarding & support verification

- Developer onboarding: `docs/docs/development/TOOLCHAIN_SETUP.md` and `docs/docs/delivery/RELEASE_PROCESS.md` already reference `uv`, Playwright, and the refreshed pre-commit hooks—no updates required. Surface the new requirement to install Playwright browsers (`npx playwright install`) for local runs in the next revision.
- Support escalation: `docs/docs/community/GOVERNANCE.md` lists release managers and security contacts; confirm the on-call rotation matches PagerDuty schedule before tagging 0.2.x.
- Help Center integration: context-sensitive buttons added in this cycle point to `docs/how-to-guides/**` topics (`openHelp` handlers). Verify those docs stay published in the operator portal prior to release.

Store this checklist alongside artifacts and link it in the release issue for traceability.
