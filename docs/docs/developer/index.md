---
title: Developer hub
toc_hide: true
summary: Codebase orientation, architecture, and contribution workflows for Hotpass engineers.
last_updated: 2025-11-03
---

# Developer hub

This guide collects the material engineers reference day-to-day:

- **Architecture & platform** – high-level diagrams, system boundaries, and data flow.
- **Environment & tooling** – how to bootstrap the uv environment, Docker images, and QA pipelines.
- **Contribution workflow** – branch policies, required checks, release automation, and escalation paths.

```text
+-----------------+      +-------------------------+      +-----------------------+
|  Source repos   | ---> |  CI quality gates (uv,  | ---> |  Release artefacts    |
|  (hotpass/*)    |      |  pytest, lint, SBOM)    |      |  (wheels, SBOM, docs) |
+-----------------+      +-------------------------+      +-----------------------+
         |                          |                                 |
         v                          v                                 v
   Local dev env             Playwright smoke                 Operator hand-off
 (Dockerfile.dev)           + accessibility suites               & user docs
```

```{toctree}
:maxdepth: 1
:hidden:

Architecture overview </architecture/documentation-architecture>
System design deep dive </docs/architecture/ARCHITECTURE_OVERVIEW>
Quality gates & CI </quality/quality-gates>
Toolchain setup </development/TOOLCHAIN_SETUP>
Contribution workflow </community/CONTRIBUTING>
Release checklist </delivery/release-checklist-2025-11-03>
Security & supply-chain </security/supply-chain-plan>
```

## Architecture at a glance

See the [documentation architecture](/architecture/documentation-architecture.md) and
[system context](/docs/architecture/ARCHITECTURE_OVERVIEW.md) diagrams for updated component maps.

## Environment & QA

- Use the lightweight runtime image for end users (`Dockerfile`).
- Use `Dockerfile.dev` when you need Node.js, Playwright browsers, or shell tooling inside a containerised dev env.
- Run `TRUNK_SKIP_TRUNK=1 scripts/testing/full.sh` before merging; the script now bootstraps `pytest-xdist`, refreshes coverage,
  and enforces pre-commit with a configurable timeout (`HOTPASS_PRECOMMIT_TIMEOUT`).
- Accessibility and Playwright smoke suites run locally once `npx playwright install --with-deps chromium` has completed.

## Contribution workflow

Follow the [docs/community contributing guide](/community/CONTRIBUTING.md) for doc updates and
[toolchain guide](/development/TOOLCHAIN_SETUP.md) for runtime details. The
[release checklist](/delivery/release-checklist-2025-11-03.md) summarises required CI checks, SBOM generation, and rollback steps.

Escalation: `#hotpass-platform` (engineering), `#hotpass-support` (ops), pager duty escalation documented in
[governance/project-charter.md](/governance/project-charter.md).
