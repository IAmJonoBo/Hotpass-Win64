---
title: Accessibility checklist (WCAG 2.2 AA)
summary: Component-level acceptance criteria to keep the Streamlit dashboard WCAG 2.2 AA compliant.
last_updated: 2025-11-02
---

| Component             | Criteria                                                                                     | WCAG ref            | Status                                                 | Evidence                                                                          |
| --------------------- | -------------------------------------------------------------------------------------------- | ------------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------- |
| Page configuration    | `st.set_page_config` defines language, title, and wide layout.                               | 3.2.4, 2.4.2        | ✅ Configured                                          | `apps/data-platform/hotpass/dashboard.py` lines 41-46                             |
| Sidebar inputs        | Labels, help text, and keyboard focus order documented.                                      | 1.3.1, 2.1.1, 2.4.6 | ⚠️ Help text present, keyboard ordering pending review | `tests/accessibility/test_dashboard_accessibility.py`                             |
| Run button            | Accessible name includes verb; `type="primary"`, `use_container_width=True` for tap targets. | 2.5.5, 2.4.7        | ✅ Verified                                            | Accessibility tests                                                               |
| Spinner               | Provides status message while pipeline executes.                                             | 4.1.3               | ✅ Verified                                            | `apps/data-platform/hotpass/dashboard.py`                                         |
| Success/error banners | Convey status with text and icon; remediation guidance pending.                              | 1.4.1, 3.3.3        | ✅ Guidance added                                      | `tests/test_dashboard.py::test_dashboard_main_runs_pipeline_and_persists_history` |
| Metrics cards         | Use `st.metric` with textual labels; ensure colour not sole indicator.                       | 1.4.1               | ✅ Verified                                            | Manual review                                                                     |
| Dataframe preview     | Provide caption/description; ensure keyboard scroll works.                                   | 1.3.1, 2.1.1        | ✅ Captioned with glossary link                        | `tests/test_dashboard.py::test_dashboard_main_runs_pipeline_and_persists_history` |
| Tabs                  | Tab order follows logical sequence; names match content.                                     | 2.4.1               | ✅ Verified                                            | Accessibility tests                                                               |
| Footer                | Includes docs link and last updated timestamp.                                               | 2.4.5               | ✅ Operations guide linked                             | `tests/test_dashboard.py::test_dashboard_main_runs_pipeline_and_persists_history` |

## Remediation tracker

- Validate keyboard navigation order in sidebar widgets and ensure focus trapping within modal states.
- Add optional high-contrast theme toggle to meet 1.4.11.
