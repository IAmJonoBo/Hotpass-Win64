# Hotpass Changelog

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
