# Hotpass Implementation Plan

This implementation plan documents the incremental delivery of Hotpass platform enhancements.
It is structured around short sprints with explicit quality gate coverage to ensure each
milestone maintains production-readiness.

## Sprint 0 – Baseline Alignment
- Inventory existing data ingestion, orchestration, and research components.
- Restore missing documentation artifacts required by QG-5.
- Re-establish baseline CI runs (pytest with coverage, lint, mypy, bandit) and capture metrics.

## Sprint 1 – Research Platform Hardening
- Ship the SearXNG research service layer with configurable throttling and caching.
- Wire orchestration to schedule research queries, deduplicate URLs, and surface telemetry.
- Document configuration surfaces (API keys, rate limits, observability) in README and docs.
- Validate QG-1 (CLI integrity) and QG-3 (enrichment chain) against the new research entrypoints.

## Sprint 2 – Security and Documentation Controls
- Finalise detect-secrets policies and baseline to enable full repository scanning in CI.
- Resolve heading hierarchy warnings in Sphinx builds and reconcile ARC deployment docs.
- Introduce CODEOWNERS coverage for newly added research components.
- Exercise QG-2 (data quality) and QG-5 (documentation completeness) with updated artifacts.

## Sprint 3 – Observability and Release Readiness
- Add expanded telemetry metrics and dashboards for research throughput and crawler health.
- Generate SBOM artifacts and align CI pipelines with security expectations.
- Perform uninterrupted baseline QA run (pytest, lint, mypy, bandit) before handover.
- Review QG-4 (MCP discoverability) alongside MCP server smoke tests.

## Quality Gate Traceability
- QG-1 (CLI Integrity): `hotpass overview` and verb help verified each sprint before release.
- QG-2 (Data Quality): Great Expectations suites executed against refined datasets after ingest updates.
- QG-3 (Enrichment Chain): Offline enrichment plus provenance checks validated prior to enabling network features.
- QG-4 (MCP Discoverability): MCP server enumerated via `hotpass.mcp.server` and Dolphin MCP tooling.
- QG-5 (Docs & Instructions): AGENTS.md, IMPLEMENTATION_PLAN.md, and `.github/copilot-instructions.md` reviewed every sprint.

## Milestones and Dependencies
- MCP integration depends on feature flags `FEATURE_ENABLE_REMOTE_RESEARCH` and `ALLOW_NETWORK_RESEARCH` being set.
- Detect-secrets rollout requires coordination with platform security for approved excludes.
- ARC deployment documentation must track infrastructure updates coordinated with the ARC operations team.

## Risks and Mitigations
- **Risk:** Research crawl throttling misconfiguration could breach provider limits.
  **Mitigation:** Default conservative rate limits and add observability alerts in telemetry.
- **Risk:** Documentation drift leading to quality gate regressions.
  **Mitigation:** Tie documentation updates to sprint exit criteria and run QG-5 validation script before merges.
- **Risk:** Security baseline gaps uncovered late in the cycle.
  **Mitigation:** Execute detect-secrets and bandit scans at the start of each sprint and remediate immediately.
