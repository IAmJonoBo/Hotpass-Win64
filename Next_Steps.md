# Next Steps

## Tasks

- [ ] Normalize legacy documentation heading levels and cross-references (owner: docs, due: 2025-03-03)
- [ ] Harden detect-secrets configuration for full-repo scans (owner: platform, due: 2025-03-03)
- [ ] Update infrastructure docs to point to current ARC deployment paths (owner: platform, due: 2025-03-03)

## Steps

- Prioritise fixing heading hierarchy warnings raised by Sphinx
- Draft detect-secrets baseline with repo-specific excludes
- Audit docs referencing deprecated infrastructure paths
- Coordinate follow-up PRs with owners for the above actions
- Keep docs CI and Makefile targets aligned with the backlog

## Deliverables

- Updated documentation files and diagrams
- Documentation architecture outline
- Docs build/CI configuration updates

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

- Pending baseline quality checks
- Need to confirm existing CI coverage for docs
- Full-repo detect-secrets scan aborted due to scope; targeted docs/apps/tests scan succeeded (follow up to scope excludes)
- Linkcheck disabled by default in make docs (set LINKCHECK=1 to run; currently blocked by external certificate failures)
