# Next Steps

## Tasks
- [x] Normalize legacy documentation heading levels and cross-references (owner: docs, due: 2025-03-03)
- [x] Harden detect-secrets configuration for full-repo scans (owner: platform, due: 2025-03-03)
- [x] Update infrastructure docs to point to current ARC deployment paths (owner: platform, due: 2025-03-03)
- [ ] Resolve local trunk CLI availability or adjust QA workflow guard (owner: platform, due: 2025-03-03)
- [ ] Address repo-wide pre-commit failures blocking `scripts/testing/full.sh` (owner: platform, due: 2025-11-10)
- [ ] Fix React compiler lint errors and restore coverage thresholds in `npm run test:unit` (owner: frontend, due: 2025-11-10)
- [ ] Triage detect-secrets findings in `apps/web-ui/pnpm-lock.yaml` (owner: security, due: 2025-11-10)
- [ ] Expand automated coverage for inventory workflows and performance benchmarks (owner: qa, due: 2025-03-10)

## Steps

1. Stabilize baseline QA tooling (pre-commit, trunk availability, detect-secrets scope).
2. Resolve frontend lint/coverage regressions introduced by React compiler rules.
3. Extend inventory coverage and performance benchmarks once quality gates are green.
4. Refresh supporting platform/docs tasks as dependencies unblock.

## Deliverables

- Updated documentation files and diagrams
- Documentation architecture outline
- Docs build/CI configuration updates
- Inventory service code, CLI commands, and frontend surfaces
- Automated tests and performance benchmarks for inventory flows
- CHANGELOG entry and version bump proposal
- [x] Rerun baseline pytest suite without interruption to confirm green signal (owner: codex, due: 2025-03-03)
- [x] Resolve Ruff findings from `uv run ruff check` (exit=1) (owner: platform, due: 2025-03-03)
- [x] Provide typing stubs or ignores for `uv run mypy` (`types-PyYAML` missing, exit=1) (owner: platform, due: 2025-03-03)
- [x] Triage Bandit warnings from `uv run bandit -r apps/data-platform/hotpass -q` (exit=1) (owner: platform, due: 2025-03-03)
- [x] Ensure packaging build succeeds (`uv run python -m build`, exit=1) (owner: platform, due: 2025-03-03)

## Steps
- Prioritise fixing heading hierarchy warnings raised by Sphinx
- Capture Ruff/mypy/bandit/build remediation from baseline failures
- Draft detect-secrets baseline with repo-specific excludes
- Audit docs referencing deprecated infrastructure paths
- Finalise detect-secrets policy updates once backlog items clear
- Reconcile infrastructure docs with ARC deployment paths
- Schedule uninterrupted baseline pytest/lint run before handover

## Deliverables
- Detect-secrets baseline update and corresponding CI notes
- Revised infrastructure runbooks reflecting ARC deployment paths
- Documentation lint fixes for heading hierarchy
- Baseline QA report from uninterrupted pytest/lint execution

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

- `scripts/testing/full.sh` fails on repo-wide pre-commit hooks (ruff import order, historical long lines, detect-secrets matches) — requires follow-up sweep or narrowed hook scope.
- `npm run lint` fails on existing React compiler memoization warnings unrelated to inventory changes.
- `npm run test:unit` passes tests but fails global coverage thresholds (baseline < required 60%).
- Local trunk CLI missing; QA scripts require override or bundled binary.
- Need to confirm existing CI coverage for docs and inventory flows.
- Linkcheck disabled by default in make docs (set LINKCHECK=1 to run; currently blocked by external certificate failures).
- Baseline QA suite now passes (`uv run pytest -q`, `ruff`, `mypy`, `bandit`, `python -m build`); track runtime as suites expand.
- Detect-secrets scan now runs with targeted directory list to avoid timeout (`apps docs infra ops scripts src tests tools`); monitor for regressions when new repos are added.
- Verify CODEOWNERS coverage for new research/SearXNG paths once implemented
- CycloneDX SBOM generation now runs in `.github/workflows/process-data.yml`; confirm the artifact retention policy meets compliance requirements.
