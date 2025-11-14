---
title: How-to — run the Hotpass QA checklist
summary: Execute smoke tests, quality gates, and artefact captures before you merge or cut a release.
last_updated: 2025-11-03
---

# Run the Hotpass QA checklist

Use this runbook before you merge a substantial change or promote a release branch. It maps each gate to the command under version control so you can confirm the repo stays in a release-ready state.

## 1. Smoke tier (under 5 minutes)

```bash
make qa
```

The target runs `scripts/testing/smoke.sh`, which in turn calls:

- `uv run ruff check` and `uv run ruff format --check`
- `uv run pytest -m smoke tests`
- `pnpm run test:unit`
- `uv run pre-commit run --all-files`

**Artefacts:** HTML coverage reports under `htmlcov/` and `apps/web-ui/coverage/unit/`.

## 2. Full regression

```bash
make qa-full
```

This command invokes `scripts/testing/full.sh` and extends the smoke tier with:

- `uv run mypy apps/data-platform/hotpass/...`
- `uv run bandit -r apps/data-platform ops`
- `uv run detect-secrets scan apps/data-platform ops scripts`
- `uv run python -m build`
- Mutation tests via `uv run python ops/qa/run_mutation_tests.py`

**Artefacts:** `coverage.xml`, mutation reports under `dist/mutation/`, and refreshed SBOM assets.

## 3. Quality gates (tests/cli/test_quality_gates.py)

Run the pytest module directly when you need parity with the nightly `quality-gates` workflow:

```bash
uv run pytest tests/cli/test_quality_gates.py -v
```

You should see the following passes:

| Gate                     | Purpose                                            | Checks                                                                                                                                                                                                                      |
| ------------------------ | -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| QG-1 CLI integrity       | Ensure CLI verbs remain discoverable.              | `hotpass --help`, `overview`, `refine`, `enrich`, `qa`, `contracts`, `setup`, `net`, `aws`, `ctx`, `env`, `arc`, `distro`, `run`, `backfill`, `doctor`, `orchestrate`, `resolve`, `dashboard`, `deploy`, `init`, `version`. |
| QG-2 Data quality        | Exercise Great Expectations suites and Data Docs.  | `ops/quality/run_qg2.py --json` emits stats plus the Data Docs path under `dist/quality-gates/qg2-data-quality/`.                                                                                                           |
| QG-3 Enrichment chain    | Validate deterministic enrichment with provenance. | `ops/quality/run_qg3.py --json` produces an enriched workbook containing the five provenance columns.                                                                                                                       |
| QG-4 MCP discoverability | Confirm tools exposed by `hotpass.mcp.server`.     | `ops/quality/run_qg4.py --json` lists the required stdio tools and ensures registration passes.                                                                                                                             |
| QG-5 Docs & instructions | Verify Codex/Copilot guidance stays present.       | `ops/quality/run_qg5.py --json` inspects `.github/copilot-instructions.md` and `AGENTS.md` for required terminology.                                                                                                        |

## 4. CLI spot checks

Run these snippets to capture fresh output for docs and dashboards:

```bash
uv run hotpass --help
uv run hotpass overview
uv run hotpass refine --help
uv run hotpass qa all --profile generic --profile-search-path apps/data-platform/hotpass/profiles
```

If you regenerate screenshots or code blocks in the documentation, paste the updated output immediately so the site stays current with the CLI.

## 5. Prefect and enrichment rehearsals

- Prefect backfill guardrail: follow `docs/operations/prefect-backfill-guardrails.md`.
- Enrichment provenance: confirm `uv run hotpass enrich --input <refined.xlsx> --output <dist/enriched.xlsx> --allow-network=false` succeeds against the deterministic test fixture in `dist/quality-gates/qg3-enrichment/`.

## 6. Documentation build

```bash
uv run sphinx-build -n -W -b html docs docs/_build/html
```

Treat warnings as failures. The nightly docs workflow mirrors this command and will fail your pull request otherwise.

## 7. Artefact collection

- Upload the refreshed coverage reports, SBOM (`dist/reports/sbom.json`), and quality gate outputs to your release ticket or evidence bucket.
- Update `Next_Steps.md` with any residual actions plus owner and due date.

Completing this checklist keeps the repo compliant with QG-1 through QG-5 and provides reviewers with fresh command output and artefacts. If any step fails, stop and fix the regression instead of deferring to CI.
