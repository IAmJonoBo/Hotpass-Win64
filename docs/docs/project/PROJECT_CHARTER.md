# Project Charter

**Working title:** Hotpass Modernisation & Orchestration Programme
**Problem worth solving:** Align data refinement, enrichment, and governance workflows behind a single CLI/MCP surface with automated quality gates, staged evidence, and observable operations.
**Success criteria (measurable):**

1. `uv run mypy src tests scripts` and `uv run pytest -q` stay green with ≤5 residual suppressed errors (current: 0).
2. All quality gates (QG‑1→QG‑5) and bench harnesses (`ops/benchmarks/hotpass_config_merge.py`) run in CI preflight.
3. Staging rehearsals (Prefect backfill guardrails, ARC lifecycle, full E2E replay) produce artefacts under `dist/staging/` before release sign‑off.
4. Docs follow the Diátaxis shape with runbooks for backfills, research enrichment, and staging rehearsals.
5. Telemetry/lineage evidence captured for each release window (Prefect, Marquez, OTLP traces).
   **Non‑negotiables:** POPIA compliance, reproducible pipelines, GitOps-managed flows, zero unaudited secrets, cost guardrails for runners and OTLP ingestion.

## Scope (what’s in / out)

- **In:** Unified CLI/MCP parity, Prefect deployment manifests, adaptive research orchestration, entity-resolution linkage, Docs/Diátaxis uplift, benchmark + QA automation, staging rehearsal artefacts.
- **Out:** Net-new UI surfaces (beyond Streamlit dashboard polish), third-party provider onboarding without approved contracts, real-time sync engines, bespoke analytics dashboards, non-POPIA compliance frameworks.

## Stakeholders & RACI

- **Product/Programme (Accountable):** Programme Manager — sets roadmap, approves staging evidence.
- **Engineering (Responsible):** Platform & Data Engineering squads — deliver CLI, pipelines, docs, and automation.
- **Design/Docs (Consulted):** Developer Experience writer, UX steward for docs navigation.
- **AI/ML (Consulted):** Enrichment SMEs ensuring deterministic-first policies persist as research features grow.
- **QA/Ops (Responsible):** QA lead & Site Reliability partner — operate Prefect workers, capture staging artefacts.
- **Security & Compliance (Informed):** Security engineer, POPIA compliance officer tracking governance evidence.

## Risks & Assumptions

- **Big rocks:**
  - Staging access gaps delaying backfill guardrail rehearsals.
  - Provider throttling or key rotation impacting research enrichment defaults.
  - Prefect worker parity drifting between CI, staging, and production environments.
  - Docs uplift falling behind feature velocity, leaving contributors without authoritative how‑tos.
- **Unknowns to spike:**
  - Load impact of large acquisition/intent payloads (tracked via merge benchmark harness).
  - Rate-limit policies for planned research providers when network access is enabled by default.
  - Streamlit dashboard hardening for accessibility before Sprint 7.

> Keep this punchy. If it can’t fit on two pages, you’re writing a novel.
