---
title: Data governance navigation
summary: How to locate, maintain, and review the governance artefacts that prove Hotpass data quality.
last_updated: 2025-11-02
---

# Data governance navigation

This guide closes the remaining Phase 2 governance action item by explaining how
QA and documentation teams surface the key artefacts—Great Expectations Data
Docs, schema exports, lineage, and evidence packs—while preparing the
`docs/data-governance-nav` pull request. Treat it as the canonical map for where
to find validation signals before programme and audit reviews.

## Primary entry points

1. **Data Docs** — Generated HTML reports under `dist/data-docs/` capture the
   latest Great Expectations checkpoint runs. Publish them as part of release
   PRs and link to the hosted copy from the roadmap. Use the refresh helper
   (`uv run python ops/validation/refresh_data_docs.py`) to update the set
   before every retro or stakeholder review.
2. **Schema exports** — Canonical JSON Schemas live under `schemas/` with the
   rendered catalogue in [`docs/reference/schemas.md`](../reference/schemas.md).
   Review these when reconciling contract changes or validating sample payloads
   during onboarding.
3. **Lineage views** — The Marquez quickstart described in
   [`docs/observability/marquez.md`](../observability/marquez.md) provides an
   interactive lineage graph that pairs with Data Docs to trace failing columns
   back to their upstream sources.
4. **Evidence ledger** — Programme evidence and audit checkpoints remain in
   [`docs/reference/research-log.md`](../reference/research-log.md). File new
   entries alongside Data Docs refreshes so auditors can match screenshots,
   artefacts, and PR references.

## Keeping artefacts in sync

- **QA rotation** — Own the `make qa` sweep and ensure Great Expectations suites
  align with any updated contracts. Raise blockers in the programme stand-up if
  suites diverge or if coverage drops below expectations.
- **Docs rotation** — Update the landing page navigation and this guide whenever
  new governance artefacts launch. Cross-link relevant how-to guides (formatting,
  validation, lineage) and include `last_updated` metadata so readers trust the
  currency of each page.
- **Shared checklist** — Before closing the `docs/data-governance-nav` PR or a
  related governance milestone, confirm that:
  - Data Docs regenerated successfully and are attached to the review.
  - Schema exports and reference docs build without warnings.
  - Marquez lineage screenshots or logs accompany any lineage-related change.
  - `Next_Steps.md` captures residual actions for the next iteration.

## Collaboration and escalation

- Surface navigation or artefact gaps in the Programme retro using
  [`docs/operations/foundation-retro.md`](../operations/foundation-retro.md).
- Coordinate with Platform when runner availability blocks Data Docs refreshes;
  the ARC lifecycle verifier now supports snapshot simulations so QA can iterate
  without live infrastructure.
- Escalate governance risks through the roadmap (`ROADMAP.md` and
  [`docs/roadmap.md`](../roadmap.md)) so stakeholders can align upcoming PRs with
  the documented expectations.
