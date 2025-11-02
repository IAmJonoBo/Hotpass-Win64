---
title: Assert-free pytest patterns
summary: Maintain Bandit compliance without sacrificing test clarity
last_updated: 2025-11-02
---

Bandit runs as part of the Hotpass quality gates and raises finding **B101** when tests rely on bare `assert` statements.
While Bandit allows waivers via `# nosec`, we prefer to keep tests compliant by using explicit failure helpers. This
section documents the accepted approach so regressions do not creep back in when adding or updating tests.

## Why we avoid bare `assert`

- Bandit treats bare `assert` as a security smell because optimisations can strip them, altering test behaviour.
- Maintaining a shared pattern ensures new contributors see consistent expectations across the suite.
- Aligns with our security review guidelines that discourage suppressing Bandit rules unless risk-assessed.

## Approved pattern: `expect`

Use the helper defined in `tests/test_lineage.py` whenever you need to express assertions without direct `assert`
statements:

```python
from hotpass import lineage
import pytest


def expect(condition: bool, message: str) -> None:
    """Fail the test with a descriptive message when condition is false."""

    if not condition:
        pytest.fail(message)
```

With this helper, test expectations are recorded as calls to `expect`, which still feel declarative but ensure Bandit sees
an explicit failure path. Example usage:

```python
expect(dataset.eventType == _StubRunState.START, "First event should signal a START state.")
```

Keep messages concise but descriptive so failures remain actionable.

## Migration checklist

1. Replace `assert <condition>` with `expect(<condition>, "reason")`.
2. Prefer deriving the message from the user-visible behaviour under test.
3. For multi-condition flows, use multiple `expect` calls rather than combining boolean logic.
4. Ensure your test module imports `pytest` so `pytest.fail` is available.
5. Re-run `uv run bandit -r <changed-files>` to verify no B101 finding slips through.

## When exceptions are acceptable

The `expect` helper is the default, but these patterns remain acceptable without additional wrappers:

- `pytest.raises` context managers to assert exception types and messages.
- `pytest.mark.parametrize` combined with `expect` inside the parametrised test body.
- `pytest.approx` for numeric comparisons, provided the final check still flows through `expect`.

If you believe a bare `assert` is required (for example, interacting with third-party assertion helpers), discuss it with
the maintainers and document the decision in the test module to avoid accidental edits later.

## Property-based coverage expectations

Hotpass exercises critical pipeline behaviours with [Hypothesis](https://hypothesis.readthedocs.io/) so edge cases stay covered
without maintaining an ever-growing set of fixtures. New suites should follow these guardrails:

- Scope property tests to directories that own the behaviour. The pipeline property suite (`tests/pipeline/test_pipeline_properties.py`)
  verifies date parsing, missing column handling, and deterministic runs; the formatting property suite (`tests/formatting/test_formatting_properties.py`)
  guards encoding and optional column behaviour.
- Keep runs fast. Constrain `max_examples` and disable Hypothesis deadlines when tests interact with disk or Excel writers so
  `uv run qa` stays responsive. Aim for sub-minute execution across the property suites.
- Inject deterministic hooks when touching time- or randomness-sensitive code. The pipeline configuration exposes
  `PipelineRuntimeHooks` and a `random_seed` field so tests can freeze clocks and RNG state without monkeypatching globals.
- Prefer shared helpers such as `expect(...)` for readable failures while keeping Bandit happy.

Document new property suites in the relevant module README or how-to guide. The testing gate expects property coverage for
encodings, date formats, missing columns, and idempotent pipeline behaviour going forward.

## Quality gate reminder

Bandit is wired into the `process-data` workflow. Local verification mirrors CI:

```bash
uv run bandit -r apps/data-platform/hotpass/lineage.py tests/test_lineage.py
```

Expand the target paths to cover your modified files before committing. This keeps the assert-free contract enforceable and
prevents regressions once the helper pattern becomes ubiquitous across the test suite.
