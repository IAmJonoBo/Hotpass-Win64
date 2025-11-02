---
title: Accessibility testing approach
summary: Automated and manual accessibility testing strategy integrated into CI workflows.
last_updated: 2025-11-02
---

## Automated checks

| Layer                        | Tooling                                             | Command                                                                             | Output                                    |
| ---------------------------- | --------------------------------------------------- | ----------------------------------------------------------------------------------- | ----------------------------------------- |
| Component semantics          | Pytest + Streamlit shim verifying labels/help text. | `uv run pytest -m accessibility tests/accessibility`                                | Pass/fail, pytest report.                 |
| Browser automation (phase 2) | Playwright + axe-core via `axe-playwright-python`.  | `uv run python ops/accessibility/run_browser_checks.py --url http://localhost:8501` | JSON axe violations uploaded as artifact. |
| Documentation accessibility  | `pa11y-ci` against TechDocs output.                 | `pa11y-ci --config pa11y.config.json` (planned)                                     | HTML/CSV violation summary.               |

The repository currently ships semantic checks via pytest (see [`tests/accessibility/test_dashboard_accessibility.py`](../../tests/accessibility/test_dashboard_accessibility.py)). Browser-based axe scans are staged for enablement after Streamlit hosting pipeline is automated.

## Manual verification

- Quarterly heuristics review (see [heuristic review](./heuristic-review.md)).
- Assistive technology spot-checks with NVDA/VoiceOver following new feature releases.
- Colour contrast validation using Stark or Chrome DevTools.

## CI integration

- `.github/workflows/process-data.yml` includes an `accessibility` job running the pytest marker.
- Future enhancement: add Playwright container step to launch Streamlit preview and execute axe scans; gate merges on zero critical violations.
- Accessibility report artefacts stored under `dist/accessibility/` for traceability.

## Issue triage

1. Record violation details (selector, rule, screenshot) in issue tracker using accessibility template.
2. Categorise severity (blocker, critical, moderate, minor) and assign owner.
3. Update checklist status and remediation tracker once resolved.

## References

- [WCAG 2.2 quick reference](https://www.w3.org/WAI/WCAG22/quickref/)
- [Streamlit accessibility guide](https://docs.streamlit.io/library/advanced-features/accessibility)
