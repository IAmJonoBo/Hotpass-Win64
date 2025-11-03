# Hotpass documentation workspace

Hotpass uses a Diátaxis structure so you can land on the right content quickly:

- **Tutorials** introduce the pipeline end to end (`docs/tutorials/`).
- **How-to guides** solve task-focused problems (`docs/how-to-guides/`).
- **Reference** topics capture canonical definitions, CLI/MCP details, policies, and governance records (`docs/reference/`).
- **Explanations** provide architecture, strategy, and rationale (`docs/explanations/`).

## Build the site locally

```bash
uv run sphinx-build -n -W -b html docs docs/_build/html
```

Treat warnings as failures; the docs CI workflow runs the same command. Use `make docs LINKCHECK=1` if you also want to run the link checker.

## Contribute effectively

1. Add or update front matter (`title`, `summary`, `last_updated`) for every Markdown/MyST file.
2. Keep examples grounded in reality—capture fresh CLI output (for example, `uv run hotpass --help`) before you update snippets.
3. Regenerate diagrams when flows change. Prefer Mermaid fenced blocks so diagrams stay version controlled.
4. Run `docs/how-to-guides/qa-checklist.md` before you open a pull request and attach artefacts to the PR description.

Need an orientation? Start with `docs/index.md` or the developer hub at `docs/explanations/developer-hub.md`.
