"""Hotpass MCP (Model Context Protocol) server implementation.

This module implements an MCP stdio server that exposes Hotpass operations
as tools that can be called by AI assistants like GitHub Copilot and Codex.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import sys
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

import pandas as pd

from hotpass.config import IndustryProfile, get_default_profile, load_industry_profile
from hotpass.mcp.access import RoleDefinition, RolePolicy
from hotpass.mcp.harness import AgentWorkflowHarness
from hotpass.pipeline_supervision import PipelineSnapshot, PipelineSupervisor
from hotpass.research import ResearchContext, ResearchOrchestrator

try:  # pragma: no cover - optional dependency for policy overrides
    import yaml
except Exception:  # pragma: no cover - PyYAML may be absent
    yaml = None  # type: ignore[assignment]

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """Represents an MCP tool definition."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class MCPRequest:
    """Represents an MCP request."""

    method: str
    params: dict[str, Any]
    id: int | str | None = None


@dataclass
class MCPResponse:
    """Represents an MCP response."""

    result: Any = None
    error: dict[str, Any] | None = None
    id: int | str | None = None


ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(slots=True)
class RegisteredTool:
    """Internal representation of a registered MCP tool."""

    definition: MCPTool
    handler: ToolHandler
    roles: frozenset[str] | None = None


DEFAULT_ROLE_POLICY: Mapping[str, object] = {
    "roles": {
        "admin": {
            "description": "Full access to all MCP tools",
            "allow": ["*"],
        },
        "operator": {
            "description": "Operate pipelines and infrastructure",
            "inherits": ["observer"],
            "allow": [
                "hotpass.refine",
                "hotpass.enrich",
                "hotpass.qa",
                "hotpass.setup",
                "hotpass.net",
                "hotpass.ctx",
                "hotpass.env",
                "hotpass.aws",
                "hotpass.arc",
                "hotpass.explain_provenance",
                "hotpass.plan.research",
                "hotpass.crawl",
                "hotpass.crawl.coordinate",
                "hotpass.search.intelligent",
                "hotpass.pipeline.supervise",
                "hotpass.ta.check",
                "hotpass.agent.workflow",
            ],
        },
        "researcher": {
            "description": "Plan and execute research flows",
            "inherits": ["observer"],
            "allow": [
                "hotpass.plan.research",
                "hotpass.search.intelligent",
                "hotpass.crawl",
                "hotpass.crawl.coordinate",
                "hotpass.pipeline.supervise",
                "hotpass.explain_provenance",
            ],
        },
        "observer": {
            "description": "Read-only tooling",
            "allow": [
                "hotpass.qa",
                "hotpass.ta.check",
                "hotpass.explain_provenance",
            ],
        },
    },
    "default_role": "operator",
}


class HotpassMCPServer:
    """MCP stdio server for Hotpass operations."""

    def __init__(self) -> None:
        """Initialize the MCP server."""

        self._tool_registry: OrderedDict[str, RegisteredTool] = OrderedDict()
        self.tools: list[MCPTool] = []
        self._research_orchestrator = ResearchOrchestrator()
        self._pipeline_supervisor = PipelineSupervisor()
        self._workflow_harness = AgentWorkflowHarness(
            self._research_orchestrator, self._pipeline_supervisor
        )
        self._default_profile_paths = self._determine_profile_paths()

        policy_payload = self._load_policy_payload()
        default_role = os.getenv("HOTPASS_MCP_DEFAULT_ROLE")
        self.role_policy = RolePolicy.from_payload(policy_payload, default_role)

        self._register_tools()
        self._load_plugins()

        logger.info("Initialized Hotpass MCP server with %s tools", len(self.tools))

    def register_tool(
        self,
        tool: MCPTool,
        handler: ToolHandler,
        *,
        roles: Sequence[str] | None = None,
    ) -> None:
        """Register a tool and optionally constrain the roles that may call it."""

        permitted_roles = tuple(role for role in (roles or ()) if role in self.role_policy.roles)
        registered = RegisteredTool(
            tool,
            handler,
            frozenset(permitted_roles) or None,
        )
        self._tool_registry[tool.name] = registered
        self.role_policy.register_tool_override(
            tool.name, permitted_roles if permitted_roles else None
        )
        self._sync_tool_index()

    def _determine_profile_paths(self) -> tuple[str, ...]:
        """Resolve default profile search paths for CLI commands."""

        candidates: list[Path] = []
        env_sources = (
            os.getenv("HOTPASS_MCP_PROFILE_PATHS"),
            os.getenv("HOTPASS_PROFILE_PATHS"),
        )
        for source in env_sources:
            if not source:
                continue
            for raw in source.split(os.pathsep):
                value = raw.strip()
                if not value:
                    continue
                candidates.append(Path(value).expanduser())

        candidates.extend(
            [
                Path(__file__).resolve().parents[1] / "profiles",
                Path.cwd() / "profiles",
                Path.cwd() / "config" / "profiles",
            ]
        )

        resolved: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            try:
                path = candidate.resolve()
            except FileNotFoundError:
                continue
            text = str(path)
            if text in seen or not path.exists():
                continue
            seen.add(text)
            resolved.append(text)
        return tuple(resolved)

    def _normalise_profile_paths(self, supplied: Any) -> tuple[str, ...]:
        """Normalise caller supplied profile search paths."""

        collected: list[str] = []
        if isinstance(supplied, str):
            candidate = supplied.strip()
            if candidate:
                collected.append(candidate)
        elif isinstance(supplied, Sequence):
            for item in supplied:
                if isinstance(item, str):
                    candidate = item.strip()
                    if candidate:
                        collected.append(candidate)

        if not collected:
            return self._default_profile_paths

        normalised: list[str] = []
        seen: set[str] = set()
        for value in (*collected, *self._default_profile_paths):
            path = Path(value).expanduser()
            try:
                resolved = str(path.resolve())
            except FileNotFoundError:
                continue
            if resolved in seen or not Path(resolved).exists():
                continue
            seen.add(resolved)
            normalised.append(resolved)
        return tuple(normalised)

    def register_role(self, definition: RoleDefinition) -> None:
        """Register or override a role definition."""

        self.role_policy.roles[definition.name] = definition

    def _sync_tool_index(self) -> None:
        """Synchronise the externally-visible tool list with the registry."""

        self.tools = [entry.definition for entry in self._tool_registry.values()]

    def _register_tools(self) -> None:
        """Register all available MCP tools."""

        self.register_tool(
            MCPTool(
                name="hotpass.refine",
                description="Run the Hotpass refinement pipeline to clean and normalize data",
                input_schema={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": (
                                "Path to input directory or file containing data to refine"
                            ),
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Path where the refined output should be written",
                        },
                        "profile": {
                            "type": "string",
                            "description": "Industry profile to use (e.g., 'aviation', 'generic')",
                            "default": "generic",
                        },
                        "archive": {
                            "type": "boolean",
                            "description": "Whether to create an archive of the refined output",
                            "default": False,
                        },
                        "profile_search_path": {
                            "oneOf": [
                                {"type": "string"},
                                {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            ],
                            "description": (
                                "Additional directories to search for named profiles "
                                "(defaults to bundled profiles)"
                            ),
                        },
                    },
                    "required": ["input_path", "output_path"],
                },
            ),
            self._run_refine,
        )

        self.register_tool(
            MCPTool(
                name="hotpass.enrich",
                description="Enrich refined data with deterministic and optional network sources",
                input_schema={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Path to the refined input file",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Path where the enriched output should be written",
                        },
                        "profile": {
                            "type": "string",
                            "description": "Industry profile to use",
                            "default": "generic",
                        },
                        "allow_network": {
                            "type": "boolean",
                            "description": "Whether to allow network-based enrichment",
                            "default": False,
                        },
                        "profile_search_path": {
                            "oneOf": [
                                {"type": "string"},
                                {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            ],
                            "description": (
                                "Additional directories to search for named profiles "
                                "(defaults to bundled profiles)"
                            ),
                        },
                    },
                    "required": ["input_path", "output_path"],
                },
            ),
            self._run_enrich,
        )

        self.register_tool(
            MCPTool(
                name="hotpass.qa",
                description="Run quality assurance checks and validation",
                input_schema={
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "enum": [
                                "all",
                                "cli",
                                "contracts",
                                "docs",
                                "profiles",
                                "ta",
                                "fitness",
                                "data-quality",
                            ],
                            "description": "Which QA checks to run",
                            "default": "all",
                        }
                    },
                },
            ),
            self._run_qa,
        )

        self.register_tool(
            MCPTool(
                name="hotpass.explain_provenance",
                description="Explain data provenance for a specific row or dataset",
                input_schema={
                    "type": "object",
                    "properties": {
                        "row_id": {
                            "type": "string",
                            "description": "ID of the row to explain provenance for",
                        },
                        "dataset_path": {
                            "type": "string",
                            "description": "Path to the dataset file",
                        },
                    },
                    "required": ["row_id", "dataset_path"],
                },
            ),
            self._explain_provenance,
        )

        self.register_tool(
            MCPTool(
                name="hotpass.setup",
                description="Run the Hotpass guided setup wizard (dry-run or execute)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "preset": {
                            "type": "string",
                            "enum": ["staging", "local"],
                            "default": "staging",
                        },
                        "extras": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Additional uv extras passed via --extras",
                        },
                        "host": {
                            "type": "string",
                            "description": "Bastion host or SSM instance for tunnels",
                        },
                        "via": {
                            "type": "string",
                            "enum": ["ssh-bastion", "ssm"],
                            "description": "Tunnel mechanism",
                        },
                        "label": {
                            "type": "string",
                            "description": "Label recorded for the tunnel session",
                        },
                        "skip_steps": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": [
                                    "deps",
                                    "prereqs",
                                    "tunnels",
                                    "aws",
                                    "ctx",
                                    "env",
                                    "arc",
                                ],
                            },
                        },
                        "aws_profile": {"type": "string"},
                        "aws_region": {"type": "string"},
                        "eks_cluster": {"type": "string"},
                        "kube_context": {"type": "string"},
                        "namespace": {"type": "string"},
                        "prefect_profile": {"type": "string"},
                        "prefect_url": {"type": "string"},
                        "env_target": {"type": "string"},
                        "allow_network": {"type": "boolean", "default": False},
                        "force_env": {"type": "boolean", "default": False},
                        "arc_owner": {"type": "string"},
                        "arc_repository": {"type": "string"},
                        "arc_scale_set": {"type": "string"},
                        "arc_namespace": {"type": "string"},
                        "arc_snapshot": {"type": "string"},
                        "dry_run": {"type": "boolean", "default": True},
                        "execute": {"type": "boolean", "default": False},
                        "assume_yes": {"type": "boolean", "default": True},
                    },
                },
            ),
            self._run_setup,
        )

        self.register_tool(
            MCPTool(
                name="hotpass.net",
                description="Manage SSH/SSM tunnels via the hotpass net command",
                input_schema={
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["up", "down", "status"],
                            "description": "net subcommand to execute",
                        },
                        "via": {
                            "type": "string",
                            "enum": ["ssh-bastion", "ssm"],
                            "description": "Tunnel mechanism for 'up'",
                        },
                        "host": {"type": "string"},
                        "label": {"type": "string"},
                        "all": {"type": "boolean"},
                        "detach": {"type": "boolean", "default": True},
                        "auto_port": {"type": "boolean"},
                        "prefect_port": {"type": "integer"},
                        "marquez_port": {"type": "integer"},
                        "no_marquez": {"type": "boolean"},
                        "dry_run": {"type": "boolean", "default": False},
                    },
                    "required": ["action"],
                },
            ),
            self._run_net,
        )

        self.register_tool(
            MCPTool(
                name="hotpass.ctx",
                description="Bootstrap or list Prefect/Kubernetes contexts",
                input_schema={
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["init", "list"],
                            "default": "init",
                        },
                        "prefect_profile": {"type": "string"},
                        "prefect_url": {"type": "string"},
                        "eks_cluster": {"type": "string"},
                        "kube_context": {"type": "string"},
                        "namespace": {"type": "string"},
                        "no_prefect": {"type": "boolean"},
                        "no_kube": {"type": "boolean"},
                        "dry_run": {"type": "boolean", "default": False},
                    },
                },
            ),
            self._run_ctx,
        )

        self.register_tool(
            MCPTool(
                name="hotpass.env",
                description="Generate .env files aligned with current tunnels/contexts",
                input_schema={
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Environment name (produces .env.<target>)",
                            "default": "staging",
                        },
                        "prefect_url": {"type": "string"},
                        "openlineage_url": {"type": "string"},
                        "allow_network": {"type": "boolean", "default": False},
                        "force": {"type": "boolean", "default": False},
                        "dry_run": {"type": "boolean", "default": False},
                    },
                },
            ),
            self._run_env,
        )

        self.register_tool(
            MCPTool(
                name="hotpass.aws",
                description="Verify AWS identity and optional EKS connectivity",
                input_schema={
                    "type": "object",
                    "properties": {
                        "profile": {"type": "string"},
                        "region": {"type": "string"},
                        "eks_cluster": {"type": "string"},
                        "verify_kubeconfig": {"type": "boolean", "default": False},
                        "kube_context": {"type": "string"},
                        "kubeconfig": {"type": "string"},
                        "output": {
                            "type": "string",
                            "enum": ["text", "json"],
                            "default": "text",
                        },
                        "dry_run": {"type": "boolean", "default": False},
                    },
                },
            ),
            self._run_aws,
        )

        self.register_tool(
            MCPTool(
                name="hotpass.arc",
                description="Verify ARC runner lifecycle via CLI wrapper",
                input_schema={
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repository": {"type": "string"},
                        "scale_set": {"type": "string"},
                        "namespace": {"type": "string", "default": "arc-runners"},
                        "aws_region": {"type": "string"},
                        "aws_profile": {"type": "string"},
                        "snapshot": {"type": "string"},
                        "verify_oidc": {"type": "boolean", "default": False},
                        "output": {
                            "type": "string",
                            "enum": ["text", "json"],
                            "default": "text",
                        },
                        "store_summary": {"type": "boolean", "default": False},
                        "dry_run": {"type": "boolean", "default": False},
                    },
                    "required": ["owner", "repository", "scale_set"],
                },
            ),
            self._run_arc,
        )

        self.register_tool(
            MCPTool(
                name="hotpass.plan.research",
                description="Plan deterministic and network research for an entity",
                input_schema={
                    "type": "object",
                    "properties": {
                        "profile": {
                            "type": "string",
                            "description": "Industry profile to use",
                            "default": "generic",
                        },
                        "dataset_path": {
                            "type": "string",
                            "description": "Optional dataset (Excel/CSV) containing the entity row",
                        },
                        "row_id": {
                            "type": "string",
                            "description": "Row identifier or index when using dataset_path",
                        },
                        "entity": {
                            "type": "string",
                            "description": "Entity name to match when row_id not supplied",
                        },
                        "query": {
                            "type": "string",
                            "description": "Free-text research query",
                        },
                        "urls": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Target URLs to crawl deterministically",
                        },
                        "allow_network": {
                            "type": "boolean",
                            "description": "Enable network access during the plan",
                            "default": False,
                        },
                        "row": {
                            "type": "object",
                            "description": "Optional dataset row supplied directly to the planner",
                        },
                    },
                },
            ),
            self._run_plan_research,
        )
        self.register_tool(
            MCPTool(
                name="hotpass.crawl",
                description="Execute research crawler (requires network permission)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query_or_url": {
                            "type": "string",
                            "description": "Query string or URL to crawl",
                        },
                        "profile": {
                            "type": "string",
                            "description": "Industry profile to use",
                            "default": "generic",
                        },
                        "backend": {
                            "type": "string",
                            "enum": ["deterministic", "research"],
                            "description": "Backend to use for crawling",
                            "default": "deterministic",
                        },
                        "allow_network": {
                            "type": "boolean",
                            "description": "Enable network access during the crawl",
                            "default": False,
                        },
                    },
                    "required": ["query_or_url"],
                },
            ),
            self._run_crawl,
        )
        self.register_tool(
            MCPTool(
                name="hotpass.ta.check",
                description="Run Technical Acceptance checks (all quality gates)",
                input_schema={
                    "type": "object",
                    "properties": {
                        "gate": {
                            "type": "integer",
                            "description": "Specific gate to run (1-5), or omit to run all",
                            "enum": [1, 2, 3, 4, 5],
                        }
                    },
                },
            ),
            self._run_ta_check,
        )

        self.register_tool(
            MCPTool(
                name="hotpass.search.intelligent",
                description="Generate intelligent search strategies without executing the pipeline",
                input_schema={
                    "type": "object",
                    "properties": {
                        "profile": {"type": "string", "default": "generic"},
                        "dataset_path": {"type": "string"},
                        "row_id": {"type": "string"},
                        "entity": {"type": "string"},
                        "query": {"type": "string"},
                        "urls": {"type": "array", "items": {"type": "string"}},
                        "allow_network": {"type": "boolean", "default": False},
                        "row": {"type": "object"},
                    },
                },
            ),
            self._run_intelligent_search,
        )

        self.register_tool(
            MCPTool(
                name="hotpass.crawl.coordinate",
                description="Produce a crawl coordination schedule for agents",
                input_schema={
                    "type": "object",
                    "properties": {
                        "profile": {"type": "string", "default": "generic"},
                        "dataset_path": {"type": "string"},
                        "row_id": {"type": "string"},
                        "entity": {"type": "string"},
                        "query": {"type": "string"},
                        "urls": {"type": "array", "items": {"type": "string"}},
                        "allow_network": {"type": "boolean", "default": False},
                        "backend": {
                            "type": "string",
                            "enum": ["deterministic", "research"],
                            "default": "deterministic",
                        },
                        "row": {"type": "object"},
                    },
                },
            ),
            self._run_coordinate_crawl,
        )

        self.register_tool(
            MCPTool(
                name="hotpass.pipeline.supervise",
                description="Analyse pipeline snapshots and surface supervision guidance",
                input_schema={
                    "type": "object",
                    "properties": {
                        "pipeline": {"type": "object"},
                    },
                },
            ),
            self._run_pipeline_supervision,
        )

        self.register_tool(
            MCPTool(
                name="hotpass.agent.workflow",
                description="Simulate an autonomous agent workflow end-to-end",
                input_schema={
                    "type": "object",
                    "properties": {
                        "profile": {"type": "string", "default": "generic"},
                        "dataset_path": {"type": "string"},
                        "row_id": {"type": "string"},
                        "entity": {"type": "string"},
                        "query": {"type": "string"},
                        "urls": {"type": "array", "items": {"type": "string"}},
                        "allow_network": {"type": "boolean", "default": False},
                        "row": {"type": "object"},
                        "pipeline_snapshot": {"type": "object"},
                        "crawl_backend": {
                            "type": "string",
                            "enum": ["deterministic", "research"],
                            "default": "deterministic",
                        },
                    },
                },
            ),
            self._run_agent_workflow,
        )

    def _load_policy_payload(self) -> Mapping[str, object]:
        policy_file = os.getenv("HOTPASS_MCP_POLICY_FILE")
        if policy_file:
            path = Path(policy_file)
            if path.exists():
                try:
                    text = path.read_text(encoding="utf-8")
                    if path.suffix.lower() in {".yml", ".yaml"} and yaml is not None:
                        loaded = yaml.safe_load(text) or {}
                    else:
                        loaded = json.loads(text)
                    if isinstance(loaded, Mapping):
                        return loaded
                except Exception:
                    logger.warning("Failed to load role policy from %s", policy_file, exc_info=True)

        env_payload = os.getenv("HOTPASS_MCP_POLICY_JSON")
        if env_payload:
            try:
                loaded_env = json.loads(env_payload)
                if isinstance(loaded_env, Mapping):
                    return loaded_env
            except json.JSONDecodeError:
                logger.warning("Invalid HOTPASS_MCP_POLICY_JSON payload", exc_info=True)

        return DEFAULT_ROLE_POLICY

    def _register_plugin(self, plugin: Any) -> None:
        register = getattr(plugin, "register_mcp_tools", None)
        if callable(register):
            register(self)

    def _load_plugins(self) -> None:
        modules = os.getenv("HOTPASS_MCP_PLUGINS", "")
        for name in modules.split(","):
            module_name = name.strip()
            if not module_name:
                continue
            try:
                plugin_module = importlib.import_module(module_name)
            except Exception:
                logger.warning("Failed to import MCP plugin module %s", module_name, exc_info=True)
                continue
            self._register_plugin(plugin_module)

        try:
            for entry_point in metadata.entry_points().select(group="hotpass.mcp_tools"):
                try:
                    plugin = entry_point.load()
                except Exception:
                    logger.warning(
                        "Failed to load MCP plugin entry point %s",
                        entry_point.name,
                        exc_info=True,
                    )
                    continue
                self._register_plugin(plugin)
        except Exception:
            logger.debug("No MCP plugin entry points discovered", exc_info=True)

    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """Handle an incoming MCP request."""
        try:
            params = request.params or {}
            if not isinstance(params, Mapping):
                params = {}

            if request.method == "tools/list":
                role, _ = self._resolve_role(params, None)
                visible_tools = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.input_schema,
                    }
                    for tool in self.tools
                    if self.role_policy.is_allowed(role, tool.name)
                ]
                return MCPResponse(result={"tools": visible_tools}, id=request.id)

            elif request.method == "tools/call":
                tool_name = params.get("name")
                raw_arguments = params.get("arguments", {})
                tool_args = dict(raw_arguments) if isinstance(raw_arguments, Mapping) else {}

                if not isinstance(tool_name, str):
                    return MCPResponse(
                        error={
                            "code": -32602,
                            "message": "Invalid params: tool name must be a string",
                        },
                        id=request.id,
                    )

                role, tool_args = self._resolve_role(params, tool_args)
                tool_args = tool_args or {}
                if not self.role_policy.is_allowed(role, tool_name):
                    return MCPResponse(
                        error={
                            "code": 403,
                            "message": (
                                f"Role '{role or self.role_policy.default_role}' "
                                f"is not permitted to call {tool_name}"
                            ),
                        },
                        id=request.id,
                    )

                result = await self._execute_tool(tool_name, tool_args)
                return MCPResponse(result=result, id=request.id)

            else:
                return MCPResponse(
                    error={
                        "code": -32601,
                        "message": f"Method not found: {request.method}",
                    },
                    id=request.id,
                )

        except Exception as e:
            logger.error(f"Error handling request: {e}", exc_info=True)
            return MCPResponse(
                error={"code": -32603, "message": f"Internal error: {str(e)}"},
                id=request.id,
            )

    async def _execute_tool(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Execute a Hotpass tool."""
        logger.info("Executing tool %s", tool_name)

        entry = self._tool_registry.get(tool_name)
        if entry is None:
            raise ValueError(f"Unknown tool: {tool_name}")

        return await entry.handler(args)

    async def _run_refine(self, args: dict[str, Any]) -> dict[str, Any]:
        """Run the refine command."""
        cmd = [
            "refine",
            "--input-dir",
            args["input_path"],
            "--output-path",
            args["output_path"],
        ]

        if "profile" in args:
            cmd.extend(["--profile", args["profile"]])

        for path in self._normalise_profile_paths(args.get("profile_search_path")):
            cmd.extend(["--profile-search-path", path])

        if args.get("archive", False):
            cmd.append("--archive")

        result = await self._run_hotpass(cmd)
        return {
            "success": result["returncode"] == 0,
            "output": result["stdout"],
            "error": result["stderr"] if result["returncode"] != 0 else None,
            "output_path": args["output_path"],
        }

    async def _run_enrich(self, args: dict[str, Any]) -> dict[str, Any]:
        """Run the enrich command."""
        cmd = [
            "enrich",
            "--input",
            args["input_path"],
            "--output",
            args["output_path"],
        ]

        if "profile" in args:
            cmd.extend(["--profile", args["profile"]])

        if "allow_network" in args:
            cmd.append(f"--allow-network={str(args['allow_network']).lower()}")

        for path in self._normalise_profile_paths(args.get("profile_search_path")):
            cmd.extend(["--profile-search-path", path])

        result = await self._run_hotpass(cmd)
        return {
            "success": result["returncode"] == 0,
            "output": result["stdout"],
            "error": result["stderr"] if result["returncode"] != 0 else None,
            "output_path": args["output_path"],
        }

    async def _run_qa(self, args: dict[str, Any]) -> dict[str, Any]:
        """Run the qa command."""
        target = args.get("target", "all")
        cmd = ["qa", target]

        result = await self._run_hotpass(cmd)
        return {
            "success": result["returncode"] == 0,
            "output": result["stdout"],
            "error": result["stderr"] if result["returncode"] != 0 else None,
        }

    async def _explain_provenance(self, args: dict[str, Any]) -> dict[str, Any]:
        """Explain provenance for a row."""
        try:
            from pathlib import Path

            import pandas as pd

            dataset_path = Path(args["dataset_path"])
            if not dataset_path.exists():
                return {
                    "success": False,
                    "error": f"Dataset not found: {dataset_path}",
                }

            # Load the dataset
            df = pd.read_excel(dataset_path)

            # Find the row by ID
            row_id = args["row_id"]
            try:
                row_index = int(row_id)
            except ValueError:
                # Try to find by a column value
                if "id" in df.columns:
                    rows = df[df["id"] == row_id]
                    if rows.empty:
                        return {"success": False, "error": f"Row ID {row_id} not found"}
                    row_index = rows.index[0]
                else:
                    return {"success": False, "error": "Invalid row ID format"}

            if row_index >= len(df):
                return {
                    "success": False,
                    "error": f"Row index {row_index} out of range",
                }

            row = df.iloc[row_index]

            # Extract provenance columns if they exist
            provenance_info = {}
            provenance_columns = [
                "provenance_source",
                "provenance_timestamp",
                "provenance_confidence",
                "provenance_strategy",
                "provenance_network_status",
            ]

            for col in provenance_columns:
                if col in df.columns:
                    provenance_info[col] = str(row.get(col, "N/A"))

            if not provenance_info:
                return {
                    "success": True,
                    "row_id": row_id,
                    "message": "No provenance information found in dataset",
                }

            return {
                "success": True,
                "row_id": row_id,
                "row_index": row_index,
                "provenance": provenance_info,
                "organization_name": str(row.get("organization_name", "N/A")),
            }

        except Exception as e:
            logger.error(f"Error explaining provenance: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to explain provenance: {str(e)}",
            }

    def _build_research_context(self, args: Mapping[str, Any]) -> ResearchContext:
        profile_name = args.get("profile") or "generic"
        profile = self._load_industry_profile(profile_name)

        row = None
        dataset_path = args.get("dataset_path")
        if dataset_path:
            row = self._load_dataset_row(Path(dataset_path), args.get("row_id"), args.get("entity"))

        if row is None and isinstance(args.get("row"), dict):
            row = pd.Series(args["row"])

        urls = args.get("urls")
        if not isinstance(urls, list):
            urls = []

        return ResearchContext(
            profile=profile,
            row=row,
            entity_name=args.get("entity"),
            query=args.get("query"),
            urls=urls,
            allow_network=bool(args.get("allow_network", False)),
        )

    def _resolve_role(
        self,
        params: Mapping[str, Any] | None,
        arguments: Mapping[str, Any] | None,
    ) -> tuple[str | None, dict[str, Any] | None]:
        candidate: str | None = None
        if params and isinstance(params, Mapping):
            value = params.get("role")
            if isinstance(value, str) and value.strip():
                candidate = value.strip()

        sanitised: dict[str, Any] | None = None
        if arguments and isinstance(arguments, Mapping):
            sanitised = dict(arguments)
            override = sanitised.pop("_role", None)
            if isinstance(override, str) and override.strip():
                candidate = override.strip()

        if candidate:
            return candidate, sanitised

        env_role = os.getenv("HOTPASS_MCP_ROLE")
        if env_role:
            return env_role, sanitised

        return None, sanitised

    async def _run_plan_research(self, args: dict[str, Any]) -> dict[str, Any]:
        """Plan deterministic and network research using the orchestrator."""

        context = self._build_research_context(args)
        outcome = self._research_orchestrator.plan(context)
        return {
            "success": outcome.success,
            "outcome": outcome.to_dict(),
        }

    async def _run_crawl(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute a crawl-only orchestrator pass."""

        query_or_url = args.get("query_or_url")
        if not isinstance(query_or_url, str) or not query_or_url.strip():
            return {
                "success": False,
                "error": "query_or_url must be a non-empty string",
            }

        context = self._build_research_context(args)
        outcome = self._research_orchestrator.crawl(
            profile=context.profile,
            query_or_url=query_or_url,
            allow_network=context.allow_network,
        )

        return {
            "success": outcome.success,
            "outcome": outcome.to_dict(),
        }

    async def _run_intelligent_search(self, args: dict[str, Any]) -> dict[str, Any]:
        """Return an intelligent search strategy for the supplied context."""

        context = self._build_research_context(args)
        strategy = self._research_orchestrator.intelligent_search(context)
        return {
            "success": True,
            "strategy": strategy.to_dict(),
        }

    async def _run_coordinate_crawl(self, args: dict[str, Any]) -> dict[str, Any]:
        """Return a crawl coordination schedule without executing network requests."""

        backend = args.get("backend") or "deterministic"
        context = self._build_research_context(args)
        schedule = self._research_orchestrator.coordinate_crawl(context, backend=backend)
        return {
            "success": True,
            "schedule": schedule.to_dict(),
        }

    async def _run_pipeline_supervision(self, args: dict[str, Any]) -> dict[str, Any]:
        """Analyse a pipeline snapshot and return supervision guidance."""

        snapshot_payload = args.get("pipeline") or {}
        if isinstance(snapshot_payload, Mapping):
            snapshot = PipelineSnapshot.from_payload(snapshot_payload)
        else:
            snapshot = PipelineSnapshot(name="pipeline", runs=(), tasks=(), metrics={})

        report = self._pipeline_supervisor.inspect(snapshot)
        return {
            "success": True,
            "report": report.to_dict(),
        }

    async def _run_agent_workflow(self, args: dict[str, Any]) -> dict[str, Any]:
        """Simulate an autonomous workflow combining search, crawl, and supervision."""

        context = self._build_research_context(args)
        snapshot_payload = args.get("pipeline_snapshot")
        backend = args.get("crawl_backend") or "deterministic"
        report = self._workflow_harness.simulate(
            context,
            pipeline_snapshot=(snapshot_payload if isinstance(snapshot_payload, Mapping) else None),
            crawl_backend=backend,
        )
        return {
            "success": True,
            "report": report.to_dict(),
        }

    async def _run_setup(self, args: dict[str, Any]) -> dict[str, Any]:
        """Execute the hotpass setup wizard."""

        cmd = ["setup"]
        preset = args.get("preset")
        if preset:
            cmd.extend(["--preset", preset])

        extras = args.get("extras") or []
        for extra in extras:
            cmd.extend(["--extras", extra])

        skip_steps = args.get("skip_steps") or []
        skip_mapping = {
            "deps": "--skip-deps",
            "prereqs": "--skip-prereqs",
            "tunnels": "--skip-tunnels",
            "aws": "--skip-aws",
            "ctx": "--skip-ctx",
            "env": "--skip-env",
            "arc": "--skip-arc",
        }
        for step in skip_steps:
            flag = skip_mapping.get(step.lower())
            if flag:
                cmd.append(flag)

        host = args.get("host")
        if host:
            cmd.extend(["--host", host])
        via = args.get("via")
        if via:
            cmd.extend(["--via", via])
        label = args.get("label")
        if label:
            cmd.extend(["--label", label])

        if args.get("aws_profile"):
            cmd.extend(["--aws-profile", args["aws_profile"]])
        if args.get("aws_region"):
            cmd.extend(["--aws-region", args["aws_region"]])
        if args.get("eks_cluster"):
            cmd.extend(["--eks-cluster", args["eks_cluster"]])
        if args.get("kube_context"):
            cmd.extend(["--kube-context", args["kube_context"]])
        if args.get("namespace"):
            cmd.extend(["--namespace", args["namespace"]])
        if args.get("prefect_profile"):
            cmd.extend(["--prefect-profile", args["prefect_profile"]])
        if args.get("prefect_url"):
            cmd.extend(["--prefect-url", args["prefect_url"]])
        if args.get("env_target"):
            cmd.extend(["--env-target", args["env_target"]])
        if args.get("allow_network"):
            cmd.append("--allow-network")
        if args.get("force_env"):
            cmd.append("--force-env")
        if args.get("arc_owner"):
            cmd.extend(["--arc-owner", args["arc_owner"]])
        if args.get("arc_repository"):
            cmd.extend(["--arc-repository", args["arc_repository"]])
        if args.get("arc_scale_set"):
            cmd.extend(["--arc-scale-set", args["arc_scale_set"]])
        if args.get("arc_namespace"):
            cmd.extend(["--arc-namespace", args["arc_namespace"]])
        if args.get("arc_snapshot"):
            cmd.extend(["--arc-snapshot", args["arc_snapshot"]])

        execute = bool(args.get("execute"))
        dry_run = args.get("dry_run", not execute)
        if dry_run:
            cmd.append("--dry-run")
        if execute:
            cmd.append("--execute")
        if args.get("assume_yes", True):
            cmd.append("--assume-yes")

        result = await self._run_hotpass(cmd)
        return {
            "success": result["returncode"] == 0,
            "output": result["stdout"],
            "error": result["stderr"] if result["returncode"] != 0 else None,
        }

    async def _run_net(self, args: dict[str, Any]) -> dict[str, Any]:
        """Run net commands."""

        action = args.get("action")
        if action not in {"up", "down", "status"}:
            return {"success": False, "error": "Unsupported net action"}

        cmd = ["net", action]

        if action == "up":
            via = args.get("via")
            if via:
                cmd.extend(["--via", via])
            host = args.get("host")
            if host:
                cmd.extend(["--host", host])
            label = args.get("label")
            if label:
                cmd.extend(["--label", label])
            if args.get("detach", True):
                cmd.append("--detach")
            if args.get("auto_port") is not None:
                flag = "--auto-port"
                if not args["auto_port"]:
                    flag = "--no-auto-port"
                cmd.append(flag)
            if args.get("prefect_port") is not None:
                cmd.extend(["--prefect-port", str(args["prefect_port"])])
            if args.get("marquez_port") is not None:
                cmd.extend(["--marquez-port", str(args["marquez_port"])])
            if args.get("no_marquez"):
                cmd.append("--no-marquez")
        elif action == "down":
            label = args.get("label")
            if label:
                cmd.extend(["--label", label])
            if args.get("all"):
                cmd.append("--all")

        if args.get("dry_run"):
            cmd.append("--dry-run")

        result = await self._run_hotpass(cmd)
        return {
            "success": result["returncode"] == 0,
            "output": result["stdout"],
            "error": result["stderr"] if result["returncode"] != 0 else None,
        }

    async def _run_ctx(self, args: dict[str, Any]) -> dict[str, Any]:
        """Run ctx commands."""

        action = args.get("action", "init")
        cmd = ["ctx", action]

        if action == "init":
            if args.get("prefect_profile"):
                cmd.extend(["--prefect-profile", args["prefect_profile"]])
            if args.get("prefect_url"):
                cmd.extend(["--prefect-url", args["prefect_url"]])
            if args.get("eks_cluster"):
                cmd.extend(["--eks-cluster", args["eks_cluster"]])
            if args.get("kube_context"):
                cmd.extend(["--kube-context", args["kube_context"]])
            if args.get("namespace"):
                cmd.extend(["--namespace", args["namespace"]])
            if args.get("no_prefect"):
                cmd.append("--no-prefect")
            if args.get("no_kube"):
                cmd.append("--no-kube")
        if args.get("dry_run"):
            cmd.append("--dry-run")

        result = await self._run_hotpass(cmd)
        return {
            "success": result["returncode"] == 0,
            "output": result["stdout"],
            "error": result["stderr"] if result["returncode"] != 0 else None,
        }

    async def _run_env(self, args: dict[str, Any]) -> dict[str, Any]:
        """Run env command."""

        cmd = ["env"]
        target = args.get("target")
        if target:
            cmd.extend(["--target", target])
        if args.get("prefect_url"):
            cmd.extend(["--prefect-url", args["prefect_url"]])
        if args.get("openlineage_url"):
            cmd.extend(["--openlineage-url", args["openlineage_url"]])
        if args.get("allow_network"):
            cmd.append("--allow-network")
        if args.get("force"):
            cmd.append("--force")
        if args.get("dry_run"):
            cmd.append("--dry-run")

        result = await self._run_hotpass(cmd)
        return {
            "success": result["returncode"] == 0,
            "output": result["stdout"],
            "error": result["stderr"] if result["returncode"] != 0 else None,
        }

    async def _run_aws(self, args: dict[str, Any]) -> dict[str, Any]:
        """Run aws verification command."""

        cmd = ["aws"]
        if args.get("profile"):
            cmd.extend(["--profile", args["profile"]])
        if args.get("region"):
            cmd.extend(["--region", args["region"]])
        if args.get("eks_cluster"):
            cmd.extend(["--eks-cluster", args["eks_cluster"]])
        if args.get("verify_kubeconfig"):
            cmd.append("--verify-kubeconfig")
        if args.get("kube_context"):
            cmd.extend(["--kube-context", args["kube_context"]])
        if args.get("kubeconfig"):
            cmd.extend(["--kubeconfig", args["kubeconfig"]])
        if args.get("output"):
            cmd.extend(["--output", args["output"]])
        if args.get("dry_run"):
            cmd.append("--dry-run")

        result = await self._run_hotpass(cmd)
        success = result["returncode"] == 0
        payload = {
            "success": success,
            "output": result["stdout"],
        }
        if not success:
            payload["error"] = result["stderr"]
        return payload

    async def _run_arc(self, args: dict[str, Any]) -> dict[str, Any]:
        """Run arc verification command."""

        cmd = [
            "arc",
            "--owner",
            args["owner"],
            "--repository",
            args["repository"],
            "--scale-set",
            args["scale_set"],
        ]
        if args.get("namespace"):
            cmd.extend(["--namespace", args["namespace"]])
        if args.get("aws_region"):
            cmd.extend(["--aws-region", args["aws_region"]])
        if args.get("aws_profile"):
            cmd.extend(["--aws-profile", args["aws_profile"]])
        if args.get("snapshot"):
            cmd.extend(["--snapshot", args["snapshot"]])
        if args.get("verify_oidc"):
            cmd.append("--verify-oidc")
        if args.get("output"):
            cmd.extend(["--output", args["output"]])
        if args.get("store_summary"):
            cmd.append("--store-summary")
        if args.get("dry_run"):
            cmd.append("--dry-run")

        result = await self._run_hotpass(cmd)
        return {
            "success": result["returncode"] == 0,
            "output": result["stdout"],
            "error": result["stderr"] if result["returncode"] != 0 else None,
        }

    def _load_industry_profile(self, profile_name: str) -> IndustryProfile:
        if profile_name == "generic":
            return get_default_profile("generic")
        try:
            return load_industry_profile(profile_name)
        except Exception:  # pragma: no cover - fallback when profile missing
            logger.warning("Falling back to generic profile for %s", profile_name)
            return get_default_profile("generic")

    def _load_dataset_row(
        self,
        dataset_path: Path,
        row_identifier: str | None,
        entity: str | None,
    ) -> pd.Series | None:
        if not dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found: {dataset_path}")

        if dataset_path.suffix.lower() in {".xlsx", ".xls", ".xlsm"}:
            frame = pd.read_excel(dataset_path)
        else:
            frame = pd.read_csv(dataset_path)

        if frame.empty:
            return None

        if row_identifier is not None:
            try:
                index = int(row_identifier)
                return frame.iloc[index]
            except (ValueError, IndexError):
                pass
            if "id" in frame.columns:
                match = frame[frame["id"].astype(str) == row_identifier]
                if not match.empty:
                    return match.iloc[0]

        if entity and "organization_name" in frame.columns:
            mask = frame["organization_name"].astype(str).str.casefold() == entity.casefold()
            match = frame[mask]
            if not match.empty:
                return match.iloc[0]

        return None

    async def _run_ta_check(self, args: dict[str, Any]) -> dict[str, Any]:
        """Run Technical Acceptance checks (all quality gates)."""
        gate = args.get("gate")
        cmd = ["python", "ops/quality/run_all_gates.py", "--json"]

        if gate:
            cmd.extend(["--gate", str(gate)])

        result = await self._run_command(cmd)

        if result["returncode"] == 0:
            # Parse JSON output
            try:
                import json

                output_data = json.loads(result["stdout"])
                return {
                    "success": True,
                    "summary": output_data.get("summary", {}),
                    "gates": output_data.get("gates", []),
                    "artifact_path": output_data.get("artifact_path"),
                }
            except json.JSONDecodeError:
                return {
                    "success": result["returncode"] == 0,
                    "output": result["stdout"],
                }
        else:
            return {
                "success": False,
                "error": result["stderr"],
                "output": result["stdout"],
            }

    async def _run_hotpass(
        self, args: list[str], *, env: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Execute a hotpass CLI command via uv run."""

        return await self._run_command(["uv", "run", "hotpass", *args], env=env)

    async def _run_command(
        self, cmd: list[str], env: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Run a command asynchronously."""
        spawn_env = None
        if env:
            spawn_env = os.environ.copy()
            spawn_env.update({key: str(value) for key, value in env.items()})

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=spawn_env,
        )

        stdout, stderr = await process.communicate()

        return {
            "returncode": process.returncode,
            "stdout": stdout.decode("utf-8"),
            "stderr": stderr.decode("utf-8"),
        }

    async def run(self) -> None:
        """Run the MCP server (stdio mode)."""
        logger.info("Starting Hotpass MCP server in stdio mode")

        try:
            while True:
                # Read line from stdin
                line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)

                if not line:
                    break

                try:
                    # Parse JSON-RPC request
                    request_data = json.loads(line.strip())
                    request = MCPRequest(
                        method=request_data.get("method"),
                        params=request_data.get("params", {}),
                        id=request_data.get("id"),
                    )

                    # Handle request
                    response = await self.handle_request(request)

                    # Build JSON-RPC response
                    response_data: dict[str, Any] = {"jsonrpc": "2.0"}
                    if response.error:
                        response_data["error"] = response.error
                    else:
                        response_data["result"] = response.result
                    if response.id is not None:
                        response_id: int | str = response.id
                        response_data["id"] = response_id

                    # Write response to stdout
                    print(json.dumps(response_data), flush=True)

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    error_response = {
                        "jsonrpc": "2.0",
                        "error": {"code": -32700, "message": "Parse error"},
                        "id": None,
                    }
                    print(json.dumps(error_response), flush=True)

        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        except Exception as e:
            logger.error(f"Server error: {e}", exc_info=True)


async def main() -> None:
    """Main entry point for the MCP server."""
    server = HotpassMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
