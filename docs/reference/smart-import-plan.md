## Smart Import Implementation Tracker

| Stage | Status | Notes |
| --- | --- | --- |
| Profiling service (`hotpass imports profile`, `/api/imports/profile`) | ✅ | Sheet summaries, column heuristics, role/keys, issue catalog |
| Preprocessing engine (`import_mappings`, `import_rules`) | ✅ (phase 1) | Rename/normalise/date/drop rules wired into pipeline |
| Sheet role classification & join hints | ✅ | Profiler now emits `role` and `join_keys` per sheet |
| Default import templates | ✅ | `profiles/generic/imports/default.json` seeds base rules |
| Advanced rule library (rename, normalize_date, drop_layout rows, etc.) | ✅ (initial set) | Additional rules ready for per-profile layering |
| Consolidation / relational export | ⏳ | TODO: entity/contact/address joins + multi-tab/Parquet export |
| Wizard UI (mapping editor, rule toggles, preview) | ⏳ | Backend-ready; FE implementation pending |
| Template service (list/save/delete) | ⏳ | Need REST endpoints + storage for named templates |
| Assistant integration (reuse templates, surface issues) | ⏳ | Queue after wizard foundation |
| QA/HIL alignment | ⏳ | Surface auto-fixes & unresolved issues in HIL panel |

### Next Actions

**Backend**
1. Implement relational consolidation helpers so entity + contact + address sheets can emit tidy linked tables (preserving multi-location/contact data) and export complementary Parquet/JSON bundles.  
2. Add API + persistence for named templates (list/create/update/delete) so wizard/assistant/CLI can reuse shared configs.  
3. Extend rule library with fuzzy matching, geocoding backfill, duplicate resolution, and provenance tagging; keep rules white-label by default.  
4. Emit structured import issue logs via SSE/telemetry for dashboards & HIL.  

**Wizard / UI**
5. Expose profiler sheet roles + join hints in the wizard to drive default selections.  
6. Build wizard steps: sheet selection → mapping editor (rename/type adjustments) → rule toggle preview (diff view) → run submission.  
7. Provide result summary (autofixes, blockers, recommendations) and allow template save directly from the wizard.

**Assistant / CLI**
8. Allow assistants/CLI to reference named templates (`--import-template foo`) and surface import issue summaries in chat/CLI output.  
9. Add assistant actions that preview suggested fixes before applying them, keeping a human-in-the-loop confirmation.

**Quality & Governance**
10. Surface import issues in pipeline telemetry/HIL workflows so operators can approve/reject critical fixes with context.  
11. Keep all defaults industry-agnostic; profile-specific templates remain optional overlays.

_Updated: 2025-11-03_

### Implementation Notes (2025-11-03)

- **Client architecture**  
  - Create `apps/web-ui/src/api/imports.ts` exposing `profileWorkbook({ file?, workbookPath?, sampleRows, maxRows })` → `ImportProfile`.  
  - Provide React Query helpers: `useImportProfile` (mutation for ad-hoc profiling) and `useStoredProfiles` (query pulling cached results once persistence lands).  
  - Extend `@/types` with `ImportProfile`, `SheetProfile`, `ColumnProfile`, `ImportIssue` to keep UI/server payloads aligned.

- **Dataset import UI**  
  - Embed an `ImportProfilePreview` panel inside `DatasetImportPanel` prior to pipeline submission (sheet cards, column stats, join-key badges, issue list, download button).  
  - Promote a dedicated `/imports/wizard` route with `SmartImportWizard`, `MappingStep`, `RuleToggleStep`, and `SummaryStep` components so operators can adjust mappings before running `refine`.  
  - Reuse the new hooks above for both the quick preview and the multi-step wizard; surface “Attach profile to run” + “Save as template” affordances.

- **Persistence strategy**  
  - Persist profiling payloads under `.hotpass/ui/import-profiles/` via `server/storage.js` helpers for quick recall.  
  - When an import job kicks off, copy the selected payload into `dist/import/<job-id>/profile.json` and include a download link in job metadata.  
  - Optional future enhancement: add `GET /api/imports/profile/:id` to retrieve archived payloads without hitting disk directly.

- **Template/API gaps**  
  - Server needs `/api/imports/templates` CRUD endpoints (list, create/update, delete) plus storage helpers (likely `.hotpass/ui/templates/`).  
  - Assistant + CLI tooling should consume the same endpoints to keep template discovery consistent.  
  - UI work (TemplatePicker, TemplateManagerDrawer, ConsolidationPreview) is blocked on these APIs; sequence backend before the wizard steps.

- **Current scaffolding (2025-11-03)**  
  - Client module `importsApi` now exposes `profileWorkbook`, stored profile CRUD, and template CRUD plus React Query hooks (`useImportProfileMutation`, `useStoredImportProfiles`, `useImportTemplates`, `useImportTemplateUpsert`, `useImportTemplateDelete`).  
  - Express server stubs `/api/imports/profiles` (GET/POST/DELETE) and `/api/imports/templates` (GET/POST/PUT/DELETE) backed by new storage helpers in `server/storage.js`.  
  - Stored assets live under `.hotpass/ui/imports/{profiles,templates}/<id>.json`; templates enforce name + payload validation and dedupe tags.

- **Recommended execution order**  
  1. ✅ Wire `DatasetImportPanel` to `useImportProfileMutation`, render an `ImportProfilePreview`, and expose download/attach actions (2025-11-03).  
  2. When an import run starts, persist the chosen profile metadata alongside the job (`dist/import/<job-id>/profile.json`) and surface the artifact link in job events.  
  3. Stand up the `/imports/wizard` route with step components (Upload → Profile → Mapping → Rules → Summary) reusing stored profiles/templates.  
  4. Layer on template UI (`TemplatePicker`, `TemplateManagerDrawer`) plus CLI export support.  
  5. Finish consolidation preview + assistant surfacing once wizard + template flows are stable.
