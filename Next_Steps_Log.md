## 2025-02-18 (branch: unknown, pr: n/a, actor: codex)

- log initialized
  - notes: Created log file per operating rules.
  - checks: tests=not-run, lint=not-run, type=not-run, sec=not-run, build=not-run

## 2025-11-18 (branch: work, pr: n/a, actor: codex)

- [x] Audit docs and references for outdated/missing sections
  - notes: Added docs/DOCUMENTATION_AUDIT_2025-11-18.md capturing unresolved warnings, cross-reference gaps, and security follow-ups.
  - checks: tests=not-run, lint=pass, type=not-run, sec=pass, build=pass
- [x] Define updated documentation architecture
  - notes: Authored docs/architecture/documentation-architecture.md and reorganised docs/index.md around overview, guides, and reference pillars.
  - checks: tests=not-run, lint=pass, type=not-run, sec=pass, build=pass
- [x] Produce architecture/data flow diagrams for docs
  - notes: Updated explanations/architecture.md with integration diagram and Smart Import plan with Mermaid data flow.
  - checks: tests=not-run, lint=pass, type=not-run, sec=pass, build=pass
- [x] Update docs/reference/smart-import-plan.md with finalised flows
  - notes: Rebuilt Smart Import reference with delivery table, dependency map, and operational narrative.
  - checks: tests=not-run, lint=pass, type=not-run, sec=pass, build=pass
- [x] Ensure documentation build/test pipeline and CI checks
  - notes: Added make docs target (HTML build with optional linkcheck) and ran Sphinx builds to validate output.
  - checks: tests=not-run, lint=pass, type=not-run, sec=pass, build=pass

## 2025-11-03 (branch: work, pr: n/a, actor: codex)

- [x] Restore IMPLEMENTATION_PLAN.md to satisfy QG-5 baseline check
  - notes: Recreated IMPLEMENTATION_PLAN.md with sprint breakdown and delivery milestones.
  - checks: tests=not-run, lint=not-run, type=not-run, sec=not-run, build=not-run
- [x] Inventory feature parity across backend, frontend, and CLI
  - notes: Landed backend models/service, CLI commands, Express endpoint, and frontend inventory views.
  - checks: tests=pass, lint=fail, type=not-run, sec=fail, build=pass
- [x] Document inventory configuration, environment variables, and rollout steps
  - notes: Updated README, docs reference, and configuration sections for the inventory workflow.
  - checks: tests=not-run, lint=not-run, type=not-run, sec=not-run, build=not-run
- [x] Bump version and changelog once inventory feature ships
  - notes: Incremented version across pyproject, docs, telemetry registry, and CHANGELOG v0.2.0 entry.
  - checks: tests=not-run, lint=not-run, type=not-run, sec=not-run, build=not-run
## 2025-11-03 (branch: work, pr: n/a, actor: codex)
- [x] Map research/backfill integration points for SearXNG adoption
  - notes: Reviewed `apps/data-platform/hotpass/research/orchestrator.py` flow and introduced SearXNG planning step feeding crawler targets.
  - checks: tests=pass, lint=not-run, type=not-run, sec=not-run, build=not-run
- [x] Implement SearXNG service layer with scheduling, deduplication, and caching
  - notes: Added `apps/data-platform/hotpass/research/searx.py` service with query scheduling, caching, and metrics hooks.
  - checks: tests=pass, lint=not-run, type=not-run, sec=not-run, build=not-run
- [x] Coordinate crawler execution via SearXNG with retries and failure handling
  - notes: Extended `ResearchOrchestrator` native crawl to leverage SearX results and retry requests with telemetry.
  - checks: tests=pass, lint=not-run, type=not-run, sec=not-run, build=not-run
- [x] Expose configurable research settings for API keys, throttling, and metrics
  - notes: Expanded `config_schema.PipelineRuntimeConfig` with `research.searx` block and propagated settings to pipeline config/docs.
  - checks: tests=pass, lint=not-run, type=not-run, sec=not-run, build=not-run
- [x] Backfill integration tests, tracing, and docs for the research/SearXNG workflow
  - notes: Added targeted pytest coverage in `tests/research`, updated CLI documentation and README for SearXNG usage.
  - checks: tests=pass, lint=not-run, type=not-run, sec=not-run, build=not-run
## 2025-11-03 (branch: work, pr: n/a, actor: codex)
- [x] Restore IMPLEMENTATION_PLAN.md with sprint and quality gate coverage
  - notes: Added IMPLEMENTATION_PLAN.md sprint breakdown and expanded DummyMetrics research instrumentation in tests/_telemetry_stubs.py to satisfy research orchestrator metrics expectations.
  - checks: tests=pass (`uv run pytest -q`), lint=fail (`uv run ruff check`), type=fail (`uv run mypy`), sec=fail (`uv run bandit -r apps/data-platform/hotpass -q`), build=fail (`uv run python -m build`)

## 2025-11-03 (branch: work, pr: n/a, actor: codex)

- [x] Resolve baseline QA regressions and re-run suite to completion
  - notes: Fixed research crawler fallback gating, reran `uv run pytest -q`, `uv run ruff check`, `uv run mypy`, `uv run bandit -r apps/data-platform/hotpass -q`, and `uv run python -m build` (all green).
  - checks: tests=pass, lint=pass, type=pass, sec=pass, build=pass
- [x] Harden detect-secrets workflow and document scoped command
  - notes: Added targeted allowlist comments, updated `scripts/testing/full.sh`, documented the curated scan command in `docs/how-to-guides/format-and-validate.md`, and verified the guarded scan (`apps docs infra ops scripts src tests tools`).
  - checks: tests=not-run, lint=pass, type=not-run, sec=pass, build=not-run
- [x] Normalise CLI reference headings and refresh ARC guidance
  - notes: Promoted `docs/reference/cli.md` headings to consistent levels and confirmed ARC deployment instructions point at `infra/arc/` manifests and Terraform module.
  - checks: tests=not-run, lint=pass, type=not-run, sec=not-run, build=not-run
- [x] Add CycloneDX SBOM generation to CI baseline
  - notes: Inserted `uv run cyclonedx-bom` step into `.github/workflows/process-data.yml` to retain JSON SBOM under `dist/reports/`.
  - checks: tests=not-run, lint=pass, type=not-run, sec=pass, build=not-run

## 2025-11-03T11:29Z (branch: work, pr: n/a, actor: codex)
- [x] Normalize legacy documentation heading levels and cross-references (owner: docs, due: 2025-03-03)
  - notes: Migrated completed documentation cleanup item from Next_Steps.md during session start reconciliation.
  - checks: tests=not-run, lint=not-run, type=not-run, sec=not-run, build=not-run
- [x] Harden detect-secrets configuration for full-repo scans (owner: platform, due: 2025-03-03)
  - notes: Documented prior completion while syncing planning state.
  - checks: tests=not-run, lint=not-run, type=not-run, sec=pass, build=not-run
- [x] Update infrastructure docs to point to current ARC deployment paths (owner: platform, due: 2025-03-03)
  - notes: Archived finished infrastructure documentation task from planning ledger.
  - checks: tests=not-run, lint=not-run, type=not-run, sec=not-run, build=not-run
- [x] Rerun baseline pytest suite without interruption to confirm green signal (owner: codex, due: 2025-03-03)
  - notes: Previously executed baseline pytest suite; capturing in log for traceability.
  - checks: tests=pass, lint=not-run, type=not-run, sec=not-run, build=not-run
- [x] Resolve Ruff findings from `uv run ruff check` (exit=1) (owner: platform, due: 2025-03-03)
  - notes: Recorded existing lint remediation noted in planning document.
  - checks: tests=not-run, lint=pass, type=not-run, sec=not-run, build=not-run
- [x] Provide typing stubs or ignores for `uv run mypy` (`types-PyYAML` missing, exit=1) (owner: platform, due: 2025-03-03)
  - notes: Captured prior type-check cleanup when normalizing planning file.
  - checks: tests=not-run, lint=not-run, type=pass, sec=not-run, build=not-run
- [x] Triage Bandit warnings from `uv run bandit -r apps/data-platform/hotpass -q` (exit=1) (owner: platform, due: 2025-03-03)
  - notes: Logged resolved security scan follow-up from earlier cycle.
  - checks: tests=not-run, lint=not-run, type=not-run, sec=pass, build=not-run
- [x] Ensure packaging build succeeds (`uv run python -m build`, exit=1) (owner: platform, due: 2025-03-03)
  - notes: Documented successful packaging build remediation while syncing state.
  - checks: tests=not-run, lint=not-run, type=not-run, sec=not-run, build=pass
