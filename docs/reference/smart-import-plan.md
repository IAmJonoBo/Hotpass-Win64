## Smart Import Implementation Tracker

| Stage                                                                  | Status           | Notes                                                         |
| ---------------------------------------------------------------------- | ---------------- | ------------------------------------------------------------- |
| Profiling service (`hotpass imports profile`, `/api/imports/profile`)  | ✅               | Sheet summaries, column heuristics, role/keys, issue catalog  |
| Preprocessing engine (`import_mappings`, `import_rules`)               | ✅ (phase 1)     | Rename/normalise/date/drop rules wired into pipeline          |
| Sheet role classification & join hints                                 | ✅               | Profiler now emits `role` and `join_keys` per sheet           |
| Default import templates                                               | ✅               | `profiles/generic/imports/default.json` seeds base rules      |
| Advanced rule library (rename, normalize_date, drop_layout rows, etc.) | ✅ (initial set) | Additional rules ready for per-profile layering               |
| Consolidation / relational export                                      | ⏳               | TODO: entity/contact/address joins + multi-tab/Parquet export |
| Wizard UI (mapping editor, rule toggles, preview)                      | ⏳               | Backend-ready; FE implementation pending                      |
| Template service (list/save/delete)                                    | ✅               | REST endpoints + storage for named templates (`/api/imports/templates`) |
| Assistant integration (reuse templates, surface issues)                | ✅ (phase 1)     | Assistant tools cover template summary/contract/telemetry     |
| QA/HIL alignment                                                       | ⏳               | Surface auto-fixes & unresolved issues in HIL panel           |

### Next Actions

**Backend**

1. Implement relational consolidation helpers so entity + contact + address sheets can emit tidy linked tables (preserving multi-location/contact data) and export complementary Parquet/JSON bundles.
2. Extend the rule library with fuzzy matching, geocoding backfill, duplicate resolution, and provenance tagging; keep rules white-label by default.
3. Emit structured import issue logs via SSE/telemetry for dashboards & HIL.
4. Add batch contract generation support (per-profile suites) and persist manifest metadata alongside `dist/contracts`.

**Wizard / UI**

5. Surface profiler sheet roles + join hints in the wizard to drive default mapping selections.
6. Implement run submission + queue trigger from the wizard, including job status hand-off and notifications.
7. Provide result summaries (autofixes, blockers, recommendations) and allow template diff export directly from the wizard UI.

**Assistant / CLI**

8. Enable assistants/CLI to trigger refinement with `--import-template` arguments and expose contract artifacts in chat responses.
9. Add assistant actions that preview suggested fixes before applying them, keeping a human-in-the-loop confirmation.

**Quality & Governance**

10. Surface import issues in pipeline telemetry/HIL workflows so operators can approve/reject critical fixes with context.
11. Keep all defaults industry-agnostic; profile-specific templates remain optional overlays.
12. Wire consolidation telemetry into governance dashboards (QA/HIL review tooling).

_Updated: 2025-11-03_

### Implementation Notes (2025-11-03)

- **Client architecture**

  - Create `apps/web-ui/src/api/imports.ts` exposing `profileWorkbook({ file?, workbookPath?, sampleRows, maxRows })` → `ImportProfile`.
  - Provide React Query helpers: `useImportProfile` (mutation for ad-hoc profiling) and `useStoredProfiles` (query pulling cached results once persistence lands).
  - Extend `@/types` with `ImportProfile`, `SheetProfile`, `ColumnProfile`, `ImportIssue` to keep UI/server payloads aligned.

- **Dataset import UI**

- Embed an `ImportProfilePreview` panel inside `DatasetImportPanel` prior to pipeline submission (sheet cards, column stats, join-key badges, issue list, download button).
- Promote a dedicated `/imports/wizard` route with `SmartImportWizard`, editable Mapping/Rules steps, consolidation preview, and summary actions so operators can adjust mappings before running `refine`.
- Reuse the new hooks above for both the quick preview and the multi-step wizard; surface “Attach profile to run”, manage templates, and export wizard payloads.

- **Persistence strategy**

  - Persist profiling payloads under `.hotpass/ui/import-profiles/` via `server/storage.js` helpers for quick recall.
  - When an import job kicks off, copy the selected payload into `dist/import/<job-id>/profile.json` and include a download link in job metadata.
  - Optional future enhancement: add `GET /api/imports/profile/:id` to retrieve archived payloads without hitting disk directly.

- **Template/API status**

  - `/api/imports/templates` CRUD endpoints (list/create/update/delete) with storage helpers live under `.hotpass/ui/imports/templates/*.json`.
  - Assistant + CLI tooling consumes the same endpoints for summary, contract publishing, and telemetry.
  - Remaining work: batch contract automation, diff manifest export, and governance dashboards that consume consolidation telemetry.

- **Current scaffolding (2025-11-03)**

  - Client module `importsApi` now exposes `profileWorkbook`, stored profile CRUD, and template CRUD plus React Query hooks (`useImportProfileMutation`, `useStoredImportProfiles`, `useImportTemplates`, `useImportTemplateUpsert`, `useImportTemplateDelete`).
  - Express server stubs `/api/imports/profiles` (GET/POST/DELETE) and `/api/imports/templates` (GET/POST/PUT/DELETE) backed by new storage helpers in `server/storage.js`.
  - Stored assets live under `.hotpass/ui/imports/{profiles,templates}/<id>.json`; templates enforce name + payload validation and dedupe tags.
  - UI includes DatasetImport profiling preview, Smart Import wizard with editable mapping/rule steps, consolidation preview, template export, and TemplateManager drawer for CRUD operations.
  - Assistant tooling (`apps/web-ui/src/agent/tools.ts`) exposes list/get/save/delete helpers for import templates, aligning CLI/assistant behaviour with the REST API.

- **Recommended execution order**
  1. ✅ Wire `DatasetImportPanel` to `useImportProfileMutation`, render an `ImportProfilePreview`, and expose download/attach actions (2025-11-03).
  2. ✅ When an import run starts, persist the chosen profile metadata alongside the job (`dist/import/<job-id>/profile.json`) and surface the artifact link in job events (2025-11-03).
  3. ✅ Stand up the `/imports/wizard` route with step components (Upload → Profile → Mapping → Rules → Summary) reusing stored profiles/templates (editable mapping/rule forms + consolidation preview live 2025-11-03).
  4. ✅ Layer on template management UI (`TemplatePicker`, `TemplateManagerDrawer`) plus CLI/assistant template tools (2025-11-03).
  5. 🔭 Next: batch contract automation + diff manifests, assistant-driven run orchestration, and governance dashboards with consolidation telemetry.
