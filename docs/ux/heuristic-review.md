---
title: Streamlit dashboard heuristic review
summary: Findings from a Nielsen heuristic evaluation of the Hotpass Streamlit dashboard.
last_updated: 2025-11-02
---

| Heuristic                                           | Observation                                                                                                           | Impact | Recommendation                                                                     | Owner       | Status      |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ------ | ---------------------------------------------------------------------------------- | ----------- | ----------- |
| Visibility of system status                         | Success and warning banners appear after pipeline run but lack timestamps for context.                                | Medium | Surface last run timestamp and provenance digest in success message.               | Platform    | Planned     |
| Match between system and real world                 | Tab labels align with pipeline concepts; however, data preview lacks column descriptions for compliance stakeholders. | Low    | Add tooltip/description to data preview expander referencing glossary.             | Docs        | Planned     |
| User control and freedom                            | No “cancel run” affordance once execution starts.                                                                     | High   | Add `st.button("⏹️ Cancel")` tied to Prefect cancellation and confirm dialogue.    | Engineering | Backlog     |
| Consistency and standards                           | Sidebar inputs include help text but lack keyboard shortcut hints.                                                    | Low    | Document keyboard navigation tips in help text, ensure focus order matches layout. | Platform    | In progress |
| Error prevention                                    | Output path accepts any string; invalid directories produce runtime exception.                                        | High   | Validate path existence and permissions before execution; show inline error.       | Engineering | Planned     |
| Recognition rather than recall                      | Execution history table sorts by timestamp but lacks filters.                                                         | Medium | Add profile filter chips and search to reduce manual scanning.                     | Platform    | Backlog     |
| Flexibility and efficiency                          | Power users require CLI invocation of last configuration.                                                             | Medium | Provide “Copy CLI command” button with pre-populated flags.                        | Engineering | Planned     |
| Aesthetic and minimalist design                     | Layout uses wide mode but metrics columns can overflow on small screens.                                              | Low    | Introduce responsive layout breakpoints and abbreviate labels.                     | Design      | Backlog     |
| Help users recognize, diagnose, recover from errors | Error banner surfaces stack trace but lacks remediation guidance.                                                     | Medium | Add knowledge base link + recommended next steps derived from exception type.      | Docs        | Planned     |
| Help and documentation                              | No direct link to docs from dashboard.                                                                                | Low    | Add footer link to tutorials/how-to guides.                                        | Docs        | In progress |

## Next actions

- Prioritise high-impact issues (cancel run, output validation) for engineering sprint.
- Collaborate with Docs to add glossary and help links in upcoming release.
- Track remediation progress in `Next_Steps.md` and update this review after each iteration.
