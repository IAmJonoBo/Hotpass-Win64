# Pull request template

## Summary

- [x] Linked roadmap item: Phase 5 T5.5 (ephemeral runners) confirmed and tagged in `ROADMAP.md`/`docs/roadmap.md`.
- [x] Documentation updated (Diátaxis + TechDocs) — release notes captured in `docs/CHANGELOG.md`, roadmap metadata refreshed, and `IMPLEMENTATION_SUMMARY.md` addendum added.
- [x] `Next_Steps.md` updated (new resolver remediation task + refreshed quality gate status).

### What changed / Why
- Drafted 2025-11-02 release notes covering UI guardrails, pipeline rehearsals, and security hardening so stakeholders have a single evidence trail for the programme review.
- Tagged Phase 5 T5.5 as complete across roadmap artefacts with links to rehearsal logs in `dist/staging/` to confirm ARC + OIDC readiness.
- Added an implementation addendum summarising the UI/pipeline/security work and baseline quality signals for quick context during sign-off.

### Coverage delta
- Baseline coverage remains 72% (last green run: 2025-11-01). Current run blocked by `pip-audit` ↔ `cyclonedx-python-lib` resolver conflict; no coverage delta recorded.

## Testing

| Category | Command | Status | Notes |
| --- | --- | --- | --- |
| Unit / Integration | `pytest tests --maxfail=1 --cov=hotpass --cov=apps --cov-report=term-missing` | ❌ | Fails at `tests/cli/test_explain_provenance.py` because `uv run hotpass explain-provenance` cannot resolve `pip-audit>=2.7.3` with `cyclonedx-python-lib>=11`. |
| Lint | `ruff check`; `ruff format --check` | ⚠️ | Existing backlog (200+ diffs, 5 files needing format) unchanged; no auto-fixes applied. |
| Type-check | `mypy apps/data-platform tests ops` | ⚠️ | 30 errors (missing stubs + scrapy imports) persist from backlog. |
| Security (SAST) | `bandit -r apps/data-platform ops`; `detect-secrets scan apps/data-platform tests ops` | ⚠️ | Bandit reports known low severity subprocess usage; detect-secrets clean. |
| Build / Supply-chain | `python -m build`; `python ops/supply_chain/generate_sbom.py --output dist/sbom/hotpass-sbom.json` | ✅ | Wheel + sdist build succeeded; SBOM regenerated under `dist/sbom/hotpass-sbom.json/`. |
| Accessibility & Playwright | _Not rerun this pass_ | ℹ️ | Coverage captured in release artefacts (`apps/web-ui/tests/auth.spec.ts`); no regressions expected from documentation-only change. |
| E2E / Prefect | _Deferred_ | ℹ️ | Staging access still pending; follow-up tracked in `Next_Steps.md` tasks. |

## Risk & mitigation

- **Risk:** Release documentation references outstanding QA gaps (pytest resolver failure, lint/type debt). Residual technical debt could block CI consumers if unresolved.
- **Rollback plan:** Revert the doc updates (`docs/CHANGELOG.md`, `IMPLEMENTATION_SUMMARY.md`, `ROADMAP.md`, `docs/roadmap.md`, `.github/PULL_REQUEST_TEMPLATE.md`) and restore `Next_Steps.md`/log entries if stakeholders request rollback; no runtime configuration changed.

## Artefacts

- CycloneDX SBOM: `dist/sbom/hotpass-sbom.json/hotpass-sbom.json`
- Prefect/Marquez rehearsal logs: `dist/staging/backfill/20251101T171853Z/` and `dist/staging/marquez/20251101T171901Z/`
- Config merge benchmark: `dist/benchmarks/hotpass_config_merge.json`
