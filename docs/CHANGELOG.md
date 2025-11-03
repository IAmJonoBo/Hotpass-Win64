# Hotpass Changelog

## 2025-11-03 — Import assist enhancements and run telemetry

### Dashboard & operator workflows
- Added inline Help Center anchors so import, contracts, and lineage widgets open topic-specific guidance without leaving the dashboard.
- Introduced a contracts explorer card backed by the new `/api/contracts` endpoint, enabling operators to download the latest YAML/JSON contracts directly from `dist/contracts`.
- Surfaced the most recent cell-level auto-fix via the Cell Spotlight panel, complete with assistant hand-off and sheet metadata.

### Run diagnostics
- Exposed `/api/runs/:id/logs` SSE stream and reworked Run Details to show live log tails with <200 ms highlight effects for fresh events.
- Wired contextual action buttons (rerun pipeline, enrich, plan research, explain provenance) to prefilled assistant prompts for faster remediation.

### Platform & documentation
- Documented `HOTPASS_IMPORT_ROOT` and `HOTPASS_CONTRACT_ROOT` environment variables for deployments that relocate artifact directories.
- Added unit coverage for CellSpotlight parsing heuristics, keeping the import UI under test.
- Refreshed the implementation summary and feature inventory to highlight remaining governance and planner tasks.

### Known gaps
- LiveProcessingWidget metrics still require dedicated tests.
- Planner tab (`plan research`) and approvals audit timeline remain open items for Stage 3.3/3.2 respectively.

## 2025-11-02 — UI hardening, pipeline guardrails, and security telemetry

### User interface and accessibility
- Enforced Okta/OIDC role gating across the web UI, introducing reusable guards and encrypted HIL storage so approver/admin only routes stay locked down while offline evidence persists safely. Evidence: `dist/staging/backfill/20251101T171853Z/hotpass-e2e-staging.log`.
- Added sidebar auth status controls and Playwright accessibility smoke coverage to guarantee assistive technologies surface approval states before operators take action. Evidence: `apps/web-ui/tests/auth.spec.ts` run with Playwright a11y assertions.

### Pipeline resilience
- Rehearsed refine→enrich lineage bundles end-to-end, capturing outputs, archive rehydration, and lineage artefacts for replay verification. Evidence: `dist/staging/marquez/20251101T171901Z/cli.log` and `dist/staging/backfill/20251101T171853Z/metadata.json`.
- Benchmarked `HotpassConfig.merge` on production-sized payloads to validate configuration merge performance before reopening backfill guardrails. Evidence: `dist/benchmarks/hotpass_config_merge.json`.

### Security and compliance
- Fronted Prefect and Marquez APIs with rate-limited proxies, CSRF-protected telemetry endpoints, and audit logging so cross-system orchestration meets security review expectations.
- Regenerated CycloneDX SBOMs and provenance attestations for the release using `ops/supply_chain/generate_sbom.py` and `generate_provenance.py`, archiving artefacts under `dist/sbom/hotpass-sbom.json/`.

### Known issues
- `pytest tests --cov=hotpass --cov=apps` fails when invoking `uv run hotpass explain-provenance` because the `pip-audit>=2.7.3`/`cyclonedx-python-lib>=11` constraints inside `hotpass[ci]` are incompatible. The gating fix is tracked in `Next_Steps.md` (Tests → Restore uv resolver compatibility) until dependency pins converge.

### Quality signals
- Latest accessibility + Playwright suite passes (`apps/web-ui/tests/auth.spec.ts`).
- Baseline coverage remains at 72% (last successful full run on 2025-11-01); no delta recorded because the uv resolver issue blocks current coverage aggregation.
