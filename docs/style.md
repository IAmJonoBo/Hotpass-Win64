---
title: Documentation style guide
summary: Conventions for writing Hotpass documentation using the Google Developer Documentation Style Guide.
last_updated: 2025-11-02
---

Hotpass documentation follows the [Google Developer Documentation Style Guide](https://developers.google.com/style). Apply the conventions below when updating or creating content.

## Voice and tone

- Write in the second person (“you”) and use active voice.
- Prefer short sentences and plain language.
- Highlight actions with imperative verbs (“Run”, “Click”, “Configure”).

## Formatting

- Use sentence case for headings.
- Include YAML front matter with `title`, `summary`, and `last_updated`.
- Add fenced code blocks with explicit languages (`bash`, `python`, `yaml`).
- Provide context before code snippets so readers know why they are running a command.

## Links and references

- Use relative links (`../tutorials/quickstart.md`) for internal pages.
- Link to official documentation for external tools (Prefect, uv, Great Expectations).
- Avoid bare URLs—wrap them in Markdown links with descriptive text.

## Accessibility

- Provide alt text for images and screenshots.
- Use ordered lists for sequential steps and unordered lists for collections.
- Avoid tables when a list communicates the information clearly.

## Change management

- Update the [roadmap](./roadmap.md) if your change introduces or completes a workstream.
- Log follow-up tasks in `Next_Steps.md` to keep progress visible.
- Ensure Sphinx builds cleanly with `sphinx-build -n -W` before submitting a pull request.
