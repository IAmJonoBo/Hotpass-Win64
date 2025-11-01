"""Hotpass MCP (Model Context Protocol) server implementation.

This module implements an MCP stdio server that exposes Hotpass operations
as tools that can be called by AI assistants like GitHub Copilot and Codex.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from hotpass.config import IndustryProfile, get_default_profile, load_industry_profile
from hotpass.research import ResearchContext, ResearchOrchestrator

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


class HotpassMCPServer:
    """MCP stdio server for Hotpass operations."""

    def __init__(self) -> None:
        """Initialize the MCP server."""
        self.tools = self._register_tools()
        logger.info(f"Initialized Hotpass MCP server with {len(self.tools)} tools")

    def _register_tools(self) -> list[MCPTool]:
        """Register all available MCP tools."""
        return [
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
                    },
                    "required": ["input_path", "output_path"],
                },
            ),
            MCPTool(
                name="hotpass.enrich",
                description=(
                    "Enrich refined data with additional information from "
                    "deterministic and optional network sources"
                ),
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
                            "description": (
                                "Whether to allow network-based enrichment (defaults to env vars)"
                            ),
                            "default": False,
                        },
                    },
                    "required": ["input_path", "output_path"],
                },
            ),
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
                            "description": "Tunnel mechanism (ssh-bastion or ssm)",
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
                            "description": "Skip the listed stages in the wizard",
                        },
                        "aws_profile": {
                            "type": "string",
                            "description": "AWS CLI profile to use",
                        },
                        "aws_region": {
                            "type": "string",
                            "description": "AWS region override",
                        },
                        "eks_cluster": {
                            "type": "string",
                            "description": "Cluster name forwarded to hotpass ctx/aws",
                        },
                        "kube_context": {
                            "type": "string",
                            "description": "Alias assigned to kubeconfig context",
                        },
                        "namespace": {
                            "type": "string",
                            "description": "Namespace recorded with context metadata",
                        },
                        "prefect_profile": {
                            "type": "string",
                            "description": "Prefect profile configured by the wizard",
                        },
                        "prefect_url": {
                            "type": "string",
                            "description": "Override Prefect API URL",
                        },
                        "env_target": {
                            "type": "string",
                            "description": "Target environment passed to hotpass env",
                        },
                        "allow_network": {
                            "type": "boolean",
                            "description": "Generate env flags for network enrichment",
                            "default": False,
                        },
                        "force_env": {
                            "type": "boolean",
                            "description": "Overwrite existing env files",
                            "default": False,
                        },
                        "arc_owner": {
                            "type": "string",
                            "description": "GitHub owner used in ARC verification",
                        },
                        "arc_repository": {
                            "type": "string",
                            "description": "Repository name used in ARC verification",
                        },
                        "arc_scale_set": {
                            "type": "string",
                            "description": "RunnerScaleSet name used in ARC verification",
                        },
                        "arc_namespace": {
                            "type": "string",
                            "description": "Namespace passed to hotpass arc",
                        },
                        "arc_snapshot": {
                            "type": "string",
                            "description": "Optional snapshot path for ARC verification",
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": "Render the wizard plan without executing",
                            "default": True,
                        },
                        "execute": {
                            "type": "boolean",
                            "description": "Execute the plan with --execute --assume-yes",
                            "default": False,
                        },
                        "assume_yes": {
                            "type": "boolean",
                            "description": "Pass --assume-yes to suppress prompts",
                            "default": True,
                        },
                    },
                },
            ),
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
                        "host": {
                            "type": "string",
                            "description": "Bastion host or SSM target for 'up'",
                        },
                        "label": {
                            "type": "string",
                            "description": "Label identifying the tunnel session",
                        },
                        "all": {
                            "type": "boolean",
                            "description": "Terminate all sessions when action=down",
                        },
                        "detach": {
                            "type": "boolean",
                            "description": "Run tunnels in the background (action=up)",
                            "default": True,
                        },
                        "auto_port": {
                            "type": "boolean",
                            "description": "Allow auto port selection when action=up",
                        },
                        "prefect_port": {
                            "type": "integer",
                            "description": "Local Prefect port override",
                        },
                        "marquez_port": {
                            "type": "integer",
                            "description": "Local Marquez port override",
                        },
                        "no_marquez": {
                            "type": "boolean",
                            "description": "Skip Marquez forwarding",
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": "Print command without executing",
                            "default": False,
                        },
                    },
                    "required": ["action"],
                },
            ),
            MCPTool(
                name="hotpass.ctx",
                description="Bootstrap or list Prefect/Kubernetes contexts",
                input_schema={
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["init", "list"],
                            "description": "ctx subcommand to run",
                            "default": "init",
                        },
                        "prefect_profile": {
                            "type": "string",
                            "description": "Prefect profile name (action=init)",
                        },
                        "prefect_url": {
                            "type": "string",
                            "description": "Prefect API URL override",
                        },
                        "eks_cluster": {
                            "type": "string",
                            "description": "Cluster name for kubeconfig updates",
                        },
                        "kube_context": {
                            "type": "string",
                            "description": "Alias assigned to kubeconfig context",
                        },
                        "namespace": {
                            "type": "string",
                            "description": "Namespace recorded alongside the context",
                        },
                        "no_prefect": {
                            "type": "boolean",
                            "description": "Skip Prefect profile creation",
                        },
                        "no_kube": {
                            "type": "boolean",
                            "description": "Skip kubeconfig updates",
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": "Print commands without executing them",
                            "default": False,
                        },
                    },
                },
            ),
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
                        "prefect_url": {
                            "type": "string",
                            "description": "Override Prefect API URL",
                        },
                        "openlineage_url": {
                            "type": "string",
                            "description": "Override OpenLineage API URL",
                        },
                        "allow_network": {
                            "type": "boolean",
                            "description": "Enable network enrichment flags",
                            "default": False,
                        },
                        "force": {
                            "type": "boolean",
                            "description": "Overwrite existing files",
                            "default": False,
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": "Preview the file without writing it",
                            "default": False,
                        },
                    },
                },
            ),
            MCPTool(
                name="hotpass.aws",
                description="Verify AWS identity and optional EKS connectivity",
                input_schema={
                    "type": "object",
                    "properties": {
                        "profile": {
                            "type": "string",
                            "description": "AWS CLI profile to use",
                        },
                        "region": {
                            "type": "string",
                            "description": "AWS region override",
                        },
                        "eks_cluster": {
                            "type": "string",
                            "description": "Cluster passed to --eks-cluster",
                        },
                        "verify_kubeconfig": {
                            "type": "boolean",
                            "description": "Run aws eks update-kubeconfig",
                            "default": False,
                        },
                        "kube_context": {
                            "type": "string",
                            "description": "Alias for kubeconfig context",
                        },
                        "kubeconfig": {
                            "type": "string",
                            "description": "Path to kubeconfig file to update",
                        },
                        "output": {
                            "type": "string",
                            "enum": ["text", "json"],
                            "description": "Render mode",
                            "default": "text",
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": "Print commands without executing",
                            "default": False,
                        },
                    },
                },
            ),
            MCPTool(
                name="hotpass.arc",
                description="Verify ARC runner lifecycle via CLI wrapper",
                input_schema={
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string", "description": "Repository owner"},
                        "repository": {
                            "type": "string",
                            "description": "Repository name",
                        },
                        "scale_set": {
                            "type": "string",
                            "description": "RunnerScaleSet to verify",
                        },
                        "namespace": {
                            "type": "string",
                            "description": "Kubernetes namespace",
                            "default": "arc-runners",
                        },
                        "aws_region": {
                            "type": "string",
                            "description": "AWS region override",
                        },
                        "aws_profile": {
                            "type": "string",
                            "description": "AWS profile override",
                        },
                        "snapshot": {
                            "type": "string",
                            "description": "Snapshot JSON for offline rehearsal",
                        },
                        "verify_oidc": {
                            "type": "boolean",
                            "description": "Enable AWS identity verification",
                            "default": False,
                        },
                        "output": {
                            "type": "string",
                            "enum": ["text", "json"],
                            "default": "text",
                        },
                        "store_summary": {
                            "type": "boolean",
                            "description": "Persist results under .hotpass/arc/",
                            "default": False,
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": "Print command without executing",
                            "default": False,
                        },
                    },
                    "required": ["owner", "repository", "scale_set"],
                },
            ),
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
                    },
                    "required": ["query_or_url"],
                },
            ),
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
        ]

    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """Handle an incoming MCP request."""
        try:
            if request.method == "tools/list":
                return MCPResponse(
                    result={
                        "tools": [
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "inputSchema": tool.input_schema,
                            }
                            for tool in self.tools
                        ]
                    },
                    id=request.id,
                )

            elif request.method == "tools/call":
                tool_name = request.params.get("name")
                tool_args = request.params.get("arguments", {})

                # Ensure tool_name is a string
                if not isinstance(tool_name, str):
                    return MCPResponse(
                        error={
                            "code": -32602,
                            "message": "Invalid params: tool name must be a string",
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
        logger.info(f"Executing tool: {tool_name} with args: {args}")

        if tool_name == "hotpass.refine":
            return await self._run_refine(args)
        elif tool_name == "hotpass.enrich":
            return await self._run_enrich(args)
        elif tool_name == "hotpass.qa":
            return await self._run_qa(args)
        elif tool_name == "hotpass.setup":
            return await self._run_setup(args)
        elif tool_name == "hotpass.net":
            return await self._run_net(args)
        elif tool_name == "hotpass.ctx":
            return await self._run_ctx(args)
        elif tool_name == "hotpass.env":
            return await self._run_env(args)
        elif tool_name == "hotpass.aws":
            return await self._run_aws(args)
        elif tool_name == "hotpass.arc":
            return await self._run_arc(args)
        elif tool_name == "hotpass.explain_provenance":
            return await self._explain_provenance(args)
        elif tool_name == "hotpass.plan.research":
            return await self._run_plan_research(args)
        elif tool_name == "hotpass.crawl":
            return await self._run_crawl(args)
        elif tool_name == "hotpass.ta.check":
            return await self._run_ta_check(args)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

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

    async def _run_plan_research(self, args: dict[str, Any]) -> dict[str, Any]:
        """Plan deterministic and network research using the orchestrator."""

        profile_name = args.get("profile") or "generic"
        profile = self._load_industry_profile(profile_name)

        row = None
        dataset_path = args.get("dataset_path")
        if dataset_path:
            row = self._load_dataset_row(Path(dataset_path), args.get("row_id"), args.get("entity"))

        if row is None and isinstance(args.get("row"), dict):
            row = pd.Series(args["row"])

        context = ResearchContext(
            profile=profile,
            row=row,
            entity_name=args.get("entity"),
            query=args.get("query"),
            urls=args.get("urls", []),
            allow_network=bool(args.get("allow_network", False)),
        )

        orchestrator = ResearchOrchestrator()
        outcome = orchestrator.plan(context)
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

        profile_name = args.get("profile") or "generic"
        profile = self._load_industry_profile(profile_name)
        allow_network = bool(args.get("allow_network", False))

        orchestrator = ResearchOrchestrator()
        outcome = orchestrator.crawl(
            profile=profile,
            query_or_url=query_or_url,
            allow_network=allow_network,
        )

        return {
            "success": outcome.success,
            "outcome": outcome.to_dict(),
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
