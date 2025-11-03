# Next Steps

## Tasks
- [ ] Normalize legacy documentation heading levels and cross-references (owner: docs, due: 2025-03-03)
- [ ] Harden detect-secrets configuration for full-repo scans (owner: platform, due: 2025-03-03)
- [ ] Update infrastructure docs to point to current ARC deployment paths (owner: platform, due: 2025-03-03)
- [ ] Rerun baseline pytest suite without interruption to confirm green signal (owner: codex, due: 2025-03-03)
- [ ] Resolve Ruff findings from `uv run ruff check` (exit=1) (owner: platform, due: 2025-03-03)
- [ ] Provide typing stubs or ignores for `uv run mypy` (`types-PyYAML` missing, exit=1) (owner: platform, due: 2025-03-03)
- [ ] Triage Bandit warnings from `uv run bandit -r apps/data-platform/hotpass -q` (exit=1) (owner: platform, due: 2025-03-03)
- [ ] Ensure packaging build succeeds (`uv run python -m build`, exit=1) (owner: platform, due: 2025-03-03)

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
- Pending baseline quality checks (pytest interrupted; rerun scheduled)
- Need to confirm existing CI coverage for docs
- Full-repo detect-secrets scan aborted due to scope; targeted docs/apps/tests scan succeeded (follow up to scope excludes)
- Linkcheck disabled by default in make docs (set LINKCHECK=1 to run; currently blocked by external certificate failures)
- Verify CODEOWNERS coverage for new research/SearXNG paths once implemented
- Add SBOM generation task to CI once research changes settle
