# Hotpass Repository Restructure Plan

> Draft — work-in-progress mapping to align Hotpass with the `frontier-repo-template` layout.
> Last updated: 2025-10-31

## 1. Goals

- Adopt a predictable, language-agnostic directory structure (`apps/`, `packages/`, `infra/`, `ops/`, `docs/`, `tests/`, etc.).
- Preserve the `hotpass` Python namespace and console entry points without breaking existing workflows.
- Keep compliance/governance artefacts, CI automation, and documentation in sync during the migration.
- Stage the transition so that every phase is reversible and fully validated (lint, tests, quality gates).

## 2. Current → Target Mapping

| Current location                          | Target bucket                         | Notes / follow-up                                                                |
| ----------------------------------------- | ------------------------------------- | -------------------------------------------------------------------------------- |
| `apps/data-platform/hotpass/**`           | `apps/data-platform/**` (primary app) | Retain `hotpass` namespace via package module or alias; update `pyproject.toml`. |
| Shared runtime helpers (to be identified) | `packages/hotpass-core/**`            | Extract reusable modules from `apps/` as needed after initial move.              |
| `ops/quality/*`                           | `ops/quality/*`                       | Update imports in quality gate runner + tests.                                   |
| `ops/arc/*`                               | `ops/arc/*`                           | ARC verifier imports in tests/workflows must point to new path.                  |
| `ops/idp/*` and bootstrap utilities       | `ops/bootstrap/*`                     | CLI bootstrap docs need path refresh.                                            |
| Remaining `scripts/*`                     | `ops/` or `tools/` (per scope)        | Categorise per automation domain; adjust invocation docs & workflows.            |
| `infra/arc`, `infra/marquez`              | `infra/` (unchanged)                  | Confirm Terraform/Kustomize references after move.                               |
| `prefect/*.yaml`                          | `ops/orchestration/prefect/*.yaml`    | Update CLI/docs referencing manifests.                                           |
| `docs/**`                                 | `docs/**` (unchanged)                 | Update internal links for moved code paths.                                      |
| Governance artefacts (`ROADMAP.md`, etc.) | `docs/governance/…` (links only)      | Files remain but references to code locations must be updated.                   |
| `tests/**`                                | `tests/**` (unchanged)                | Update imports once runtime/scripts move.                                        |
| `dist/**`                                 | `dist/**` (or `ops/artifacts/**`)     | Decide whether to retain root `dist`; update evidence checklists accordingly.    |
| `schemas/`, `data_expectations/`          | `packages/data-contracts/**` (future) | Optional follow-up; initial move may leave them in place and just relabel docs.  |
| CLI launcher `hotpass` (shell script)     | `tools/cli/hotpass`                   | Ensure script points to new module location.                                     |
| Root configs (`pyproject.toml`, etc.)     | Root                                  | Update paths for packages, coverage, lint config.                                |

> **Action:** refine the table with specific module lists before executing any `git mv`.

## 3. Module & Import Strategy

- **Namespace preservation:** keep `import hotpass…` valid by:
  - Moving `apps/data-platform/hotpass` to `apps/data-platform/hotpass` and pointing `pyproject.toml`’s `packages`/`package-dir` to the new path, **or**
  - Creating `packages/hotpass_core` with `hotpass/` inside and updating `apps/data-platform` to import from that package.
- **Transitional shim:** add a temporary `apps/data-platform/hotpass/__init__.py` that imports from the new package until all references are updated (remove after migration).
- **Entry points:** update the console script in `pyproject.toml` (`hotpass = hotpass.cli.main:main`) if module path changes; adjust the `hotpass` shell launcher accordingly.
- **Tests & scripts:** after moves, run `python -m compileall` or import sweeps to catch stale paths; ensure `tests/scripts/test_arc_runner_verifier.py` and CLI tests reference new module locations.

## 4. Automation & Config Touchpoints

- **CI workflows:** `.github/workflows/*.yml` referencing `scripts/...`, `src/...`, or `prefect/*.yaml` must be updated concurrently.
- **Makefile:** adjust targets that shell into `scripts/` or assume `src/` paths (e.g., lint, mypy, pytest).
- **Pre-commit & lint configs:** update include/exclude globs (`.pre-commit-config.yaml`, `pyproject.toml` [ruff, mypy, coverage], `detect-secrets` baseline).
- **Docs:** refresh path references in README, AGENTS.md, CLI reference, repo inventory, roadmap, implementation plan, contributing guides, ADRs, and runbooks.
- **Packaging:** confirm `uv.lock`, `requirements*.txt`, and `setup` metadata still resolve after directory changes.

## 5. Migration Phases

1. **Design sign-off**
   - Finalise mapping table, confirm destination names, and circulate for review.
   - Decide on artefact directory strategy (`dist/` vs `ops/artifacts/`).
2. **Prep & shims**
   - Introduce namespace shim (`packages/hotpass_core` or similar).
   - Update `pyproject.toml` and CLI launcher to support dual locations if needed.
   - Adjust CI configs to accept both old/new paths temporarily.
3. **Domain moves (repeat per group)**
   - Use `git mv` to relocate runtime code (`apps/data-platform/hotpass` → `apps/...`).
   - Update imports, run targeted tests (`uv run pytest tests/test_*`), lint, and quality gates.
   - Move automation scripts, update workflows/tests, validate.
4. **Docs & workflow updates**
   - Immediately patch documentation and GitHub workflows referencing the moved files.
   - Refresh repo inventory and roadmap/discovery docs.
5. **Cleanup**
   - Remove transitional shims, obsolete paths, and launcher proxies once everything passes CI.
   - Capture evidence in `Next_Steps.md`/`Next_Steps_Log.md` and governance artefacts.

## 6. Validation Checklist

- `uv run ruff check` and `uv run mypy` succeed.
- `uv run pytest` (core suites + `tests/scripts`) succeeds.
- Quality gates workflow (`ops/quality/run_all_gates.py`) runs green.
- CLI smoke tests (`uv run hotpass overview`, refine/enrich/qa) succeed.
- ARC verifier (`python ops/arc/verify_runner_lifecycle.py …`) executes post-move.
- GitHub workflows pass in CI (process-data, quality-gates, docs, arc smoke).
- README quickstart and agent docs reference the updated commands/paths.

---

Use this document as the working plan. Update sections as mapping decisions solidify and during execution capture any deviations or post-migration clean-up tasks.
