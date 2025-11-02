---
title: How-to — broker agentic runs with Prefect
summary: Configure Model Context Protocol policies and Prefect tasks to approve or deny agent-triggered Hotpass runs.
last_updated: 2025-11-02
---

This guide explains how to use the new Prefect tasks and MCP configuration files to control autonomous agents that want to run the Hotpass refinement pipeline.

## 1. Configure MCP server and client policies

The prototype policies live in [`ops/agents/`](../../ops/agents/README.md):

1. Review `mcp_server.yaml` and update the allowlisted tools, repositories, and Prefect deployments to match your environment.
2. Adjust approval routing. Operator and reviewer roles require manual approval in the example policy; analysts are auto-approved.
3. Point the Prefect worker to the policy by exporting `HOTPASS_AGENT_POLICY_PATH=/path/to/mcp_server.yaml` before starting the agent-aware work pool.
4. Distribute `mcp_client.yaml` to agent operators so the correct role and broker endpoint are presented with each request.

> ℹ️ Agents may call infrastructure helpers (`hotpass.setup`, `hotpass.net`, `hotpass.ctx`, `hotpass.env`, `hotpass.aws`, `hotpass.arc`) directly via MCP. Update your policy files to grant access to these tools when staging automation should run unattended.

## 2. Enable Prefect runtime for agent gating

Set `HOTPASS_ENABLE_PREFECT_RUNTIME=1` in the environment and ensure the orchestration extras are installed (`uv sync --extra orchestration`). The `hotpass.orchestration` module now exposes:

- `evaluate_agent_request` — validates the request against the tool policy and optional manual approval decision.
- `log_agent_action` — records audit entries to Prefect logs and optional sinks.
- `broker_agent_run` — composes the flow: validate the request, run the pipeline, and log both success and denial events.

Example usage inside a Prefect flow:

```python
from hotpass.orchestration import (
    AgenticRequest,
    AgentToolPolicy,
    broker_agent_run,
)

@flow
def agent_entrypoint(request: dict):
    policy = AgentToolPolicy(
        allowed_tools_by_role={"operator": {"prefect"}, "analyst": {"prefect", "github"}},
        auto_approved_roles={"analyst"},
    )
    agent_request = AgenticRequest(**request)
    return broker_agent_run(agent_request, policy)
```

## 3. Capture audit trails

`broker_agent_run` writes structured `AgentAuditRecord` entries. Provide a mutable sequence (for example, a list or a custom log writer) via the `log_sink` argument to persist records to disk or an evidence store:

```python
audit_log: list[AgentAuditRecord] = []
summary = broker_agent_run(agent_request, policy, log_sink=audit_log)
```

Each record captures the decision (`approved`, `denied`, `executed`, or `failed`), approver identity, timestamp, and any result metadata such as the pipeline summary payload. Use this data to back POPIA audit requirements and roadmap quality gates.

## 4. Simulate approvals in tests

The regression suite includes [`tests/test_agentic_orchestration.py`](../../tests/test_agentic_orchestration.py), which demonstrates how to:

- Deny requests when a role attempts to use an unlisted tool.
- Enforce manual approvals for privileged roles.
- Approve and execute a run while capturing audit entries.

Use these patterns when adding new agent roles or tools to ensure the gating logic and audit logging remain covered.
