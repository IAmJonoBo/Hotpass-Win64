# Hotpass UI Feature Catalog and Backlog Alignment

This catalog tracks the web UI surfaces that depend on backend Hotpass APIs. It captures what is shipping today, highlights open gaps, and links each item to the backend contract it depends on so frontend and platform work can stay coordinated.

## Summary

| Surface | Backend API / Module | UI Entry Point | Status |
| --- | --- | --- | --- |
| Governance inventory snapshot | Express `GET /api/inventory` → `apps/data-platform/hotpass/inventory` service | `/governance/inventory` → `InventoryOverview` | ✅ Routed and responsive (snapshot + requirements, new error handling) |
| Contracts explorer | Express `GET /api/contracts` | Dashboard `ContractsExplorer` | ✅ Operational (requires `dist/contracts` volume) |
| Import job live view | Express `/api/imports/**`, `/api/jobs/:id/events` | Dashboard `DatasetImportPanel` | ✅ Operational (SSE + metadata hydration) |
| Import template summaries | Express `GET /api/imports/templates/:id/summary` | (missing) | ⏳ Pending UI surface |
| Import/contract artifact downloads | Express `/api/jobs/:id/artifacts/*` | (partial) Dashboard `DatasetImportPanel` | ⏳ UI wiring incomplete for profile/contract download |
| Inventory feature status guard | `hotpass.inventory.status.load_feature_requirements` | `InventoryOverview` requirement badges | ✅ Status + detail surfaced |

**Legend:** ✅ shipped · ⏳ planned · ⚠️ blocked

## Detailed backlog

### Governance inventory page
- **Backend contract:** `GET /api/inventory` backed by `InventoryService` and feature status loader.
- **Current UI:** Inventory overview card renders manifest metadata, requirements, and tabular assets. Routed via `/governance/inventory` (new) and participates in the sidebar navigation guard for operator/approver/admin roles.
- **New work in this PR:**
  - Added React Router route and responsive tweaks (mobile overflow handling, locale-aware timestamp, richer error messages).
  - Hardened the fetch client to surface backend `error` details so manifest misconfigurations show actionable feedback instead of generic HTTP status text.
  - Copied `data/inventory` into the production container so the Express layer can serve manifests without extra volumes.
- **Follow-up:** None; page is now aligned with backend service expectations.

### Import template summary API consumption
- **Backend contract:** `GET /api/imports/templates/:id/summary` summarises template metadata and consolidation stats (`apps/web-ui/server/index.mjs`).
- **Current UI gap:** No component requests the summary endpoint; the Imports wizard only lists templates (`useImportTemplates`) and allows CRUD, but does not surface consolidated statistics (sample columns, calculated rules, consolidation telemetry).
- **Next action:** Build a detail drawer or template inspector in the Imports wizard that calls the summary endpoint and exposes aggregation metrics for operators (status ⏳ pending).

### Job artifact download UX
- **Backend contract:** `/api/jobs/:id/artifacts`, `/profile`, `/contract`, `/refined`, `/archive/:filename` (Express server enumerates and streams files emitted by pipeline runs).
- **Current UI gap:** `DatasetImportPanel` tracks the artifact metadata but only renders inline badges; there is no download affordance for individual artifacts (profiles, contract snapshots, archived inputs).
- **Next action:** Add download buttons per artifact row leveraging the existing metadata (URLs already normalised). Ensure access is role-gated and flagged when archive directories are missing (status ⏳ pending).

### Contracts explorer prerequisite volumes
- **Backend contract:** `GET /api/contracts` lists files under `HOTPASS_CONTRACT_ROOT` (defaults to `dist/contracts`).
- **Operational note:** Containers must mount or bake the contracts directory alongside the UI bundle. The Dockerfile now ensures inventory manifests ship with the UI; a follow-up item is to copy contracts archives or document the volume requirement in the deployment guides.

## References
- Backend inventory service: `apps/data-platform/hotpass/inventory/service.py`
- Inventory feature status rules: `apps/data-platform/hotpass/inventory/status.py`
- Express server contracts: `apps/web-ui/server/index.mjs`
- Governance components: `apps/web-ui/src/components/governance`
