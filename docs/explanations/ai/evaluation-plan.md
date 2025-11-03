---
title: Explanation — AI evaluation plan
summary: Metrics, datasets, and automation hooks used to evaluate Hotpass AI workflows.
last_updated: 2025-11-03
---

# AI evaluation plan

This evaluation plan keeps Codex and Copilot workflows trustworthy as you extend Hotpass automation.

## Metrics

| Metric | Description | Source |
| ------ | ----------- | ------ |
| Task success rate | Percentage of scripted evaluations that finish without manual intervention. | Codex replay harness (`ops/agents/mcp_server.yaml`, `AgentWorkflowHarness`). |
| Regression delta | Comparison of task success between the latest commit and the baseline stored in `dist/quality-gates/history.ndjson`. | `python ops/quality/ta_history_report.py --json`. |
| Safety violations | Count of blocked tool calls (policy denies, missing intent, network disabled). | MCP audit log (`HOTPASS_MCP_AUDIT_LOG`). |
| Latency | Duration from tool request to completion (P95). | Audit log timestamps or the `trace_operation` helper in `hotpass.observability`. |

## Datasets and fixtures

- Deterministic enrichment fixtures under `dist/quality-gates/qg3-enrichment/`.
- Synthetic research plans in `tests/fixtures/research/` feed the `hotpass.plan.research` tool.
- CLI golden outputs in `tests/fixtures/cli/` back the expectation tests for `hotpass overview` and `hotpass --help`.

Refresh fixtures by running:

```bash
uv run python ops/quality/refresh_fixtures.py
```

(Create this script if you add new fixtures; current fixtures are static.)

## Protocol

1. **Preflight** — run `make qa-full` and `uv run pytest tests/cli/test_quality_gates.py -k QG5` to ensure documentation and tooling stay in sync.
2. **Offline evaluation** — replay the scripted Codex sessions:

   ```bash
   uv run python ops/agents/replay_codex_sessions.py --output dist/evals/codex.json
   ```

   Record task success, failure reasons, and tool invocations.

3. **Online spot checks** — trigger the MCP server locally and run `/call hotpass.refine ...` via `dolphin-mcp`. Capture latency and any policy denials.
4. **Analysis** — compare `dist/evals/codex.json` with the latest `dist/quality-gates/history.ndjson` to spot regressions. Update the history file using `python ops/quality/ta_history_report.py --json`.
5. **Sign-off** — document outcomes in `Next_Steps_Log.md`, including any mitigations for observed regressions.

## Automation

- Add a scheduled GitHub Action that runs the replay script nightly and uploads the JSON artefact. Flag runs where task success drops below 95% or safety violations increase week-over-week.
- Publish the metrics to your observability stack by instrumenting the replay script with `hotpass.observability.get_pipeline_metrics()`.

## Ownership

- AI steward: ensures role policies and guardrails remain accurate.
- Platform engineering: maintains the MCP server and tool definitions.
- Docs team: keeps `AGENTS.md` and this evaluation plan current.

Update this plan whenever you introduce a new MCP tool, change the Codex checklist, or expand the evaluation dataset.
