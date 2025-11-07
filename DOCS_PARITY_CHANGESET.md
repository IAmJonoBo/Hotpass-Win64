# Documentation Parity Changeset

**Date:** 2025-11-07
**PR:** copilot/update-docs-for-parity
**Purpose:** Establish 100% code↔docs parity with automated sanity checks

## What Was Added

### 1. Documentation Verification Script (`scripts/verify_docs.py`)

A comprehensive Python script that:
- **Extracts source of truth** from the codebase:
  - Parses `apps/data-platform/hotpass/cli/main.py` to discover all 28 registered CLI commands
  - Scans Python files for environment variable references (210+ discovered)
  - Scans shell scripts for environment variable usage
- **Validates documentation** against source truth:
  - Checks all `.md` files in root and `docs/` directory
  - Identifies unknown commands referenced in documentation
  - Flags environment variables not found in source code
  - Reduces false positives for Python imports, Mermaid syntax, and generic terms
- **Outputs results** in two formats:
  - Human-readable colored terminal output
  - JSON format for CI integration
- **Current status:** Runs in pre-commit and CI, currently non-blocking (--fail-on-issues=False)

**Discovered:**
- 28 CLI commands (overview, refine, enrich, qa, contracts, credentials, imports, inventory, plan, crawl, setup, net, aws, ctx, env, arc, distro, run, backfill, doctor, orchestrate, resolve, dashboard, deploy, init, version, explain-provenance, optional)
- 210+ environment variables (HOTPASS_* namespace and others)
- 33 potential parity issues requiring manual review

### 2. Mermaid Architecture Diagrams

Created three comprehensive diagrams under `docs/diagrams/`:

#### `system-architecture.mmd`
- **Purpose:** High-level component view
- **Shows:** All major subsystems and their relationships
- **Components:**
  - CLI & Operators (hotpass, hotpass-operator, MCP server)
  - Core Pipeline (refinement, enrichment, resolution, QA)
  - Orchestration (Prefect, Marquez, OpenTelemetry)
  - Storage (MinIO/S3, LocalStack, archives)
  - Research (SearXNG, crawlers, LLMs)
  - Governance (contracts, Data Docs, Presidio, POPIA)
  - Infrastructure (tunnels, ARC, contexts)

#### `data-flow.mmd`
- **Purpose:** End-to-end data transformation view
- **Traces:** Raw input → refinement → outputs → optional enrichment/resolution → QA → governance
- **Stages:**
  - Input: Raw workbooks + profile config
  - Refinement: Load → normalise → dedupe → validate → score
  - Primary Output: Refined XLSX/Parquet + archives
  - Enrichment: Deterministic + network (optional)
  - Resolution: Splink linkage + Label Studio (optional)
  - QA: Great Expectations + Frictionless contracts
  - Governance: Schemas + audit + compliance reports

#### `run-lifecycle.mmd`
- **Purpose:** Sequence diagram of a complete run
- **Shows:** Step-by-step interaction between:
  - Operator → CLI → Profile Loader
  - Pipeline → Great Expectations
  - Pipeline → Storage Layer
  - Pipeline → Marquez (lineage)
  - Pipeline → OpenTelemetry (telemetry)
  - Optional QA, enrichment, and research planning flows

All diagrams use consistent color coding and are maintained as source files for version control.

### 3. CI/Pre-commit Integration

#### Pre-commit Hook (`.pre-commit-config.yaml`)
Added new hook:
```yaml
- id: verify-docs
  name: Verify documentation parity
  entry: uv run python scripts/verify_docs.py
  language: system
  pass_filenames: false
  files: \.(md|py)$
  stages: [pre-commit]
```
- Runs on every commit that touches `.md` or `.py` files
- Currently non-blocking (exit code 0 even with issues)

#### CI Workflow (`.github/workflows/quality-gates.yml`)
Added step to `quality-gate-checks` job:
```yaml
- name: Verify documentation parity
  run: uv run python scripts/verify_docs.py
```
- Runs after QG-5 (Docs/Instructions check)
- Provides visibility into documentation drift
- Currently informational only

### 4. Documentation Updates

#### README.md
- **Added:** "Architecture" section with comprehensive overview
- **Content:**
  - Links to all three Mermaid diagrams
  - Description of each diagram's purpose and contents
  - Note about automated verification maintaining accuracy
  - Clear captions for diagram links
- **Enhanced:** Quick Overview section now links to detailed diagrams

#### docs/explanations/architecture.md
- **Added:** "Architecture diagrams" section at the top
- **Content:**
  - Lists all three diagram files with descriptions
  - Notes automatic verification process
  - Positions diagrams before the existing system context diagram
- **Updated:** last_updated date to 2025-11-07

## What Was Changed

### File Modifications

1. **scripts/verify_docs.py** (new)
   - 456 lines of Python code
   - Comprehensive CLI command and environment variable extraction
   - Documentation validation with smart false-positive filtering
   - Colored terminal output and JSON export

2. **docs/diagrams/system-architecture.mmd** (new)
   - 84 lines of Mermaid diagram source
   - Graph TB layout with 7 subgraphs
   - 28 component nodes with color-coded styling

3. **docs/diagrams/data-flow.mmd** (new)
   - 95 lines of Mermaid diagram source
   - Flowchart LR layout with 7 subgraphs
   - 35 transformation nodes showing complete data pipeline

4. **docs/diagrams/run-lifecycle.mmd** (new)
   - 77 lines of Mermaid diagram source
   - Sequence diagram with 8 participants
   - 40+ interactions showing complete lifecycle

5. **.pre-commit-config.yaml** (modified)
   - Added verify-docs hook under local hooks section

6. **.github/workflows/quality-gates.yml** (modified)
   - Added documentation verification step after QG-5

7. **README.md** (modified)
   - Added 43 lines for Architecture section
   - Enhanced Quick Overview with diagram links

8. **docs/explanations/architecture.md** (modified)
   - Added 12 lines for Architecture diagrams section
   - Updated last_updated date

## Known Issues / Future Work

### 33 Parity Issues Identified

The verification script detected 33 potential issues, primarily environment variables documented but not found in the current source code scan:

**Categories:**
1. **Environment variables in examples** (e.g., `HOTPASS_LLM_BASE_URL`, `HOTPASS_GEOCODE_API_KEY`)
   - These may be valid variables used only in configuration files
   - Need manual review to determine if they should be added to source or removed from docs

2. **Provider-specific variables** (e.g., `HOTPASS_CIPC_*`, `HOTPASS_INTENT_TOKEN`)
   - May be optional/plugin-specific
   - Documentation might be ahead of implementation

3. **Legacy references**
   - May represent deprecated features that need cleanup

**Action Items:**
- [ ] Manual review of all 33 flagged items
- [ ] Update documentation or add variables to source as appropriate
- [ ] Enable `--fail-on-issues` flag once issues are resolved
- [ ] Consider adding config file parsing to verification script

### Recommended Next Steps

1. **Immediate:**
   - Review the 33 flagged environment variables
   - Determine which are valid, which are outdated, which need implementation

2. **Short-term:**
   - Add example usage to verification script docs
   - Consider extracting env vars from TOML/YAML configs
   - Add command flag verification (currently only checks command names)

3. **Medium-term:**
   - Enable strict mode (`--fail-on-issues=True`) after cleanup
   - Add verification of code examples in documentation
   - Integrate with documentation build process

## Testing Performed

### Manual Testing
- ✅ Ran `uv run hotpass overview` - confirmed 28 commands listed
- ✅ Ran `scripts/verify_docs.py` - confirmed output and JSON export
- ✅ Pre-commit hook executes successfully
- ✅ All diagram files render correctly in Mermaid viewers

### Automated Testing
- ✅ Pre-commit hooks pass (including new verify-docs hook)
- ✅ Ruff formatting/linting passes
- ✅ mypy type checking passes
- ✅ detect-secrets passes
- ✅ uv pip check passes

### QA Gates
- Ready for: `make qa`, `uv run hotpass qa all`
- CI will run quality gates on push

## Backwards Compatibility

**No breaking changes:**
- All additions are new files or additive changes
- Existing CLI commands unchanged
- Documentation enhanced, not replaced
- CI/pre-commit hooks non-blocking

## Migration Guide

**For developers:**
1. Pull the latest changes
2. Run `uv run python scripts/verify_docs.py` to see current parity status
3. Pre-commit will now run verification on commits touching `.md` or `.py` files
4. If you add new CLI commands, verify documentation is updated

**For documentation writers:**
1. When referencing CLI commands, use exact names from `hotpass --help`
2. When documenting environment variables, ensure they exist in source or mark as examples
3. Check verification output before committing: `uv run python scripts/verify_docs.py`

## Summary

This changeset establishes a foundation for maintaining documentation parity through:

1. **Automated verification** that catches drift between code and docs
2. **Visual documentation** via comprehensive Mermaid diagrams
3. **CI integration** that makes parity checks visible in every build
4. **Clear ownership** with diagrams versioned alongside code

The system is designed to evolve with the codebase while maintaining accuracy without creating excessive friction in the development workflow. The current informational mode allows teams to address existing issues before enforcing strict parity requirements.
