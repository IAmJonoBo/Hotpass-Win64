---
title: Reference — development standards
summary: Coding, linting, and documentation conventions that keep the Hotpass codebase consistent.
last_updated: 2025-11-03
---

# Development standards

Use this reference when you write or review code. It captures the conventions enforced by the configuration files in the repository, so you can map CI failures back to the rules that triggered them.

## Python style

- Python 3.13 is the supported runtime. `pyproject.toml` pins `requires-python = ">=3.13,<3.14"` and mypy compiles against the same version.
- Ruff provides linting **and** formatting. The project enforces a line length of 100 characters, double quotes, and space indents. Run `uv run ruff check` and `uv run ruff format --check` locally or rely on `make qa`.
- Type hints are mandatory for modules covered by the mypy target list:
  - `apps/data-platform/hotpass/pipeline/config.py`
  - `apps/data-platform/hotpass/storage/adapters.py`
  - `apps/data-platform/hotpass/domain/party/schemas.py`
  - `apps/data-platform/hotpass/_compat_nameparser.py`
  - `apps/data-platform/hotpass/orchestration.py`
  - `apps/data-platform/hotpass/pipeline/orchestrator.py`
  - `apps/data-platform/hotpass/telemetry/{bootstrap,registry}.py`
  - `ops/quality/fitness_functions.py`
    If you extend these modules, run `uv run mypy` before pushing so CI stays green.
- Keep the functional decomposition used in `apps/data-platform/hotpass/pipeline/`: ingestion, mapping, validation, enrichment, and export stages each live in their own module. Prefer extending those modules over adding ad-hoc logic to `pipeline/base.py`.

## Testing conventions

- All tests live under `tests/` and default to the `full` bandwidth marker. Use `@pytest.mark.bandwidth("smoke")` for deterministic smoke coverage or `bandwidth("quality_gate")` for nightly-only gates.
- Do not use bare `assert`. Instead, import and call `expect(condition, message)` from `tests/cli/test_quality_gates.py`, which satisfies Bandit rule B101.
- Pytest emits coverage reports (`coverage.xml` and HTML under `htmlcov/`) through `addopts` defined in `pyproject.toml`. You do not need to add flags when running `pytest`.
- UI unit tests use Vitest (`pnpm run test:unit`). Playwright e2e checks require a one-time `npx playwright install --with-deps chromium`.

## Commit and branch hygiene

- Branch from `main` and name branches `<type>/<short-description>` (for example, `docs/refresh-cli-reference` or `fix/pipeline-redaction-null`).
- Use Conventional Commits in PR titles and commits (`docs: update how-to guide`, `feat: add enrichment provenance column`). Release Drafter consumes these scopes.
- Keep pull requests focused; link follow-up work in `Next_Steps.md` when you intentionally defer changes.

## Documentation expectations

- Every Markdown or MyST file in `docs/` must include front matter with `title`, `summary`, and `last_updated`.
- The documentation build treats warnings as errors. Run `uv run sphinx-build -n -W -b html docs docs/_build/html` before you submit a change.
- Keep tutorials, how-to guides, reference topics, and explanations aligned with the Diátaxis sections introduced in `docs/index.md`. Move content between sections instead of duplicating it.

## Security and compliance

- Bandit, detect-secrets, and CycloneDX run during `make qa-full`. Address findings directly; do not suppress warnings without recording a rationale in `Next_Steps.md`.
- When you add new enrichment connectors or API integrations, document required credentials in `docs/reference/security-policy.md` and update `tools.json` if you expose a new MCP tool.
- Provenance columns (`provenance_source`, `provenance_timestamp`, `provenance_confidence`, `provenance_strategy`, `provenance_network_status`) are mandatory for enriched datasets. The enrichment gate (`ops/quality/run_qg3.py`) enforces this—make sure your changes preserve the columns.

## When in doubt

- Prefer extending existing how-to guides or explanations instead of adding standalone notes.
- Ask for a docs review when you touch CLI output, sample commands, or diagrams. The documentation test plan (`docs/how-to-guides/qa-checklist.md`) expects these artefacts to stay current.
- Capture architectural decisions as ADRs under `docs/adr/` using the template in `docs/reference/templates.md`.

These standards keep the repo predictable for engineers, operators, and AI assistants. If a guideline needs to change, propose the update and reference the impacted tooling so reviewers understand the blast radius.
