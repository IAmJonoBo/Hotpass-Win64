---
title: Dependency and tooling matrix
summary: Ownership, lifecycle, and compliance posture for dependencies.
last_updated: 2025-11-02
---

| Dependency    | Version | Owner       | Lifecycle | Integration points     | License      | Compliance notes                    |
| ------------- | ------- | ----------- | --------- | ---------------------- | ------------ | ----------------------------------- |
| Python        | 3.13    | Platform    | Active    | CLI, Prefect flows     | PSF          | Covered by enterprise Python policy |
| uv            | 0.9.5   | Platform    | Active    | Dependency mgmt, build | MIT          | Documented in TechDocs              |
| Prefect       | 3.4.25  | Engineering | Active    | Orchestration          | Prefect EULA | Requires offline config approval    |
| Streamlit     | 1.40.0  | Platform    | Active    | Dashboard              | Apache-2.0   | Pending accessibility enhancements  |
| Pandas        | 2.3.3   | Engineering | Active    | Data processing        | BSD-3-Clause | Approved                            |
| CycloneDX-BOM | 4.0+    | Security    | Trial     | Supply-chain           | Apache-2.0   | Evaluate signing integration        |
| Mutmut        | 2.4+    | QA          | Trial     | Mutation tests         | MIT          | Monitor runtime impact              |
| Semgrep       | 1.78+   | Security    | Assess    | Static analysis        | LGPL-2.1     | Confirm license obligations         |
| Sigstore      | TBD     | Security    | Assess    | Signing                | Apache-2.0   | Requires OIDC integration           |

## Governance

- Update matrix on dependency upgrades.
- Link to Renovate config for automation context.
- Capture risk acceptance decisions alongside compliance backlog.
