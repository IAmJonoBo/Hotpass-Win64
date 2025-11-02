---
title: Deployment notes and feature toggles
summary: Rollback considerations and toggles for recent automation.
last_updated: 2025-11-02
---

# Deployment notes and feature toggles

| Change                       | Toggle                                       | Rollback                                                                   | Notes                                                                    |
| ---------------------------- | -------------------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Accessibility pytest job     | `A11Y_CHECKS_ENABLED` env var (default true) | Disable job via workflow input; revert tests if causing blocking failures. | Requires Streamlit stub; no external services.                           |
| Mutation testing job         | `MUTATION_CHECKS_ENABLED` env var (future)   | Temporarily skip job by toggling workflow dispatch input.                  | Monitor runtime; adjust targets in `ops/qa/run_mutation_tests.py`.       |
| Supply-chain SBOM/provenance | `SUPPLY_CHAIN_ENFORCED` env var (future)     | Remove job from workflow; ensure manual SBOM attached before merging.      | Policy evaluation uses Python shim; extend with Sigstore when available. |
| Semgrep static analysis      | `SEMgrep_SUPPRESS` label (manual)            | Add waiver comment referencing issue; rerun job after remediation.         | Keep config pinned to `--config=auto`; adjust when custom rules added.   |
| Fitness functions script     | None (always on)                             | Update thresholds or skip specific check by editing script (requires PR).  | Document exceptions in `Next_Steps.md`.                                  |

Maintain this table as new automation lands to keep rollback mechanics discoverable.
