---
title: Quality and security gates
summary: Expanded automated gates covering testing, linting, mutation, contracts, and security scans.
last_updated: 2025-11-02
---

## Current automation

| Gate                     | Tooling                | Command                                                                                       | Evidence                    |
| ------------------------ | ---------------------- | --------------------------------------------------------------------------------------------- | --------------------------- |
| Unit + integration tests | pytest                 | `uv run pytest --cov=src --cov=tests`                                                         | QA job (`process-data.yml`) |
| Linting                  | Ruff                   | `uv run ruff check`                                                                           | QA job                      |
| Formatting               | Ruff                   | `uv run ruff format --check`                                                                  | QA job                      |
| Types                    | mypy                   | `uv run mypy src tests scripts`                                                               | QA job                      |
| Security                 | Bandit                 | `uv run bandit -r src scripts`                                                                | QA job                      |
| Secrets                  | detect-secrets         | `uv run detect-secrets scan src tests scripts`                                                | QA job                      |
| Build                    | uv build               | `uv run uv build`                                                                             | QA job                      |
| Lineage coverage         | pytest                 | `uv run pytest tests/test_orchestration_lineage.py tests/cli/test_run_lineage_integration.py` |
| QA job                   |
| Accessibility            | pytest marker          | `uv run pytest -m accessibility`                                                              | Accessibility job           |
| Mutation testing         | mutmut                 | `uv run python ops/qa/run_mutation_tests.py`                                                  | Mutation job                |
| Contract testing         | pytest contract suite  | `uv run pytest tests/contracts`                                                               | QA job                      |
| Static analysis          | Semgrep                | `uv run semgrep --config=policy/semgrep/hotpass.yml`                                          | Static-analysis job         |
| Supply-chain             | CycloneDX + provenance | `uv run python ops/supply_chain/generate_sbom.py`                                             | Supply-chain job            |
| Policy-as-code           | OPA                    | `opa eval --data policy --input dist/sbom/hotpass-sbom.json "data.hotpass.allow"`             | Supply-chain job            |

The Semgrep scan relies on the repository-hosted `policy/semgrep/hotpass.yml` ruleset so quality gates pass without fetching
remote registries.

The pipeline refactor split `pipeline.base` into stage-specific modules (`ingestion`, `aggregation`, `validation`, `export`, and
`config`). The fitness-function gate (`uv run python ops/quality/fitness_functions.py`) now watches these modules to keep the
orchestrator slim enough to review in isolation.

## Additional gates roadmap

- **OWASP ZAP baseline** — Execute via Docker action targeting Streamlit staging env (pending).
- **Performance budget** — Add `pytest-benchmark` thresholds for pipeline latency.
- **Accessibility budget** — Gate on zero critical axe violations once Playwright integration lands.
- **CodeQL** — Evaluate integration for static code analysis (pending GitHub Advanced Security licence).

## Governance

- Document gate owners in `Next_Steps.md` tasks.
- Capture waiver process (owner approval, expiry date) in `docs/governance/pr-playbook.md`.
- Record gate outcomes per release in `docs/roadmap/30-60-90.md`.
