---
title: Explanation — agent system architecture
summary: Understand how Hotpass exposes MCP tools, role policies, and automation helpers for AI assistants.
last_updated: 2025-11-03
---

# Agent system architecture

Hotpass ships an MCP (Model Context Protocol) server so AI assistants such as GitHub Copilot or Codex can operate the pipeline safely. This page explains the moving parts you interact with when you embed automation.

## Components

- **MCP server implementation** — `apps/data-platform/hotpass/mcp/server.py` instantiates `HotpassMCPServer`. The server:
  - Registers CLI-equivalent tools (`hotpass.refine`, `hotpass.enrich`, `hotpass.qa`, `hotpass.setup`, `hotpass.net`, `hotpass.ctx`, `hotpass.env`, `hotpass.aws`, `hotpass.arc`, `hotpass.explain_provenance`, `hotpass.plan.research`, `hotpass.crawl`, `hotpass.pipeline.supervise`, `hotpass.ta.check`).
  - Loads optional plugins from Python entry points so teams can extend the toolset without modifying core code.
  - Applies role-based access control using `RolePolicy`; you can override the default role with `HOTPASS_MCP_DEFAULT_ROLE`.
- **Workflow harness** — `AgentWorkflowHarness` coordinates the `ResearchOrchestrator` and `PipelineSupervisor`. It lets assistants run research plans, schedule crawls, and inspect pipeline snapshots without bypassing governance.
- **Tool discovery** — Assistants call `tools/list` over stdio. The server responds with JSON described by `MCPTool` objects (name, description, JSON schema for inputs).
- **HTTP surface** — `tools.json` mirrors the enabled tooling for REST-esque agents. It exposes endpoints like `run_hotpass_refine` and `get_marquez_lineage` so hosted platforms can call the same operations over HTTPS.

## Role policy

Default roles live in `DEFAULT_ROLE_POLICY`:

| Role | Permissions | Use case |
| ---- | ----------- | -------- |
| `admin` | `*` | Bot operators or CI systems that must call every tool. |
| `operator` | Pipeline verbs (`refine`, `enrich`, `qa`, `setup`, `net`, `ctx`, `env`, `aws`, `arc`, `explain_provenance`, `plan.research`, `crawl`, `pipeline.supervise`, `search.intelligent`, `ta.check`, `agent.workflow`). | Daily operations and release readiness. |
| `researcher` | Research-only verbs (`plan.research`, `search.intelligent`, `crawl`, `pipeline.supervise`, `explain_provenance`). | Analysts running deterministic crawls. |
| `observer` | Read-only verbs (`qa`, `ta.check`, `explain_provenance`). | Viewers who should not mutate state. |

To override:

```bash
export HOTPASS_MCP_DEFAULT_ROLE=observer
uv run python -m hotpass.mcp.server
```

Provide a YAML policy via `HOTPASS_MCP_ROLE_POLICY=/path/to/policy.yaml` when you need custom roles.

## Launching the server

```bash
uv run python -m hotpass.mcp.server
```

The server runs in stdio mode. Use `dolphin-mcp` or Copilot Chat to connect:

```bash
dolphin-mcp list --server hotpass
dolphin-mcp call --server hotpass hotpass.refine input_path=./data output_path=./dist/refined.xlsx profile=aviation archive=true
```

For hosted assistants, mirror this command in `.vscode/mcp.json` or Copilot workspace settings. Ensure you export `HOTPASS_UV_EXTRAS` (for example, `dev orchestration enrichment`) before launching so the server resolves optional features.

## Safety boundaries

- The server refuses to expose tools unless they are registered with an allowed role. Unlisted tools remain inaccessible even if a plugin loads them.
- Network-heavy actions (`hotpass.crawl`, remote enrichment) require environment variables `FEATURE_ENABLE_REMOTE_RESEARCH=1` and `ALLOW_NETWORK_RESEARCH=1`. Leave them unset in restricted environments.
- API keys must be exported as environment variables (`HOTPASS_GEOCODE_API_KEY`, `HOTPASS_ENRICH_API_KEY`) before you start the server. Secrets are not accepted via tool arguments.
- All calls are logged when you set `HOTPASS_MCP_AUDIT_LOG=/path/to/log.jsonl`. Use this in production to capture provenance for compliance reviews.

## Integrating with Codex Cloud or Copilot

1. Follow the cloud recipe in `AGENTS.md` to build the environment, select dependency extras, and configure network allow-lists.
2. Run the MCP server as part of your automation run. For Codex tasks, declare it in `.mcp.json` with `transport: "stdio"` and the same `HOTPASS_UV_EXTRAS` you synced locally.
3. Use the checklist in `AGENTS.md` (“Tool Contract”) to verify that `list_prefect_flows`, `get_marquez_lineage`, and `run_hotpass_refine` remain reachable over HTTPS when required.

The agent architecture keeps human and automated workflows aligned: assistants call the same CLI functionality through strongly-typed tools, while role policies and environment flags enforce the guardrails documented in the governance playbooks.
