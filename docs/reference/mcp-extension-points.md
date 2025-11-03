---
title: Reference — MCP extension points
summary: Extend the MCP server safely by registering new tools, policies, or orchestration helpers.
last_updated: 2025-11-03
---

# MCP extension points and operational notes

Hotpass exposes its MCP surface as an extensible platform. This reference documents the
supported hooks, guardrails, and quality expectations for additional agent integrations.

## Role-based access control

- **Policy definition** – The server loads a policy from `HOTPASS_MCP_POLICY_FILE`
  (YAML/JSON), `HOTPASS_MCP_POLICY_JSON`, or falls back to the built-in policy. Each
  role declares `allow`, `deny`, `inherits`, and optional `allow_all` flags.
- **Default role** – Override via `HOTPASS_MCP_DEFAULT_ROLE`. Requests may supply a
  role explicitly using the top-level JSON-RPC `role` parameter or the `_role`
  argument inside `tools/call` payloads. The `_role` hint is stripped before the tool
  handler executes, so downstream code never sees RBAC metadata.
- **Tool overrides** – `server.register_tool(..., roles=[...])` restricts a tool to
  the supplied role list. Passing `roles=None` clears overrides, enabling plugin-driven
  updates without mutating the policy file.

## Plugin registration

- **Module hook** – Export `register_mcp_tools(server)` from a module and list it in
  `HOTPASS_MCP_PLUGINS` (comma-separated). The hook receives the live
  `HotpassMCPServer` instance and may register tools or roles.
- **Entry point** – Distribute plugins via packaging by declaring an entry point under
  `hotpass.mcp_tools`. The server loads each entry point, calls it with the server
  instance, and logs failures without aborting startup.
- **Tool registry** – Internally, tools are tracked in an ordered registry. Re-register
  a tool to replace the handler or signature; the public tool list synchronises after
  each registration to keep `tools/list` output consistent.

## Shared orchestrators and supervision

- `ResearchOrchestrator` now exposes lightweight helpers:
  - `intelligent_search(context)` builds enriched search strategies without executing
    the full pipeline.
  - `coordinate_crawl(context, backend)` emits crawl schedules that downstream agents
    can consume incrementally.
- `PipelineSupervisor` analyses pipeline snapshots (runs, tasks, metrics) and returns
  actionable recommendations. Provide payloads shaped like the `PipelineSnapshot`
  dataclass or supply instances directly.
- `AgentWorkflowHarness` combines both surfaces so agents can simulate search → crawl
  → supervision workflows offline. Pass an optional `PipelineSnapshot` mapping to test
  supervision heuristics before promoting orchestration changes.

## Operational guidance

- Prefer deterministic runs first. Tools that mutate infrastructure (`hotpass.setup`,
  `hotpass.net`, etc.) remain available only to operator roles by default.
- Audit logs live under the orchestrator cache root (`.hotpass/mcp-audit.log` by
  default). Review these logs when debugging agent behaviour or verifying RBAC.
- New tools should include descriptive `input_schema` metadata—downstream MCP clients
  rely on schema discovery to surface affordances in chat interfaces.
- Extend the automated test suite alongside new tooling. Unit tests exist for RBAC
  policy evaluation, search/crawl orchestration, pipeline supervision, and the agent
  workflow harness; mirror those patterns for additional orchestration features.
