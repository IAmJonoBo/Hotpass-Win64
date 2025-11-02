---
title: Developer experience experiments
summary: Targeted experiments to reduce toil and measure SPACE-oriented outcomes.
last_updated: 2025-11-02
---

## Experiment backlog

| #   | Hypothesis                                                                       | Experiment design                                                                                                | Metrics                                                                 | Owner                        | Status                        |
| --- | -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | ---------------------------- | ----------------------------- |
| 1   | Automating environment bootstrap will cut onboarding time by 40%.                | Deliver `ops/idp/bootstrap.py` to configure uv env, Prefect profiles, and secrets. Pilot with two new engineers. | Onboarding duration, first-success rate, survey satisfaction.           | Platform Engineering         | Planned (kick-off 2025-11-05) |
| 2   | Parallelising QA checks via `uvx` will reduce local feedback cycle by 25%.       | Introduce Make target orchestrating lint/type/test in parallel; measure vs sequential baseline.                  | QA loop duration, failure discovery stage.                              | Engineering Productivity     | Planned                       |
| 3   | Backstage golden path templates will remove duplication when creating new flows. | Publish template for Prefect flow + CLI wrapper; track adoption and PR lead time.                                | Template adoption rate, PR cycle time, documentation update compliance. | Developer Productivity Guild | In design                     |
| 4   | Automated compliance evidence export will cut weekly manual effort by 2 hours.   | Extend Prefect flow to emit evidence bundle to object storage and auto-update backlog.                           | Evidence freshness SLAs, manual effort logs.                            | Compliance                   | Scoped                        |
| 5   | SBOM & provenance surfacing inside dashboard reduces incident triage time.       | Add SBOM/provenance widget to dashboard; simulate incident drill.                                                | Incident triage duration, stakeholder satisfaction.                     | Platform + Security          | Pilot scheduled 2025-12-01    |

## Experiment lifecycle

1. Select experiment from backlog aligned to roadmap objectives.
2. Capture baseline metrics inside SPACE dashboard.
3. Implement change via feature flag or IDP template.
4. Observe for two sprints; collect qualitative feedback.
5. Decide: scale, iterate, or retire. Document learnings in DevEx review loop.

## Measurement cadence

- Review experiment metrics monthly in DevEx governance forum (see [review cadence](./review-loop.md)).
- Publish highlights in `docs/metrics/metrics-plan.md` and `docs/roadmap/30-60-90.md`.
- Feed outcomes into quarterly SPACE survey for longitudinal tracking.
