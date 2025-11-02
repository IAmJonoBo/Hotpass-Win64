---
title: Tech radar
summary: Lifecycle governance for tooling used across Hotpass.
last_updated: 2025-11-02
---

## Adopt

| Technology | Domain                  | Rationale                                                   |
| ---------- | ----------------------- | ----------------------------------------------------------- |
| uv         | Build & dependency mgmt | Fast Python package management, reproducible sync.          |
| Prefect 3  | Orchestration           | Production orchestration with observability hooks.          |
| Streamlit  | Dashboards              | Rapid dashboarding for quality signals.                     |
| CycloneDX  | SBOM                    | Industry-standard SBOM format, integrates with policy gate. |

## Trial

| Technology                   | Domain           | Experiment                                            |
| ---------------------------- | ---------------- | ----------------------------------------------------- |
| Mutmut                       | Testing          | Evaluate mutation coverage for core modules.          |
| Playwright + axe-core        | Accessibility    | Browser-based accessibility scans for dashboard.      |
| Sigstore                     | Supply-chain     | Keyless signing for artefacts.                        |
| Model Context Protocol (MCP) | Agent governance | Validate gating of agentic orchestration via Prefect. |

## Assess

| Technology                   | Domain            | Notes                                            |
| ---------------------------- | ----------------- | ------------------------------------------------ |
| Chaos Mesh                   | Chaos engineering | Investigate for Prefect flow disruption testing. |
| Import Linter                | Architecture      | Potential tool for coupling guardrails.          |
| Semgrep Supply-chain ruleset | Security          | Validate coverage for dependency integrity.      |

## Hold

| Technology | Domain         | Reason |
| ---------- | -------------- | ------ | ------------------------------------------------ |
| `curl      | sh` installers | Build  | Replaced with pinned artefacts per roadmap item. |

## Governance process

1. Propose additions/changes via DevEx forum (see [`docs/devex/review-loop.md`](../devex/review-loop.md)).
2. Record lifecycle decision here and in Backstage TechDocs.
3. Update `Next_Steps.md` tasks if migration required.
4. Review radar quarterly alongside roadmap.
