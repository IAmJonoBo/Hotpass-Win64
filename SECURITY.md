# Security policy

## Supported versions

| Branch            | Supported | Notes                                    |
| ----------------- | --------- | ---------------------------------------- |
| `main`            | ✅        | Nightly integration branch; security fixes land here first. |
| `release/1.x`     | ✅        | Maintained LTS branch for production deployments. |
| `legacy/0.x`      | ⚠️        | Security fixes only if severity is Critical or High. |

## Reporting a vulnerability

- Email [security@n00tropic.example](mailto:security@n00tropic.example) with proof-of-concept details, affected version/branch, and reproduction steps.
- Include SBOM/provenance artefacts if available to accelerate triage.
- Optionally encrypt your report with our PGP key (`SECURITY-KEYS.md`).
- Expected response: acknowledgement within **2 business days**, initial triage outcome within **5 business days**.

## Stewardship and licensing

- Hotpass source code is published under the Business Source License 1.1 with a commercial option for organisations that need expanded production rights. The steward, n00tropic, maintains the canonical distribution and coordinates commercial support via `security@n00tropic.example`.
- On the defined Change Date the codebase converts to Apache License 2.0, ensuring long-term openness while allowing n00tropic to provide governed, supported releases in the interim.

## Security response process

1. Acknowledge report and create private tracker entry.
2. Assess severity, assign ownership (Security + relevant squad).
3. Develop fix, run full QA + supply-chain suite.
4. Publish advisory and update roadmap/remediation backlog.

### Coordinated disclosure timeline

- **Day 0:** Reporter submits vulnerability. Security team acknowledges within 48 hours.
- **Day 5:** Initial triage complete. Reporter receives severity, affected surface, and planned remediation window.
- **Day 10:** Fix ready for review; quality + supply-chain workflows executed (`Security & Supply Chain` GitHub Action).
- **Day 14:** Coordinated release to supported branches; advisory shared with reporter and published to the security mailing list.
- Timelines may be accelerated for critical issues; we keep reporters informed if additional time is required.

## Disclosure policy

- Responsible disclosure preferred; coordinate release date with reporter.
- Credits provided in advisory unless reporter opts out.
- Non-sensitive fixes batched into monthly security release notes.

## Front-end protections & residual risk

- The Hotpass web UI now performs client-side validation and sanitisation for operator inputs
  (admin endpoint configuration, lineage search) and clamps telemetry feedback to 500 characters
  while stripping control characters. These checks run in addition to server-side validation and
  reject protocols outside HTTP/HTTPS.
- Browser interactions with Prefect and Marquez APIs are throttled via an application-level rate
  limiter that mirrors the platform defaults (30/min Prefect, 20/min Marquez) to reduce the risk of
  client burst traffic exhausting upstream quotas.
- CSRF protection for operator feedback is enforced by requiring a per-session token retrieved from
  `/telemetry/operator-feedback/csrf`; feedback submission is disabled when the token or validation
  context is unavailable.
- **Residual risk:** front-end validation cannot guarantee integrity if an attacker tampers with the
  browser runtime. Server-side enforcement remains authoritative and must stay enabled. Rate limiting
  is best-effort and assumes a cooperative browser; automated clients can still exceed thresholds if
  they bypass the UI. Continue to review telemetry endpoints for abuse-resistant authentication when
  wiring into production data paths.
