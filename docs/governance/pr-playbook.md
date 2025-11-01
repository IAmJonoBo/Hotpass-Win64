---
title: Pull request playbook
summary: Expectations, quality gates, and waiver process for Hotpass pull requests.
last_updated: 2025-12-03
---

## Checklist

1. Reference roadmap item or issue.
2. Update documentation (Diátaxis) and `Next_Steps.md`.
3. Run QA suite locally (tests, lint, type, security, secrets, build, accessibility, mutation, fitness functions).
4. Ensure commits follow Conventional Commits; the `commitlint` workflow blocks merges on violations.
5. Confirm Prefect configuration changes respect concurrency guardrails (e.g. `orchestrator.backfill.concurrency_limit`, deployment work pools) and document overrides or sequential fallbacks.
6. Validate post-deploy observability checks by referencing the lineage and Prefect runbooks (`docs/operations/lineage-smoke-tests.md`, `docs/operations/prefect-backfill-guardrails.md`) and note OTEL exporter status in the PR description.
7. Attach artefacts (SBOM, provenance, accessibility report) as PR uploads if relevant.
8. Tag code owners (`@platform-eng`, `@security`, `@docs`) per affected areas and confirm label automation applied the correct taxonomy (`type:*`, `scope:*`, `prefect`, `uv`).

## Quality gate waivers

| Gate          | Owner       | Waiver conditions                                              | Max duration |
| ------------- | ----------- | -------------------------------------------------------------- | ------------ |
| Tests         | Engineering | Only for flaky tests with mitigation issue filed.              | 5 days       |
| Accessibility | Platform    | Allowed for feature flagged UI with remediation scheduled.     | 7 days       |
| Mutation      | QA          | Permitted if coverage tool unstable; rerun within next sprint. | 7 days       |
| Supply-chain  | Security    | Only if upstream CycloneDX outage; require manual SBOM in PR.  | 3 days       |

Waivers require documented approval comment and entry in `Next_Steps.md` Quality Gates with expiry date.

## Review workflow

- **Author** ensures PR template completed, attaches test evidence.
- **Reviewers** inspect code, docs, and artefacts; confirm automation success (commitlint, labeler, Release Drafter status).
- **Security reviewer** validates supply-chain outputs and policy evaluations.
- **Docs reviewer** ensures TechDocs/Diátaxis updates align with style guide.

## Automation guardrails

- **Commit message linting**: `commitlint` workflow enforces Conventional Commits on every PR update. Fix failures by amending commits before requesting review.
- **PR labelling**: `pr-labeler` workflow synchronises labels with file patterns and branch prefixes. Manually adjust labels if automation misses an edge case.
- **Release notes**: `release-drafter` workflow assembles notes from Conventional Commit-aligned labels. Keep the `type:*`, `scope:*`, `prefect`, and `uv` labels accurate so the release outline remains trustworthy. Use `skip-changelog` for build-only noise.

## Rollback procedure

- Revert commit via GitHub UI or CLI (`git revert <sha>`).
- Restore previous release artefacts (dist, SBOM, provenance) from GitHub Releases.
- Update `Next_Steps.md` with rollback summary and follow-up tasks.
- Notify stakeholders in `#hotpass` Slack channel with remediation ETA.

## Prefect deployments

- **Concurrency guardrails**: Treat `orchestrator.backfill.concurrency_limit` and Prefect work-pool limits as part of the change control process. Setting the limit to `0` forces sequential execution in lower environments and is acceptable when documenting the rationale in the PR description.
- **Ephemeral API avoidance**: If Prefect concurrency slots cannot be acquired (for example, CI without an API server), the flows fall back to synchronous execution and emit a warning. Surface the warning in PR notes when observed.
- **Configuration traceability**: Changes to Prefect deployments (schedules, work pools, concurrency keys) must be reflected in the Diátaxis how-to guide and referenced in `Next_Steps.md` deliverables so operations can audit the rollout.
