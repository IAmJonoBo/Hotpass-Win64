# Hotpass Agent Runbook (E2E)

**Version:** 1.1
**Date:**
**Audience:** GitHub Copilot CLI / Copilot Agent HQ / Codex (with MCP)
**Goal:** upgrade Hotpass so agents can, from natural language, refine a spreadsheet, enrich or double-check a row, and enforce data-quality gates — all through one CLI and one MCP surface.
**Supersedes:** `UPGRADE_B.md` and `GAP_ANALYSIS_30_10_25.md`; this runbook is now the canonical plan.

---

## 0. Executive Summary

- **Completed**
  - CLI & MCP parity is live: the new command set ships under `apps/data-platform/hotpass/cli/commands/` and the stdio server in `apps/data-platform/hotpass/mcp/server.py` exposes `hotpass.refine`, `hotpass.enrich`, `hotpass.qa`, `hotpass.explain_provenance`, `hotpass.crawl` (guarded), and `hotpass.ta.check`.
  - Quality gates QG‑1 → QG‑5 now run end-to-end via `ops/quality/run_qg*.py`, `ops/quality/run_all_gates.py`, and the GitHub workflow `.github/workflows/quality-gates.yml`.
  - Supply-chain automation publishes SBOM, provenance, and checksums directly from `.github/workflows/process-data.yml`, backed by `ops/supply_chain/` utilities.
  - Adaptive research orchestrator shipped under `apps/data-platform/hotpass/research/`, with CLI verbs (`plan research`, `crawl`) and MCP tools (`hotpass.plan.research`, `hotpass.crawl`) wiring deterministic-first planning into agent workflows.
- **In progress**
  - Docs navigation uplift and long-tail telemetry/performance benchmarking remain open (Sprint 4 follow-ons).
  - Streamlit UI/export backlog (Sprint 7) scheduled post-orchestrator GA.
- Profile-first linkage improvements still need additional coverage; the `expect()` helper is now adopted across compliance/enrichment suites with 32 legacy `assert` usages remaining elsewhere.
- **Blockers / dependencies**
  - Staging access is still required to capture live Marquez lineage evidence and ARC runner smoke logs.
  - Docker buildx cache reuse work has not begun; pipeline cost reductions remain blocked pending that PR.
- Adaptive research enhancements depend on tightening provider-specific automation before enabling network defaults at scale; rate-limit scaffolding now exists per profile, and human-in-the-loop controls remain outstanding.

---

## 1. Implementation Status Dashboard

### 1.1 Next Steps alignment (tasks)

| Item                                                                 | Due | Owner            | Status             | Evidence / Notes                                                                                                                                                                                       |
| -------------------------------------------------------------------- | --- | ---------------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Confirm Phase 5 T5.5 completion against programme expectations       |     | Programme        | Pending sign-off   | Roadmap milestone is marked complete, but stakeholder confirmation is outstanding (`ROADMAP.md`).                                                                                                      |
| Execute full E2E runs with canonical configuration toggles           |     | QA               | Open               | Requires running `uv run hotpass overview/refine/enrich/qa` with `hotpass-e2e-staging`; no artefact recorded yet.                                                                                      |
| Validate Prefect backfill deployment guardrails in staging           |     | Platform         | In progress        | Prefect manifests exist (`prefect/backfill.yaml`, `prefect/refinement.yaml`); staging validation still pending.                                                                                        |
| Benchmark `HotpassConfig.merge` on large payloads                    |     | Engineering      | Not started        | No benchmark harness or artefact committed.                                                                                                                                                            |
| Extend orchestrate/resolve CLI coverage for advanced profiles        |     | Engineering & QA | In progress        | Resolve command exists (`apps/data-platform/hotpass/cli/commands/resolve.py`), but advanced profile fixtures/tests remain to be authored.                                                              |
| Merge Prefect deployment manifests and validate idempotent schedules |     | Platform         | Complete           | Manifests landed (`prefect/backfill.yaml`, `prefect/refinement.yaml`) and CLI deployment tests cover overrides (`tests/cli/test_deploy_command.py`).                                                   |
| Exercise OpenLineage + Marquez hardening follow-up                   |     | Engineering & QA | Blocked on staging | Compose stack and tests ready (`tests/infrastructure/test_marquez_stack.py`, `tests/test_lineage.py`); waiting for staging lineage smoke.                                                              |
| Harden uv-based CI quality gates                                     |     | Platform         | Complete           | Gate scripts orchestrated in `ops/quality/run_qg*.py`; workflow `.github/workflows/quality-gates.yml` enforces them.                                                                                   |
| Ship CodeQL + secrets scanning                                       |     | Security         | Complete           | Workflows `.github/workflows/codeql.yml` and `.github/workflows/secret-scanning.yml` active; SARIF uploads configured.                                                                                 |
| Enable Docker buildx cache reuse                                     |     | Platform         | Not started        | No `ci/docker-cache` workflow yet; caching remains manual.                                                                                                                                             |
| Publish SBOM + SLSA attestations                                     |     | Platform         | Complete           | `.github/workflows/process-data.yml` `supply-chain` job runs `ops/supply_chain/generate_sbom.py` / `generate_provenance.py` and uploads artefacts.                                                     |
| Complete ARC runner rollout and OIDC wiring                          |     | Platform         | In progress        | ARC manifests and smoke workflow exist (`infra/arc/runner-scale-set.yaml`, `.github/workflows/arc-ephemeral-runner.yml`, `ops/arc/verify_runner_lifecycle.py`); live staging rehearsal pending access. |
| Finalise OpenTelemetry exporter propagation                          |     | Engineering      | Complete           | Telemetry bootstrap integrated in CLI (`apps/data-platform/hotpass/cli/shared.py`, `apps/data-platform/hotpass/cli/commands/run.py`, `apps/data-platform/hotpass/telemetry/bootstrap.py`).             |
| Finish Diátaxis navigation uplift follow-on                          |     | Docs & UX        | In progress        | Navigation doc merged (`docs/governance/data-governance-navigation.md`) and surfaced via `docs/index.md`; follow-on UX review scheduled.                                                               |
| Release `cli/doctor` + `cli/init` onboarding refinements             |     | Engineering & UX | Complete           | Commands and docs shipped (`apps/data-platform/hotpass/cli/commands/doctor.py`, `docs/reference/cli.md`).                                                                                              |

### 1.2 Next Steps — hygiene, steps, and deliverables

- **PR hygiene reminder** — ongoing rolling reminder. Continue updating `Next_Steps.md` after each PR hand-off.
- **Manifest-driven Prefect deployments** — manifests are committed; remaining work is staging validation plus doc update in `docs/how-to-guides/prefect-manifests.md` (todo).
- **Marquez lineage smoke scheduling** — blocked until optional dependencies land on staging; track via `tests/infrastructure/test_marquez_stack.py` and staging access ticket.
- **Assertion migration** — partially complete; 36 suites still contain bare `assert` (e.g. `tests/test_evidence.py`).
- **Telemetry/mypy audit** — remediation plan (Hypothesis wrappers → optional-dependency stubs → CLI/MCP typing → long-tail cleanup) completed; `uv run mypy src tests scripts` (2025-10-31) now reports 0 errors (baseline archived at `dist/quality-gates/baselines/mypy-baseline-2025-10-31.txt`).【F:Next_Steps.md†L20-L48】【F:tests/helpers/stubs.py†L1-L170】

### Deliverable status\*\*

- **Marquez lineage smoke evidence** — instrumentation and automated checks exist, but live evidence (logs/screenshots) still outstanding pending staging access.

### Quality gate status

- **QG‑1 (CLI integrity)** — ✅ Passing via `ops/quality/run_qg1.py` and workflow job.
- **QG‑2 (Data quality)** — ✅ Passing locally/CI; outputs archived under `dist/quality-gates/qg2-data-quality`.
- **QG‑3 (Enrichment chain)** — ✅ Passing using deterministic fixtures in `tests/cli/test_quality_gates.py::TestQG3EnrichmentChain`.
- **QG‑4 (MCP discoverability)** — ✅ Passing; MCP server exposes tool list via stdio and gate script asserts presence.
- **QG‑5 (Docs/instructions)** — ✅ Passing; instructions verified by gate script and CI job.

### 1.3 Gap closure tracker (from 30 Oct audit)

| Gap                                     | Status                   | Evidence                                                                                                                                                                                                      | Next action                                                                                               |
| --------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| QG‑2 only performed schema checks       | Resolved                 | `ops/quality/run_qg2.py` runs full GE checkpoints; uploads in `.github/workflows/quality-gates.yml`.                                                                                                          | Monitor GE dependency availability; ensure sample workbooks stay in `data/`.                              |
| Sprint 5 automation stubs               | Resolved with follow-ups | Gate scripts and MCP `hotpass.ta.check` implemented (`ops/quality/run_qg*.py`, `apps/data-platform/hotpass/mcp/server.py`); integration tests cover research & TA tools (`tests/mcp/test_research_tools.py`). | Publish TA analytics dashboards/aggregations from persisted JSON artefact.                                |
| Documentation misalignment              | Resolved                 | CLI reference refreshed (`docs/reference/cli.md`), instructions mention core verbs in `.github/copilot-instructions.md` & `AGENTS.md`.                                                                        | Extend reference set with MCP/quality gate pages.                                                         |
| Research APIs promised but not exposed  | Resolved                 | Adaptive research orchestrator + CLI (`hotpass plan research`, `hotpass crawl`) and MCP tools (`hotpass.plan.research`, `hotpass.crawl`) ship from `apps/data-platform/hotpass/research/orchestrator.py`.     | Integration regression tests cover CLI + MCP tooling; monitor staging rehearsals for additional evidence. |
| Assert-free pytest migration incomplete | Outstanding              | Bare asserts present (e.g. `tests/test_evidence.py`).                                                                                                                                                         | Continue migrating to shared `expect()` helper per `docs/how-to-guides/assert-free-pytest.md`.            |
| Next Steps backlog alignment            | Ongoing                  | This dashboard now mirrors outstanding work; maintain weekly review cadence.                                                                                                                                  | Update `Next_Steps.md` & this section after each closure.                                                 |

### 1.4 Strategic enhancements (from `UPGRADE_B.md`)

| Enhancement                                                                                   | Status                 | Notes                                                                                                                         |
| --------------------------------------------------------------------------------------------- | ---------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Research-first positioning across docs/README                                                 | In progress            | README/landing copy still emphasises refinement over research; update messaging once orchestrator lands.                      |
| Adaptive research orchestrator module (`apps/data-platform/hotpass/research/orchestrator.py`) | Delivered              | Planner orchestrates local snapshots, deterministic enrichment, native crawl metadata, and backfill recommendations.          |
| Relationship & identity mapping (Splink, graph view)                                          | Partially delivered    | Linkage module active (`apps/data-platform/hotpass/linkage/`); need profile-driven graph export and UI hooks.                 |
| Agent-native research planning tools (`hotpass.plan.research`, MCP hooks, audit log)          | Delivered (follow-ups) | CLI + MCP tools live; expand audit analytics and add integration tests.                                                       |
| Live spreadsheet UI with provenance badges                                                    | Not started            | Streamlit dashboard exists in legacy branch only; no AG Grid / Handsontable integration here.                                 |
| CLI export formats (`--export xlsx,csv,pipe`)                                                 | Not started            | CLI presently writes XLSX/CSV explicitly; expose shared export flag and docs.                                                 |
| Frontier-grade guarantees (single system, adaptive research, provenance, human-in-loop)       | Dependent              | Achieved partially through CLI+MCP parity and quality gates; full guarantee requires orchestrator, UI, and audit hooks above. |

---

## 2. Sprint Plan (phased roadmap)

### Sprint 1 – CLI & MCP parity (**Status: ✅ Complete**)

- Exposed required CLI verbs under `apps/data-platform/hotpass/cli/commands/` and ensured `uv run hotpass overview/refine/enrich/qa/contracts` share a consistent parser.
- Implemented MCP stdio server (`apps/data-platform/hotpass/mcp/server.py`) registering `hotpass.refine`, `hotpass.enrich`, `hotpass.qa`, `hotpass.crawl` (guarded), `hotpass.explain_provenance`, and `hotpass.ta.check`.
- Repo instructions updated (`.github/copilot-instructions.md`, `AGENTS.md`) to describe CLI + MCP usage.
- **Quality gate:** `uv run hotpass overview` (QG‑1) enforced in CI.

### Sprint 2 – Enrichment translation (**Status: ✅ Complete, monitor placeholders**)

- Introduced deterministic and research fetchers under `apps/data-platform/hotpass/enrichment/fetchers/` with environment guardrails in `research.py`.
- `apps/data-platform/hotpass/enrichment/pipeline.py` orchestrates deterministic-first enrichment with provenance tracking (`provenance.py`).
- CLI `hotpass enrich` implements `--allow-network` toggle aligned with env flags.
- **Quality gate:** `uv run hotpass enrich --allow-network=false` run in QG‑3; research fetchers currently contain placeholder API integrations.

### Sprint 3 – Profiles & compliance unification (**Status: ✅ Complete**)

- Profile linter (`tools/profile_lint.py`) validates ingest/refine/enrich/compliance blocks.
- JSON/Schema outputs (`tools/profile_lint.py --json/--schema-json`) power QG summaries and contributor tooling, guarded by `tests/profiles/test_profile_lint_cli.py`.
- Contract tests and Great Expectations suites validate active profiles.
- Advanced resolve coverage added via `tests/cli/test_resolve_profile.py`, ensuring profile-driven Splink defaults and sensitive-field redaction are exercised end-to-end.

### Sprint 4 – Docs & agent UX (**Status: ✅ Complete with follow-ons**)

- Docs refreshed (`docs/reference/cli.md`, `.github/copilot-instructions.md`, `AGENTS.md`) and MCP instructions included.
- Additional work planned: navigation uplift QA and agent walkthrough updates tied to adaptive research features.

### Sprint 5 – Technical Acceptance automation (**Status: ✅ Complete with follow-ons**)

- Gate scripts and `hotpass qa ta` delegate to `ops/quality/run_all_gates.py`.
- MCP `hotpass.ta.check` calls the consolidated runner.
- TA runs now persist `dist/quality-gates/latest-ta.json` and append to `dist/quality-gates/history.ndjson` (written by `hotpass qa ta` / `ops/quality/run_all_gates.py`) so the latest gate summary and history are easy to reference post-run.
- `ops/quality/ta_history_report.py` produces pass-rate analytics from the persisted history; MCP regression tests now cover research planning, crawl, rate-limit propagation, and TA summaries (`tests/mcp/test_research_tools.py`).
- Follow-on: optionally surface TA analytics in dashboards/telemetry (data pipeline now captured locally).

### Sprint 6 – Adaptive research orchestrator (**Status: ✅ Complete with follow-ons**)

- `apps/data-platform/hotpass/research/orchestrator.py` now implements the adaptive loop (local snapshot → authority check → deterministic enrichment → optional network enrichment → native crawl/backfill planning). CLI (`plan research`, `crawl`) and MCP tools (`hotpass.plan.research`, `hotpass.crawl`) wrap the planner, emitting audit entries to `./.hotpass/mcp-audit.log`.
- Profile schema adds `authority_sources` and `research_backfill` so planners understand trusted registries and backfillable fields; agent docs cover the new flags.
- Profile-driven throttling (`research_rate_limit` min interval + optional burst) keeps network fetchers within provider limits, and each native crawl stores metadata snapshots under `.hotpass/research_runs/<entity>/crawl/` alongside the run summary.
- MCP + CLI integration tests cover research planning, crawl, rate limits, and artefact persistence; provider guardrail guidance now ships in `docs/reference/profiles.md` and `AGENTS.md` (future follow-on: per-provider automation & staging rehearsals).

### Sprint 7 – Agent-first UI & exports (**Status: 🚧 Planned**)

- Embed Streamlit dashboard with AG Grid / Handsontable status matrix, provenance badges, and re-run controls.
- Require human approval for low-confidence merges and network escalation.
- Surface multi-format exports via shared `--export` flag; extend docs and tests.

---

## 3. CLI & MCP Contract

Hotpass must keep the CLI surface predictable and short-form to suit Copilot/Codex planners.

### 3.1 Canonical CLI verbs

```markdown
uv run hotpass overview
uv run hotpass refine --input-dir ./data --output-path ./dist/refined.xlsx --profile <profile> --archive
uv run hotpass enrich --input ./dist/refined.xlsx --output ./dist/enriched.xlsx --profile <profile> --allow-network=<true|false>
uv run hotpass qa <target>
uv run hotpass contracts emit --profile <profile>
uv run hotpass explain-provenance --dataset ./dist/enriched.xlsx --row-id 0 --json
```

- `overview` lists available commands, profiles, and quick start hints.
- `refine` runs deterministic cleaning using the selected profile.
- `enrich` performs deterministic-first enrichment, promoting network fetchers only when `--allow-network=true` and environment flags permit.
- `qa` targets (`all`, `cli`, `contracts`, `docs`, `profiles`, `fitness`, `data-quality`, `ta`) and delegates to gate scripts.
- `contracts emit` regenerates governed schemas for downstream consumers.
- `explain-provenance` surfaces provenance metadata for a specific row, returning JSON when the `--json` flag is supplied (status `2` when provenance columns are absent).

### 3.2 MCP tooling requirements

Expose the same capabilities via MCP stdio:

| Tool                         | Purpose                            | Notes                                                                                   |
| ---------------------------- | ---------------------------------- | --------------------------------------------------------------------------------------- |
| `hotpass.refine`             | Shells to CLI refine               | Accepts `input_path`, `output_path`, `profile`, `archive`.                              |
| `hotpass.enrich`             | Shells to CLI enrich               | Honors `allow_network` and env guardrails.                                              |
| `hotpass.qa`                 | Runs `hotpass qa <target>`         | Default `target="all"`.                                                                 |
| `hotpass.crawl`              | Executes research orchestrator     | Runs adaptive crawl with profile-driven throttling; still guarded behind feature flags. |
| `hotpass.explain_provenance` | Reads provenance columns for a row | Works on XLSX outputs with provenance fields.                                           |
| `hotpass.ta.check`           | Runs consolidated quality gates    | Optional `gate` argument filters to a specific gate.                                    |

Ensure `tools/list` returns the full tool set and that the server logs tool invocations (future: write to `./.hotpass/mcp-audit.log` once implemented).

---

## 4. Adaptive Research Orchestrator (status & follow-ups)

The adaptive planner in `apps/data-platform/hotpass/research/orchestrator.py` now runs end-to-end:

1. **Local & authority pass** — reuses refined artefacts plus cached authority snapshots per profile (`authority_sources`), recording outcomes in the audit log.
2. **OSS-first extraction** — executes deterministic enrichment before any network escalation, capturing provenance metadata.
3. **Native crawl** — performs guarded network requests (or Scrapy crawls when available) with profile-driven throttling, persisting crawl artefacts under `.hotpass/research_runs/<entity>/crawl/`.
4. **Backfill planning** — enumerates approved backfill fields and surfaces them in step artefacts.
5. **Stop condition** — returns a structured outcome payload for CLI, MCP, and MCP tooling consumers.

Follow-ups:

- Add CLI + MCP integration tests that assert artefact locations, rate-limit behaviour, and audit logging.
- Expand provider-specific guardrails (per-domain throttles, human-in-the-loop approvals) before enabling network defaults at scale.
- Surface crawl artefact catalogues and provenance rollups in agent-facing docs/dashboards.

---

## 5. Relationship & Identity Mapping

Existing linkage tooling (`apps/data-platform/hotpass/linkage/`) provides Splink + RapidFuzz matching with Label Studio integration.

Focus areas:

- Integrate linkage results into enrichment provenance and orchestrator decisions.
- Extend profiles with identity configuration (e.g. `identity.match_on`, `identity.resolver`, `identity.backfill_from_related`).
- Surface graph exports or review artefacts via CLI (`hotpass resolve --export-graph`) and Streamlit UI.
- Ensure Label Studio connector records reviewer decisions and merges them back into datasets.

---

## 6. Agent UX, UI, and Human-in-the-loop

Planned enhancements:

- Streamlit dashboard upgrade with AG Grid/Handsontable for live status:
  - Colour legend: pending (grey), refined (green), enriched deterministic (blue), enriched network (orange), backfilled low confidence (red).
  - Buttons to rerun adaptive research with expanded budget.
  - Inline warnings for crawler rate limits and provenance anomalies.
- Approval workflow:
  - Require human approval for low-confidence merges, enabling network fetchers, and probabilistic matches below configurable Splink threshold.
  - Record approvals in audit log for compliance review.

---

## 7. Data Quality Gates & Automation

Quality gates guard every stage:

| Gate                     | Command                  | Pass criteria                                                                           | Artefact                                                                     |
| ------------------------ | ------------------------ | --------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| QG‑1 CLI integrity       | `ops/quality/run_qg1.py` | CLI verbs present, help text works                                                      | Summary JSON under `dist/quality-gates/qg1-cli-integrity`.                   |
| QG‑2 Data quality        | `ops/quality/run_qg2.py` | GE checkpoints succeed; Data Docs generated                                             | Data Docs archived under `dist/quality-gates/qg2-data-quality/<timestamp>/`. |
| QG‑3 Enrichment chain    | `ops/quality/run_qg3.py` | Deterministic enrichment produces output with provenance; network skipped when disabled | Test fixtures under `tests/data/`.                                           |
| QG‑4 MCP discoverability | `ops/quality/run_qg4.py` | MCP server lists required tools                                                         | JSON summary from gate script.                                               |
| QG‑5 Docs/instructions   | `ops/quality/run_qg5.py` | Instruction files present and contain key phrases                                       | Summary JSON plus optional markdown excerpts.                                |

Use `ops/quality/run_all_gates.py --json` for consolidated runs (called by `hotpass qa ta` and MCP `hotpass.ta.check`). Ensure workflow artefacts remain accessible for audits.

---

## 8. Technical Acceptance Criteria

TA is achieved when:

1. **Single-tool rule** — All user-facing operations route through `uv run hotpass ...` or MCP equivalents (validated via QG‑1/QG‑4).
2. **Profile completeness** — Every profile includes ingest/refine/enrich/compliance blocks validated by `tools/profile_lint.py` and QG‑2.
3. **Offline-first enrichment** — `hotpass enrich --allow-network=false` succeeds with provenance showing network disabled.
4. **Network safety** — Respect `FEATURE_ENABLE_REMOTE_RESEARCH` and `ALLOW_NETWORK_RESEARCH`; provenance notes when network skipped.
5. **MCP parity** — All CLI verbs exposed via MCP and listed in `tools/list`.
6. **Quality gates wired** — QG‑1 → QG‑5 runnable locally and in CI, with artefacts uploaded.
7. **Docs ready** — `.github/copilot-instructions.md` and `AGENTS.md` emphasise profile-first, deterministic-first, provenance.

Failing any TA item should block releases until scripts/docs/tests are corrected and gates rerun.

---

## 9. Research, Investigation, and Backfilling Mode

Agents must support both local and remote research pipelines:

1. **Authority-first search** — Profiles declare preferred registries/directories; orchestrator hits them before web.
2. **Deterministic enrichments** — Use local lookup tables, historical archives, and derived fields (already implemented via deterministic fetchers).
3. **Adaptive research (planned)** — Once orchestrator lands, promote network crawlers only when flags permit and budgets allow.
4. **Backfill control** — Only mutate fields the profile marks as backfillable; preserve originals and record provenance with strategy/backfill confidence.
5. **Entity resolution loop** — Re-run linkage when enrichment introduces conflicting data; integrate Splink results and reviewer decisions.

Post-research, rerun `uv run hotpass qa all` and invoke `hotpass.explain_provenance` to keep the audit trail complete.

---

## 10. Search Strategies & Source Prioritisation

1. **Authority sources first** — Regulator, government, or profile-declared authority endpoints.
2. **Focused Hotpass research search** — (Planned) `hotpass.plan.research` and future `hotpass.research.search` should query provider APIs with temporal filters.
3. **Temporal filtering** — Restrict to recent results for volatile data (past day/week/month).
4. **Structural crawl** — Use deterministic crawler or orchestrator step to map unknown site structures within rate limits.
5. **Exhaustive sweep** — Broader web search only when higher authority sources fail; emit warnings when using general web data.

Always validate results via GE expectations and provenance metadata.

---

## 11. Threat Model & Hardening

- Restrict MCP tool exposure to Hotpass plus required GitHub defaults; avoid enabling unrelated tools.
- Require explicit user approval for filesystem/network actions (aligned with Copilot CLI security posture).
- Implement prompt-injection guardrails: detect instructions that attempt to disable validation or leak secrets; log and abort.
- Log MCP tool calls (planned path: `./.hotpass/mcp-audit.log`) with timestamps, arguments, and outcomes for compliance.
- Honour environment-controlled network toggles; never fetch remote data when disabled.
- On Windows deployments, keep MCP server bound to stdio/local named pipe and rely on OS prompts for consent.

---

## 12. OSS-first Extractors & Fallbacks

Maintain vendor-neutral extraction defaults:

- HTML → text: prefer `trafilatura` or `readability-lxml`.
- JS-heavy: render with Playwright headless (possibly via `scrapy-playwright`).
- Bulk/domain jobs: schedule focused crawls with Scrapy/Crawlee; store raw HTML/JSONL under `./.hotpass/cache/`.
- Documents/PDF: convert using `unstructured` or `pdfplumber` before enrichment.
- Data quality expansion: integrate Soda Core or whylogs alongside Great Expectations if additional drift checks are required.

Only escalate to third-party/vendor APIs after OSS paths fail or when profiles explicitly opt in.

---

This runbook is the single source of truth for Hotpass upgrades. Update it whenever tasks close (alongside `Next_Steps.md`, `ROADMAP.md`, and `IMPLEMENTATION_PLAN.md`) and archive superseded artefacts rather than letting parallel plans drift.
