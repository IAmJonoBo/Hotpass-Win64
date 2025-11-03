---
title: Documentation Audit Report — 2025-11-18
summary: Follow-up audit capturing navigation gaps, build warnings, and remediation actions after restructuring the docs architecture.
last_updated: 2025-11-18
---

# Documentation Audit Report

## Executive summary

The 18 November audit verified that the documentation restructuring aligns with the new overview → guides → reference model. The
review focused on Sphinx build health, unresolved cross-references, Smart Import coverage, and potential security signal within
published examples.

## Key findings

### Navigation & scope

- The top-level index now advertises overview, implementation guides, and reference material, but 32 legacy markdown files under
  `docs/docs/**` remain outside the navigation tree and continue to trigger `toc.not_included` warnings.
- Multiple how-to guides (for example `how-to-guides/manage-arc-runners.md`) reference infrastructure paths that no longer exist
  (`infra/arc/terraform`). These need updated links or archival notices.

### Build warnings

- `sphinx-build -n` still emits **360 heading hierarchy warnings** for historical ADRs and governance pages that start at H2. A
  staged backlog reduction plan is required before enabling `-W` in CI.
- Ten cross-reference warnings remain, notably in `agent-instructions.md` (`../UPGRADE.md`) and `reference/repo-inventory.md`
  (links to code directories that are not documentation pages). Each warning has been catalogued for follow-up fixes.

### Security & compliance

- Example connection strings in `adr/0006-mlflow-lifecycle-strategy.md` and `how-to-guides/model-lifecycle-mlflow.md` used the
  literal `user:pass` credentials. These have been replaced with `<user>:<password>` placeholders and should stay masked in
  future snippets.
- `detect-secrets` targeted scans succeeded on `docs/`, `apps/data-platform/hotpass/`, and `tests/`, but running the tool against
  the repository root still requires scoped excludes to avoid timeouts. The doc tooling backlog now tracks this requirement.

### Content gaps

- `reference/smart-import-plan.md` previously listed delivery checkboxes only. The page has been expanded with a full data flow,
  dependency map, and narrative to document how CLI, API, and UI components interact.
- The documentation now includes a dedicated `documentation-architecture` page so contributors can validate new content against
  the three core pillars.

## Actions taken in this audit

1. Updated the global index and added `architecture/documentation-architecture.md` to document the navigation model.
2. Replaced legacy Mermaid code fences (` ```mermaid`) with MyST directives (` ```{mermaid}`) to eliminate highlighting warnings.
3. Sanitised MLflow connection string examples to remove credential-shaped strings flagged by `detect-secrets`.
4. Rebuilt Smart Import reference content with an explicit data flow diagram, dependency list, and operator narrative.

## Open follow-ups

| Item                                      | Owner            | Notes                                                                                |
| ----------------------------------------- | ---------------- | ------------------------------------------------------------------------------------ |
| Reduce heading hierarchy warnings         | Docs maintainers | Normalise legacy ADRs/governance pages to start at H1 before re-enabling `-W`.       |
| Reconcile orphaned `docs/docs/**` content | Docs maintainers | Decide whether to migrate or archive the duplicate handbook pages.                   |
| Harden detect-secrets baseline            | Platform         | Commit a `detect-secrets.yaml` with repo-specific excludes to allow full-repo scans. |
| Refresh infrastructure links              | Platform         | Replace outdated ARC Terraform references with the current deployment path.          |

The audit log complements `DOCUMENTATION_AUDIT_2025-11-02.md`; keep both records for longitudinal tracking until the backlog is
fully resolved.
