# Hotpass Changelog

## 2025-11-20 — Governance inventory UI alignment

### Governance inventory
- Wired the `/governance/inventory` route into the React router with role guards so operators and approvers can reach the govern
ance snapshot directly from the sidebar.
- Added locale-aware snapshot timestamps and mobile overflow handling to the inventory table so manifests render cleanly on smal
ler breakpoints.
- Hardened the inventory fetch client to surface backend JSON error messages (manifest missing, cache failures) instead of gener
ic HTTP status text.

### Frontend infrastructure
- Copied `data/inventory` into the production Docker image and documented the dependency in the UI feature catalog so `/api/inv
entory` remains available out of the box.
- Extended the Vite dev proxy with `/api/inventory` so local development setups can share the Express backend without additional
 wiring.

### Quality
- Added Vitest coverage for the `Inventory` page hook-up and API error handling scenarios.
- Introduced a Playwright `inventory` spec to exercise the new navigation route and backend stub.

## 2025-11-19 — Inventory feature rollout (v0.2.0)

### Inventory orchestration
- Finalised the `hotpass.inventory` backend module with schema coercion, cache validation, and manifest normalisation so YAML manifests with implicit dates parse reliably and reuse cached summaries safely.
- Added configuration guards for `HOTPASS_INVENTORY_PATH` and cache TTL overrides, surfacing clear errors when misconfigured in CLI or service environments.

### Operator workflows
- Extended the unified CLI with table output tests and documentation so `hotpass inventory list`/`status` integrate into quality gates and AGENT workflows.
- Instrumented the Express `/api/inventory` endpoint with cache invalidation helpers and exported server handles, enabling integration tests to validate JSON payloads and degraded responses.

### Web experience
- Bumped the Governance UI version banner and added vitest + supertest coverage around `/api/inventory` to ensure the React inventory page always receives normalised snapshots.

### Release management
- Bumped project, documentation, telemetry, and UI package versions to `0.2.0` and recorded the rollout details here.
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

### Accessibility & QA hardening
- Normalised icon-only controls, scroll regions, and alert palettes across dashboard, contracts explorer, lineage filters, and assistant widgets so Playwright axe scans pass on `/`, `/lineage`, `/admin`, and `/assistant`.
- Tightened shared primitives (`<Table>`, power tools command previews, sheet close buttons) to expose keyboard focus and narratable labels, eliminating nested interactive/control violations.
- Upgraded the QA harness to bootstrap `pytest-xdist`, regenerated the detect-secrets baseline without lockfile noise, and retired redundant `ruff-format` hooks so pre-commit completes cleanly on airgapped agents.

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
