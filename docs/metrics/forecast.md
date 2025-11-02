---
title: Metrics forecast
summary: Forecasted impact of DevEx, security, and UX initiatives on key metrics.
last_updated: 2025-11-02
---

| Metric                          | Baseline | 30-day forecast | 60-day forecast | 90-day forecast | Driver                                                    |
| ------------------------------- | -------- | --------------- | --------------- | --------------- | --------------------------------------------------------- |
| Deployment frequency (monthly)  | 8        | 10              | 12              | 14              | Automation of environment bootstrap + Backstage templates |
| Lead time for changes           | 2.5 days | 2.2 days        | 2.0 days        | 1.8 days        | Mutation tests + improved QA parallelism                  |
| Change failure rate             | 12%      | 10%             | 9%              | 7%              | Contract tests, supply-chain policy gates                 |
| MTTR                            | 6h       | 5h              | 4h              | 3.5h            | Provenance visibility, DevEx review cadence               |
| SPACE satisfaction              | 3.6/5    | 3.8/5           | 4.0/5           | 4.1/5           | Experiments + governance rituals                          |
| Accessibility issues (critical) | 4        | 2               | 1               | 0               | Automated accessibility job + heuristics remediation      |

## Assumptions

- Team capacity sustained at current headcount.
- Sigstore integration delivered by day 90 to unlock full supply-chain benefits.
- Compliance automation reduces manual toil by 30% within 90 days.

## Monitoring

- Publish forecasts alongside actuals in DevEx quarterly report.
- Adjust plan if variance >10% for two consecutive months.
