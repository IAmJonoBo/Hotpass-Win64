---
title: Reference — documentation templates
summary: Copy-ready templates for ADRs, RFCs, postmortems, agent prompts, and release notes.
last_updated: 2025-11-03
---

# Documentation templates

Use these templates when you write decision records, prompts, or release notes. Update the snippets in-place so every team produces consistent artefacts.

## Architecture Decision Record (ADR)

```markdown
# {ADR-NNN}: Title

_Status:_ Proposed | Accepted | Superseded by {NNN}
_Date:_ YYYY-MM-DD

## Context

…

## Decision

…

## Consequences

…
```

## RFC

```markdown
# RFC: {concise-title}

## Summary

Problem, proposal, alternatives, impact.

## Motivation & Goals

…

## Detailed Design

APIs, data models, diagrams, migration.

## Security & Privacy

…

## Rollout

Phases, flags, telemetry, rollback.

## Unresolved Questions

…
```

## Release notes

```markdown
# Release {X.Y.Z}

## Highlights

- …

## Changes

- feat: …
- fix: …
- perf: …
- chore: …

## Migrations / Breaking changes

- …
```

## Postmortem

```markdown
# Post-mortem: {incident-title}

- Date / Duration / Severity
- Impact
- Timeline
- Root cause(s)
- What went well / poorly
- Action items (owner, due date)
```

## Agent evaluation

```markdown
# Agent Evaluation Template

- Task definition
- Dataset / scenarios
- Metrics & thresholds
- Observed failure modes
- Follow-ups
```

## Agent prompt

```markdown
# Agent Prompt Template

## Intent

What outcome you want, success criteria.

## System Prompt

…

## User Prompt(s)

…

## Tools & Constraints

Available tools, limits, budgets.

## Eval notes

Edge cases, do-nots, red flags.
```

## Test case

```markdown
# Test Case: {feature-or-bug}

- Preconditions
- Steps
- Expected
- Notes
```

## Threat model

```markdown
# Threat Model Template

- Context diagram link
- Assets & trust zones
- Misuse cases
- Controls & coverage mapping (ASVS)
- Residual risk sign-off
```

These blocks replace the placeholders previously stored under `docs/docs/templates/`. Copy them into new docs or tickets and fill in the sections before you request review.
