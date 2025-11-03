# Next Steps

## Tasks

- [x] Resolve `uv run ruff check` (exit=1) UP038/I001/UP035/E501 lint regressions across inventory, MCP, Prefect tooling, and profile lint scripts (owner: platform, due: 2025-11-10)
- [x] Provide typing stubs or ignores for `uv run mypy` missing `yaml` stubs (exit=1) (owner: platform, due: 2025-11-10)
- [x] Ensure packaging build dependencies available so `uv run python -m build` succeeds (exit=1) (owner: platform, due: 2025-11-10)
- [x] Resolve local trunk CLI availability or adjust QA workflow guard (owner: platform, due: 2025-03-03)
- [x] Address repo-wide pre-commit failures blocking `scripts/testing/full.sh` (owner: platform, due: 2025-11-10)
- [x] Fix React compiler lint errors and restore coverage thresholds in `npm run test:unit` (owner: frontend, due: 2025-11-10)
- [x] Resolve Playwright e2e failures for `npx playwright test` (exit=1) caused by duplicate exports and missing browsers (owner: frontend, due: 2025-11-10)
- [x] Triage detect-secrets findings in `apps/web-ui/pnpm-lock.yaml` (owner: security, due: 2025-11-10)
- [ ] Expand automated coverage for inventory workflows and performance benchmarks (owner: qa, due: 2025-03-10)

## Steps

1. Monitor the refreshed QA pipeline (pre-commit + playwright axe) and bake the new accessibility patterns into component guidelines.
2. Prioritise remaining coverage/performance expansion for inventory workflows now that lint/test gates are green.
3. Coordinate cross-team follow-up on documentation + telemetry improvements surfaced during accessibility hardening.

## Deliverables

- Updated documentation files and diagrams
- Documentation architecture outline
- Docs build/CI configuration updates
- Inventory service code, CLI commands, and frontend surfaces
- Automated tests and performance benchmarks for inventory flows
- CHANGELOG entry and version bump proposal

## Quality Gates

- tests: pass
- linters/formatters: clean
- type-checks: clean
- security scan: clean
- coverage: ≥ current baseline
- build: success
- docs updated

## Links

- PRs: pending
- Files/lines: pending

## Risks/Notes

- Accessibility axe suite is now a hard gate; new icon-only controls must ship with `aria-label`/text equivalents or face regression failures.
- Coverage sits comfortably above thresholds after new hook/linkage tests, but inventory performance benchmarking remains outstanding.
- `scripts/testing/full.sh` now bootstraps `pytest-xdist`; document the `HOTPASS_SKIP_XDIST_BOOTSTRAP` escape hatch for constrained envs.
- Detect-secrets baseline regenerated without lockfile noise; future dependency bumps should reuse the targeted scan scope.
- Docs linkcheck remains disabled pending upstream TLS fixes; coordinate with docs team before re-enabling to avoid CI churn.
