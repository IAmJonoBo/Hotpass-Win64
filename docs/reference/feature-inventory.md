# Hotpass Feature Inventory — 2025-11-03 Snapshot

| Area | Requirement | Status | Notes |
| --- | --- | --- | --- |
| Backend | Job runner smoke tests | ⚠️ Pending | Add Vitest coverage for `server/job-runner.js` (Stage 1 follow-up). |
| Backend | `GET /api/runs/:id/logs` SSE | ✅ | Streams job logs with keep-alives and graceful teardown. |
| Backend | Contracts directory listing | ✅ | `/api/contracts` enumerates `dist/contracts`, download endpoint provided. |
| Frontend | Dashboard inline help anchors | ✅ | Import, contracts, and lineage cards launch topic-specific help. |
| Frontend | Run Details real-time logs | ✅ | SSE stream with highlight effect and assistant deep link. |
| Frontend | Run Details QA viewer | ⚠️ Missing | Needs embedded docs from `dist/data-docs`. |
| Frontend | Action buttons (Re-run, Enrich, Plan research, Explain provenance) | ✅ | Buttons trigger assistant commands prefilled with run context. |
| Frontend | Planner tab (`plan research`) | ⚠️ Not started | Stage 3.3 requirement. |
| CLI | Contracts helper | ✅ | Assistant tools export/publish via `/api/imports/templates/:id/contracts`. |
| CLI | `plan research` automation | ⚠️ Pending UI integration | CLI tool exists; UI needs planner tab. |
| QA | Unit tests for import widgets | ⚠️ Partial | `CellSpotlight` parsing covered; add `LiveProcessingWidget` metrics test. |
| QA | Playwright scenarios (Stage 7) | ⚠️ Not started | Documented in WEBUI backlog. |
| Docs | Environment variables | ✅ | README details `HOTPASS_IMPORT_ROOT`/`HOTPASS_CONTRACT_ROOT`; help wiring captured in IMPLEMENTATION_SUMMARY. |
| Docs | CHANGELOG/update version | ⚠️ Pending | Once new features stabilise. |
