---
title: Hotpass documentation
summary: Learn how to install, operate, and extend the Hotpass data refinement platform.
owner: n00tropic
last_updated: 2025-11-03
---

# Hotpass documentation

Welcome to the Hotpass knowledge base. Start with the section that matches your goal, then explore the deeper references.

```{toctree}
:maxdepth: 1
:caption: Start here

/explanations/developer-hub
/how-to-guides/operator-runbook
```

## Diátaxis navigation

```{toctree}
:maxdepth: 2
:caption: Tutorials

/tutorials/index
```

```{toctree}
:maxdepth: 2
:caption: How-to guides

/how-to-guides/index
```

```{toctree}
:maxdepth: 2
:caption: Reference

/reference/index
```

```{toctree}
:maxdepth: 2
:caption: Explanations

/explanations/index
```

## Need a quick refresher?

- Check `docs/how-to-guides/qa-checklist.md` before you merge or cut a release.
- Use `docs/reference/cli.md` when you need canonical CLI syntax and examples.
- Explore `docs/explanations/ai/guardrails.md` if you run Hotpass through Codex or Copilot.

For lineage and provenance insight, launch the [Marquez lineage UI](observability/marquez.md) through `uv run hotpass net up` and pair the output with [Data Docs](reference/data-docs.md) while triaging validation issues.
