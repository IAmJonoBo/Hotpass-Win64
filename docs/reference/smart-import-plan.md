---
title: Reference — Smart Import plan
summary: Delivery tracker, data flow, and dependency map for the Smart Import experience across API, CLI, and UI surfaces.
last_updated: 2025-11-18
---

# Smart Import plan

## Delivery status

| Stage                                                                 | Status           | Notes                                                                                                     |
| --------------------------------------------------------------------- | ---------------- | --------------------------------------------------------------------------------------------------------- |
| Profiling service (`hotpass imports profile`, `/api/imports/profile`) | ✅               | Emits sheet summaries, column heuristics, role/join key hints, and issue catalogues.                      |
| Preprocessing engine (`import_mappings`, `import_rules`)              | ✅ (phase 1)     | Rename/normalise/date/drop rules wired into the pipeline with profile overlays.                           |
| Sheet role classification & join hints                                | ✅               | Profiler exposes `role` and `join_keys` per sheet for auto-mapping.                                       |
| Default import templates                                              | ✅               | `profiles/generic/imports/default.json` seeds base rules and plays nicely with profile-specific overlays. |
| Advanced rule library                                                 | ✅ (initial set) | Layout pruning, canonical date parsing, and standard normalisers available for reuse.                     |
| Consolidation / relational export                                     | ⏳               | Outstanding entity/contact/address joins and Parquet bundle exports.                                      |
| Wizard UI (mapping editor, rule toggles, preview)                     | ⏳               | Backend ready; front-end polish and consolidation preview finishing.                                      |
| Template service (list/save/delete)                                   | ✅               | REST endpoints (`/api/imports/templates`) and storage helpers ship with CLI + assistant support.          |
| Assistant integration                                                 | ✅ (phase 1)     | Assistant tools cover template summary, contract export, and telemetry.                                   |
| QA/HIL alignment                                                      | ⏳               | Need surfaced auto-fixes & unresolved issues in HIL and observability dashboards.                         |

## End-to-end data flow

```{mermaid}
flowchart LR
    subgraph Sources
        Workbook[Spreadsheet workbook]
        Template[Template selection]
    end

    subgraph Profiling
        ProfileSvc[Profile service\n`/api/imports/profile`]
        RulesStore[Template storage\n`.hotpass/ui/imports/templates/`]
    end

    subgraph Pipeline
        Mapper[Mapping engine\n`import_mappings`]
        RuleEngine[Rule library\n`import_rules`]
        Consolidator[Consolidation helpers]
    end

    subgraph Outputs
        JobArtifacts[`dist/import/<job-id>/`]
        Contracts[`dist/contracts/`]
        Dashboard[Streamlit dashboard]
    end

    Workbook --> ProfileSvc
    Template --> RulesStore
    ProfileSvc --> Mapper
    RulesStore --> Mapper
    Mapper --> RuleEngine
    RuleEngine --> Consolidator
    Consolidator --> JobArtifacts
    Consolidator --> Dashboard
    JobArtifacts --> Contracts
```

The flow shows how operators choose a template, run profiling, review rule impacts, and persist a consolidated dataset alongside
contracts and dashboards.

## Dependency map

| Layer                | Components                                                                                          | Notes                                                                                                                     |
| -------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **Backend**          | `apps/data-platform/hotpass/imports/`, `/api/imports/profile`, `/api/imports/templates`             | Python services expose profiling, rule evaluation, and template persistence; results stored under `.hotpass/ui/imports/`. |
| **CLI & assistants** | `hotpass refine --import-template`, `hotpass plan import`, MCP tools `hotpass.imports.*`            | Consumers can trigger runs with a template, preview issues, and surface contracts inside chat-based workflows.            |
| **Web UI**           | `apps/web-ui/src/api/imports.ts`, `SmartImportWizard`, `TemplateManagerDrawer`                      | React Query hooks and wizard screens orchestrate uploads, mapping tweaks, and result summaries.                           |
| **Persistence**      | `.hotpass/ui/imports/{profiles,templates}/`, `dist/import/<job-id>/profile.json`, `dist/contracts/` | Profiles and templates cached locally; job artefacts stored alongside run metadata for download and auditing.             |
| **Telemetry**        | `ops/telemetry`, dashboards, SSE streams                                                            | Import issue logs and status updates feed the Streamlit dashboard and HIL tooling.                                        |

## Pipeline narrative

1. **Profile** — operator uploads a workbook (or points to a stored file). The profiling service analyses sheet structure,
   generates role/join key hints, and records issues.
2. **Review mappings** — default templates plus profile overlays populate the wizard. Operators confirm or adjust column mapping,
   rename rules, and layout filters.
3. **Queue run** — the wizard or CLI submits a pipeline run with the selected template, optionally attaching the profiling payload
   for provenance.
4. **Execute rules** — the pipeline applies mapping/rule stages, tracking autofixes, drops, and outstanding manual work.
5. **Consolidate & export** — once consolidation helpers land, the pipeline will emit tidy entity/contact/address tables alongside
   Parquet bundles while maintaining the Excel outputs.
6. **Surface results** — dashboards render live SSE logs, issue summaries, and download links (`dist/import/<job-id>/profile.json`).
7. **Governance** — contracts and manifests drop into `dist/contracts/` so data governance tooling can track import provenance.

## Operational readiness checklist

### Backend

- [x] DatasetImportPanel wired to `useImportProfileMutation` with download and attach actions.
- [x] Import runs persist profile metadata alongside job outputs.
- [x] `/imports/wizard` route delivers Upload → Profile → Mapping → Rules → Summary steps.
- [x] Template management UI exposes CRUD flows, matching CLI and assistant tooling.
- [ ] Batch contract automation, diff manifests, and governance dashboards consuming consolidation telemetry.

### Assistant & CLI

- [x] CLI and assistants share template CRUD helpers (see `apps/web-ui/src/agent/tools.ts`).
- [ ] Add assistant pre-flight checks that preview suggested fixes and require explicit confirmation before applying.
- [ ] Extend `hotpass refine` with richer `--import-template` ergonomics once consolidation ships.

### QA & governance

- [ ] Emit structured import issue logs via SSE/telemetry for dashboards & HIL.
- [ ] Surface auto-fixes and unresolved issues within the HIL panel for approvals.
- [ ] Keep defaults industry-agnostic; ensure profile-specific overlays remain optional.

Track these backlog items in the operations board; once checked off, promote the Smart Import wizard from beta to general
availability.
