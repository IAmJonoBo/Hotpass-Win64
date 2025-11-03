# Inventory Feature Implementation Plan

## Objectives

- Provide a governed asset inventory that is accessible from the Hotpass backend, CLI, and operator web UI.
- Track implementation status for each surface (backend service, CLI tooling, and frontend experience).
- Share a single source of truth for asset metadata (owner, custodian, controls) sourced from `data/inventory/asset-register.yaml`.
- Expose lightweight summaries for operators while keeping the YAML manifest authoritative.

## Scope and Deliverables

1. **Backend service**
   - Parse and validate the asset register using strict schemas.
   - Cache inventory snapshots with TTL + mtime guards for predictable performance.
   - Produce summaries and requirement status metadata for downstream consumers.
2. **CLI command**
   - Add `hotpass inventory` with `list` and `status` actions (tabular + JSON output).
   - Surface requirement status (backend/frontend/CLI) and asset summaries.
3. **Web UI + API**
   - Add `/api/inventory` endpoint returning assets, summary metrics, and requirement status.
   - Create an Inventory page under Governance with filtering/search and status callouts.
   - Link the new page from the sidebar and help surfaces.
4. **Testing & automation**
   - Unit tests for inventory parsing, caching, and status evaluation.
   - CLI regression tests for `hotpass inventory`.
   - React component tests + API client tests to ensure rendering and empty states.
5. **Docs & release hygiene**
   - Update README, CLI reference, repo inventory, and AGENTS (where relevant).
   - Document new environment variables (`HOTPASS_INVENTORY_PATH`, cache TTL overrides).
   - Add changelog entry and bump project/package versions.

## Milestones

1. Schema + service foundation (backend)
2. CLI plumbing and quality gates update
3. API + frontend integration
4. Docs, changelog, and version bump
5. QA pass (pytest + vitest + lint/type checks)

## Sprint breakdown

- **Sprint 1** — Finalise schemas, caching strategy, and manifest normalisation for the backend service.
- **Sprint 2** — Ship CLI command wiring, update quality gates, and confirm operator workflows.
- **Sprint 3** — Expose `/api/inventory` for the Governance UI and connect React surfaces.
- **Sprint 4** — Harden docs, configuration validation, and release assets (version bump + changelog).
- **Sprint 5** — Burn down QA/regression items, expand automated tests, and validate rollout telemetry.

## Risks / Mitigations

- **Large manifests**: ensure caching supports TTL + file mtime to avoid reparsing.
- **Missing env vars**: validate configuration early with descriptive errors.
- **Front-end drift**: centralise requirement status in backend module and reuse via API to keep UI and CLI aligned.
- **Baseline failures**: maintain tests referencing the new command and docs to keep QG-1 passing.

## Success Criteria

- `hotpass inventory list` returns parsed assets and summary metrics.
- `/api/inventory` responds with assets + requirement status and is consumed by the Governance Inventory page.
- Documentation references the new workflow and environment variables.
- Project version bumped with changelog entry summarising the rollout.
