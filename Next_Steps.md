# Next Steps

## Tasks

- [ ] Normalize legacy documentation heading levels and cross-references (owner: docs, due: 2025-03-03)
- [ ] Harden detect-secrets configuration for full-repo scans (owner: platform, due: 2025-03-03)
- [ ] Update infrastructure docs to point to current ARC deployment paths (owner: platform, due: 2025-03-03)
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
