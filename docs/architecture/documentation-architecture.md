---
title: Architecture — documentation information architecture
summary: Navigation model that maps Hotpass documentation across overview, in-depth guides, and automation references.
last_updated: 2025-11-18
---

# Documentation information architecture

Hotpass documentation now follows three reader journeys: orientation, implementation, and automation reference. Each journey is
anchored in the Diátaxis framework and backed by dedicated navigation entry points so contributors can keep the library balanced
while readers can jump directly to the right depth.

## Pillars at a glance

| Pillar                         | Intent                                                                                                         | Primary entry points                                                                                                                   |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Overview**                   | Explain what Hotpass is, why it exists, and how the platform fits together.                                    | `explanations/architecture`, `explanations/platform-scope`, `architecture/documentation-architecture`                                  |
| **In-depth guides**            | Provide step-by-step instructions for running pipelines, operating orchestration, and responding to incidents. | Tutorials under `/tutorials/`, how-to guides under `/how-to-guides/`, and operational runbooks under `/operations/`                    |
| **API & automation reference** | Capture CLI verbs, MCP tooling, profile schemas, Smart Import workflows, and governance artefacts.             | `/reference/cli`, `/reference/data-model`, `/reference/smart-import-plan`, `/reference/repo-inventory`, `/governance/`, `/compliance/` |

The front page (`docs/index.md`) surfaces these pillars so that navigation cards, toctrees, and contributor checklists stay in
sync.

## Navigation map

```{mermaid}
mindmap
  root((Hotpass docs))
    Overview
      Architecture overview
      Platform scope
      Data-quality strategy
    In-depth guides
      Tutorials
      How-to guides
      Operations playbooks
      Metrics & retrospectives
    API & automation reference
      CLI & MCP
      Smart Import plan
      Data contracts & schemas
      Governance & compliance
```

Each leaf node maps to a maintained folder. Contributors should treat the mind map as the canonical checklist before adding new
documents: if a node does not exist yet, decide whether the content belongs in an existing pillar or if a new branch is needed.

## Maintenance guardrails

1. **Overview** pages must answer "what" and "why" within two clicks from the index. Keep deep configuration details in the
   reference pillar.
2. **Guides** should link back to at least one reference page so readers can dig deeper without duplicating authoritative
   content.
3. **Reference** material must include the `last_updated` substitution and code pointers so CI and MCP checks can confirm
   freshness.
4. Every new document must be added to a toctree section; the docs CI workflow runs with `-n -W` so orphaned pages fail the
   build once the outstanding warning backlog is cleared.

## Build commands

Use the new make target to preview the docs locally:

```bash
make docs
```

The target runs a nitpicky HTML build followed by `linkcheck`, matching the `docs.yml` workflow. Address warnings before
promoting a change so that the CI backlog can shrink steadily.
