---
title: Explanation — developer hub
summary: Navigate the Hotpass codebase, tooling, and review expectations as a platform engineer.
last_updated: 2025-11-03
---

# Developer hub

Use this hub to jump into the codebase, understand the architecture, and find the runbooks that keep quality gates green.

## Codebase map

| Path | Purpose |
| ---- | ------- |
| `apps/data-platform/hotpass/cli/` | Unified CLI entry point (`hotpass`), including commands such as `refine`, `enrich`, `qa`, `net`, `doctor`, and `setup`. |
| `apps/data-platform/hotpass/pipeline/` | Core pipeline stages (`ingestion.py`, `aggregation.py`, `validation.py`, `enrichment.py`, `export.py`) and orchestrator/feature toggles. |
| `apps/data-platform/hotpass/prefect/` | Deployment manifests and helpers for Prefect work pools. |
| `apps/data-platform/hotpass/mcp/` | MCP server and role policy code. |
| `apps/web-ui/` | React operator experience, with Storybook stories under `apps/web-ui/src`. |
| `ops/` | Automation scripts (quality gates, UV sync, tunnel helpers, supply-chain tooling). |

```{mermaid}
graph TD
    CLI[CLI & MCP<br/>apps/data-platform/hotpass] --> Docs[Diátaxis docs<br/>docs/]
    CLI --> Tests[Quality gates<br/>tests/]
    Docs --> Agents[AGENTS.md & tools.json]
    Tests --> CI[GitHub workflows<br/>.github/workflows]
    Docs --> WebUI[Operator UI<br/>apps/web-ui]
```

Start with `docs/explanations/architecture.md` for diagrams and the C4 workspace. Use `docs/reference/development-standards.md` to align with linting, typing, and documentation conventions.

## Daily workflow

1. **Bootstrap** — follow `docs/how-to-guides/toolchain-setup.md` to sync extras, install pre-commit hooks, and install web assets.
2. **Develop** — follow feature-specific guides in `docs/how-to-guides/`:
   - Pipeline changes: `configure-pipeline.md`, `run-a-backfill.md`.
   - Prefect and tunnels: `setup-wizard.md`, `manage-prefect-deployments.md`, `manage-arc-runners.md`.
   - Web UI updates: `format-and-validate.md`, `secure-web-auth.md`.
3. **Validate** — run the QA checklist (`docs/how-to-guides/qa-checklist.md`) before you push. Capture CLI output (`hotpass --help`, `hotpass overview`) if your change affects commands or documentation.
4. **Document** — update the relevant Diátaxis section (tutorial, how-to, reference, explanation). Treat the docs build (`uv run sphinx-build -n -W -b html docs docs/_build/html`) as a required local gate.

## Review readiness

- Keep pull requests focused. Link deferred work in `Next_Steps.md` with an owner and due date.
- Add or update tests alongside code changes. Use the bandwidth markers described in `docs/engineering/testing.md`.
- Update diagrams (`docs/explanations/architecture.md`, `docs/how-to-guides/agentic-orchestration.md`) when you change flows.
- Attach artefacts (`htmlcov/`, `dist/reports/sbom.json`, refreshed CLI output) to the PR description or release ticket.

## Escalation paths

- **Quality gates** — see `docs/security/quality-gates.md` for owners and remediation policy.
- **Documentation** — flag large reorganisations in `docs/Next_Steps.md` and coordinate with the docs maintainers.
- **Operations** — runbooks live under `docs/operations/` (backfills, staging rehearsals, lineage smoke tests) and `docs/how-to-guides/incident-response.md`.
- **Governance** — the programme charter and policy references live in `docs/governance/` and `docs/compliance/`.

## Quick shortcuts

- `uv run hotpass overview` — confirm CLI verbs.
- `uv run hotpass doctor --profile ...` — validate config before handing off to operators.
- `uv run pytest tests/cli/test_quality_gates.py -k QG1` — reproduce CLI regressions.
- `make docs` (or `uv run sphinx-build -n -W -b html ...`) — treat warnings as failures.

Keep this page updated whenever you add a new command, quality gate, or directory so engineers and AI agents land in the right spot immediately.
