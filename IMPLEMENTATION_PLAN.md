# Hotpass Implementation Plan

**Version:** 1.1
**Last Updated:** 2025-11-15
**Status:** Active
**Aligned with:** UPGRADE.md, Next_Steps.md, ROADMAP.md

## Executive Summary

This implementation plan provides a comprehensive breakdown of development sprints, quality gates, and deliverables for the Hotpass data refinement platform. It serves as the operational blueprint for delivering a production-ready system that transforms messy spreadsheets into governed, analysis-ready workbooks.

**Current Status:**
- CLI & MCP parity: ✅ Complete
- Quality gates (QG-1 → QG-5): ✅ Complete and operational
- Adaptive research orchestrator: ✅ Delivered
- Docs & agent UX: 🔄 In progress
- Platform infrastructure: 🔄 In progress (blocked on staging access)
- Sprint 7 (UI & exports): 🚧 Planned

## Sprint Structure

### Sprint 1 – CLI & MCP Parity ✅

**Objective:** Establish unified command surface for both CLI and MCP interactions.

**Deliverables:**
- [x] Core CLI verbs: `overview`, `refine`, `enrich`, `qa`, `contracts`
- [x] MCP stdio server exposing equivalent tools
- [x] Consistent argument parsing and validation
- [x] Agent instruction documentation

**Quality Gate:** QG-1 (CLI Integrity)
- All commands present and functional
- Help text comprehensive and accurate
- Exit codes consistent

**Evidence:**
- `apps/data-platform/hotpass/cli/commands/` - CLI implementations
- `apps/data-platform/hotpass/mcp/server.py` - MCP server
- Quality gate script: `ops/quality/run_qg1.py`

---

### Sprint 2 – Enrichment Translation ✅

**Objective:** Implement deterministic-first enrichment pipeline with provenance tracking.

**Deliverables:**
- [x] Deterministic fetchers under `apps/data-platform/hotpass/enrichment/fetchers/`
- [x] Research fetchers with environment guardrails
- [x] Pipeline orchestrator with provenance tracking
- [x] Network safety toggles (`--allow-network`)

**Quality Gate:** QG-3 (Enrichment Chain)
- Deterministic enrichment succeeds offline
- Provenance metadata captured
- Network fetchers respect environment flags

**Evidence:**
- `apps/data-platform/hotpass/enrichment/` - Enrichment modules
- `ops/quality/run_qg3.py` - Gate script
- Test coverage: `tests/cli/test_quality_gates.py::TestQG3EnrichmentChain`

---

### Sprint 3 – Profiles & Compliance Unification ✅

**Objective:** Establish profile-driven validation and compliance framework.

**Deliverables:**
- [x] Profile linter (`tools/profile_lint.py`)
- [x] JSON/Schema outputs for QA gates
- [x] Contract tests with Great Expectations
- [x] Advanced resolve coverage with Splink integration

**Quality Gate:** QG-2 (Data Quality)
- Profile validation passes
- Great Expectations checkpoints succeed
- Data Docs generated

**Evidence:**
- `tools/profile_lint.py` - Profile validation
- `ops/quality/run_qg2.py` - Gate script
- Test coverage: `tests/cli/test_resolve_profile.py`

---

### Sprint 4 – Docs & Agent UX ✅

**Objective:** Provide comprehensive documentation and agent-friendly interfaces.

**Deliverables:**
- [x] CLI reference documentation
- [x] Agent instructions (`.github/copilot-instructions.md`, `AGENTS.md`)
- [x] MCP tool documentation
- [x] Diátaxis-structured docs

**Quality Gate:** QG-5 (Docs/Instructions)
- All planning documents present
- Key terms mentioned in instructions
- Documentation up-to-date

**Evidence:**
- `docs/reference/cli.md` - CLI reference
- `.github/copilot-instructions.md` - Agent instructions
- `ops/quality/run_qg5.py` - Gate script

**In Progress:**
- [ ] Navigation uplift follow-on
- [ ] Additional MCP tool documentation pages

---

### Sprint 5 – Technical Acceptance Automation ✅

**Objective:** Implement comprehensive quality gate automation.

**Deliverables:**
- [x] Gate scripts (QG-1 → QG-5)
- [x] Consolidated runner (`ops/quality/run_all_gates.py`)
- [x] MCP `hotpass.ta.check` tool
- [x] CI workflow integration
- [x] TA history tracking and analytics

**Quality Gates:** All (QG-1 → QG-5)
- QG-1: CLI Integrity
- QG-2: Data Quality
- QG-3: Enrichment Chain
- QG-4: MCP Discoverability
- QG-5: Docs/Instructions

**Evidence:**
- `ops/quality/run_qg*.py` - Individual gate scripts
- `ops/quality/run_all_gates.py` - Consolidated runner
- `.github/workflows/quality-gates.yml` - CI workflow
- Artifacts: `dist/quality-gates/latest-ta.json`, `dist/quality-gates/history.ndjson`

---

### Sprint 6 – Adaptive Research Orchestrator ✅

**Objective:** Deliver adaptive research planning and execution capabilities.

**Deliverables:**
- [x] Research orchestrator (`apps/data-platform/hotpass/research/orchestrator.py`)
- [x] CLI verbs: `plan research`, `crawl`
- [x] MCP tools: `hotpass.plan.research`, `hotpass.crawl`
- [x] Profile schema extensions (authority_sources, research_backfill)
- [x] Rate-limit scaffolding
- [x] Audit logging framework

**Quality Gate:** Integration tests
- Research planning produces structured output
- Crawl respects rate limits
- Artifacts persisted correctly

**Evidence:**
- `apps/data-platform/hotpass/research/` - Research modules
- `tests/mcp/test_research_tools.py` - Integration tests
- Audit log: `.hotpass/mcp-audit.log`

**Follow-ups:**
- [ ] Per-provider automation enhancements
- [ ] Staging rehearsal validation
- [ ] Human-in-the-loop controls

---

### Sprint 7 – Agent-First UI & Exports 🚧

**Objective:** Deliver interactive UI and multi-format export capabilities.

**Status:** Planned

**Deliverables:**
- [ ] Streamlit dashboard with AG Grid/Handsontable
- [ ] Provenance badges and status matrix
- [ ] Re-run controls with budget management
- [ ] Multi-format exports (`--export xlsx,csv,pipe`)
- [ ] Human approval workflow for low-confidence merges
- [ ] Network escalation approval flow

**Quality Gate:** User acceptance testing
- Dashboard renders correctly
- Exports produce valid outputs
- Approval workflow captures decisions

**Planned Evidence:**
- Streamlit dashboard implementation
- Export format integration tests
- Approval workflow audit logs

---

## Quality Gate Definitions

### QG-1: CLI Integrity

**Purpose:** Ensure all CLI commands are present, functional, and documented.

**Criteria:**
- All required commands present: overview, refine, enrich, qa, contracts, setup, net, aws, ctx, env, arc
- Help text available for each command
- Commands execute without errors
- Exit codes consistent (0 = success, non-zero = failure)

**Automation:** `ops/quality/run_qg1.py`

**Pass Threshold:** 13/13 checks passed

---

### QG-2: Data Quality

**Purpose:** Validate data contracts and quality expectations.

**Criteria:**
- Great Expectations checkpoints succeed
- Data Docs generated successfully
- Sample workbooks validate against profiles
- Schema exports match expectations

**Automation:** `ops/quality/run_qg2.py`

**Pass Threshold:** 7/7 checks passed

---

### QG-3: Enrichment Chain

**Purpose:** Verify enrichment pipeline operates correctly offline and online.

**Criteria:**
- Deterministic enrichment succeeds with `--allow-network=false`
- Provenance metadata captured
- Output artifacts produced
- Network fetchers respect environment flags

**Automation:** `ops/quality/run_qg3.py`

**Pass Threshold:** 3/3 checks passed

---

### QG-4: MCP Discoverability

**Purpose:** Ensure MCP server exposes all required tools.

**Criteria:**
- MCP server module exists and is importable
- Server lists all required tools: refine, enrich, qa, crawl, explain_provenance, ta.check
- Tool schemas valid
- Server responds to tool invocations

**Automation:** `ops/quality/run_qg4.py`

**Pass Threshold:** 4/4 checks passed

---

### QG-5: Docs/Instructions

**Purpose:** Verify documentation is complete and up-to-date.

**Criteria:**
- Planning documents exist: UPGRADE.md, Next_Steps.md, ROADMAP.md, IMPLEMENTATION_PLAN.md
- Agent instructions present: .github/copilot-instructions.md, AGENTS.md
- Key terms mentioned: profile, deterministic, provenance, quality gates
- Documentation references sprints and quality gates

**Automation:** `ops/quality/run_qg5.py`

**Pass Threshold:** 9/9 checks passed

---

## Platform Infrastructure Status

### Completed ✅

- Docker buildx cache reuse workflow (`.github/workflows/docker-cache.yml`)
- CodeQL and secrets scanning workflows
- SBOM and SLSA provenance generation
- OpenTelemetry exporter propagation
- Quality gate CI integration

### In Progress 🔄

- **Prefect backfill deployment validation** (blocked on staging access)
  - Manifests exist: `prefect/backfill.yaml`, `prefect/refinement.yaml`
  - Need: Staging environment validation
  - Owner: Platform

- **ARC runner rollout** (blocked on staging access)
  - Manifests exist: `infra/arc/runner-scale-set.yaml`
  - Workflow exists: `.github/workflows/arc-ephemeral-runner.yml`
  - Need: Live staging rehearsal
  - Owner: Platform

- **Marquez lineage smoke tests** (blocked on staging access)
  - Compose stack ready: `infra/marquez/docker-compose.yaml`
  - Tests ready: `tests/infrastructure/test_marquez_stack.py`
  - Need: Staging lineage evidence
  - Owner: Engineering & QA

### Planned 🚧

- Enhanced telemetry dashboards
- TA analytics aggregations
- Provider-specific research guardrails

---

## Test Coverage Requirements

### Target Coverage: ≥85% Line and Branch Coverage

**Current Coverage Status:**
- CLI commands: ✅ >90%
- Enrichment pipeline: ✅ >85%
- Quality gates: ✅ >95%
- MCP server: ✅ >85%
- Research orchestrator: 🔄 ~80% (target: >85%)

### Coverage by Module

| Module | Line Coverage | Branch Coverage | Status |
|--------|--------------|-----------------|--------|
| `apps/data-platform/hotpass/cli/` | >90% | >85% | ✅ |
| `apps/data-platform/hotpass/enrichment/` | >85% | >80% | ✅ |
| `apps/data-platform/hotpass/mcp/` | >85% | >85% | ✅ |
| `apps/data-platform/hotpass/research/` | ~80% | ~75% | 🔄 |
| `ops/quality/` | >95% | >90% | ✅ |
| `ops/validation/` | >85% | >80% | ✅ |

### Coverage Improvement Plan

1. **Research module enhancement** (target: +5% line coverage)
   - Add integration tests for provider-specific flows
   - Cover error handling paths
   - Test rate-limit scenarios

2. **Assert-free migration completion** (27 files remaining)
   - Migrate to `expect()` helper per `docs/how-to-guides/assert-free-pytest.md`
   - Improves test clarity and failure messages
   - Target: Complete by Sprint 7 start

---

## Code Quality Standards

### Linting & Formatting
- **Ruff:** Zero high-priority issues
- **Black/Ruff Format:** All code formatted consistently
- **isort:** Import ordering enforced

### Type Safety
- **MyPy:** Target <50 errors (current: ~199, documented progression)
- Strict mode enabled for new modules
- Type stubs for third-party dependencies

### Security
- **Bandit:** Zero high-severity issues
- **detect-secrets:** Clean scan required
- **CodeQL:** No critical alerts
- **Secrets scanning:** Automated on every commit

---

## Dependencies & Blockers

### Critical Path Items

**Staging Access Required:**
1. Prefect backfill deployment validation
2. ARC runner lifecycle verification
3. Marquez lineage smoke tests

**Mitigation:** Local Docker Compose stack provides development/testing environment. Production validation deferred to staging access window.

### Technical Dependencies

**Optional Dependencies:**
- Great Expectations (data quality)
- Prefect (orchestration)
- Splink (entity resolution)
- Playwright (enrichment)
- Scrapy (crawling)

**Strategy:** Graceful degradation when optional dependencies unavailable. Core functionality works offline with deterministic-only features.

---

## Release Readiness Criteria

### Must Have (Blocking)
- [x] All quality gates (QG-1 → QG-5) passing
- [x] Core CLI commands functional
- [x] MCP server operational
- [x] Test coverage ≥85% for core modules
- [x] Documentation complete
- [x] Security scans clean
- [ ] IMPLEMENTATION_PLAN.md present (this document)

### Should Have (Important)
- [x] Adaptive research orchestrator
- [x] Provenance tracking
- [x] Profile-driven validation
- [ ] Staging validation complete
- [ ] Assert-free pytest migration complete

### Nice to Have (Future)
- [ ] Streamlit dashboard enhancements
- [ ] Multi-format export support
- [ ] Human-in-the-loop approval flows
- [ ] Enhanced telemetry dashboards

---

## Risk Assessment

### High Risk
- **Staging access delays:** Mitigated by comprehensive local testing
- **Optional dependency availability:** Mitigated by graceful degradation

### Medium Risk
- **Type safety improvements:** Progressive enhancement, documented in Next_Steps.md
- **Assert-free migration:** Quality improvement, non-blocking

### Low Risk
- **Documentation drift:** Automated validation via QG-5
- **Test regression:** Comprehensive CI coverage

---

## Next Steps

### Immediate (This Release)
1. ✅ Create IMPLEMENTATION_PLAN.md (this document)
2. 🔄 Complete assert-free pytest migration
3. 🔄 Achieve ≥85% coverage for research module
4. 🔄 Document staging validation plans

### Short Term (Next Sprint)
1. Validate Prefect backfill in staging
2. Complete ARC runner rollout
3. Execute Marquez lineage smoke tests
4. Begin Sprint 7 planning

### Long Term (Future Sprints)
1. Streamlit dashboard enhancements
2. Multi-format export implementation
3. Human-in-the-loop approval workflows
4. Enhanced telemetry and analytics

---

## Maintenance & Evolution

**Review Cadence:** Weekly during active development, monthly during maintenance

**Update Triggers:**
- Sprint completion
- Quality gate changes
- Major feature additions
- Architecture changes

**Alignment:** Keep synchronized with UPGRADE.md, Next_Steps.md, and ROADMAP.md

**Archive Policy:** Superseded versions archived in `docs/archive/` with timestamp

---

**Document Status:** Active
**Next Review:** On Sprint 7 kickoff or staging access availability
**Maintainers:** Engineering & QA teams
