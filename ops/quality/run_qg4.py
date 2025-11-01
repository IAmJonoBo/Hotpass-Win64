#!/usr/bin/env python3
"""Run QG-4 (MCP Discoverability) checks."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass
class StepResult:
    """Result of an MCP discoverability validation step."""

    step_id: str
    description: str
    passed: bool
    message: str
    duration_seconds: float


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute QG-4 MCP discoverability validations.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON summary.",
    )
    return parser


def _import_server() -> StepResult:
    start = time.time()
    try:
        from hotpass.mcp.server import HotpassMCPServer  # pylint: disable=import-outside-toplevel
    except Exception as exc:  # pragma: no cover - defensive guard
        return StepResult(
            step_id="import",
            description="Import HotpassMCPServer",
            passed=False,
            message=f"Failed to import HotpassMCPServer: {exc}",
            duration_seconds=time.time() - start,
        )

    try:
        server = HotpassMCPServer()
    except Exception as exc:  # pragma: no cover - defensive guard
        return StepResult(
            step_id="instantiate",
            description="Instantiate HotpassMCPServer",
            passed=False,
            message=f"Failed to instantiate HotpassMCPServer: {exc}",
            duration_seconds=time.time() - start,
        )

    return StepResult(
        step_id="instantiate",
        description="Instantiate HotpassMCPServer",
        passed=True,
        message=f"HotpassMCPServer initialized with {len(server.tools)} tools",
        duration_seconds=time.time() - start,
    )


def _check_required_tools() -> StepResult:
    start = time.time()
    from hotpass.mcp.server import HotpassMCPServer  # pylint: disable=import-outside-toplevel

    server = HotpassMCPServer()
    tool_names = {tool.name for tool in server.tools}
    required_tools = {
        "hotpass.refine",
        "hotpass.enrich",
        "hotpass.qa",
        "hotpass.explain_provenance",
        "hotpass.plan.research",
        "hotpass.crawl",
        "hotpass.ta.check",
    }
    missing = sorted(required_tools.difference(tool_names))
    if missing:
        return StepResult(
            step_id="required-tools",
            description="Verify MCP required tools are registered",
            passed=False,
            message=f"Missing MCP tools: {', '.join(missing)}",
            duration_seconds=time.time() - start,
        )

    return StepResult(
        step_id="required-tools",
        description="Verify MCP required tools are registered",
        passed=True,
        message="All required MCP tools are registered",
        duration_seconds=time.time() - start,
    )


def _check_schema_shapes() -> StepResult:
    start = time.time()
    from hotpass.mcp.server import HotpassMCPServer  # pylint: disable=import-outside-toplevel

    server = HotpassMCPServer()
    issues: list[str] = []
    for tool in server.tools:
        schema = tool.input_schema
        if schema.get("type") != "object":
            issues.append(f"{tool.name} input schema type must be 'object'")
        properties_obj = schema.get("properties")
        if not isinstance(properties_obj, dict):
            issues.append(f"{tool.name} input schema missing properties")
            continue
        if tool.name == "hotpass.qa":
            target_schema = properties_obj.get("target")
            enum_values = target_schema.get("enum") if isinstance(target_schema, dict) else None
            expected_targets = {
                "all",
                "contracts",
                "docs",
                "profiles",
                "ta",
                "fitness",
                "data-quality",
            }
            if not isinstance(enum_values, list) or not expected_targets.issubset(set(enum_values)):
                issues.append(
                    "hotpass.qa target enum must include "
                    "'all, contracts, docs, profiles, ta, fitness, data-quality'",
                )
        if tool.name == "hotpass.plan.research":
            urls_schema = properties_obj.get("urls")
            if not isinstance(urls_schema, dict) or urls_schema.get("type") != "array":
                issues.append("hotpass.plan.research.urls must be an array")

    passed = not issues
    message = "; ".join(issues) if issues else "MCP tool schemas are well-formed"
    return StepResult(
        step_id="schema-shape",
        description="Validate MCP tool schemas",
        passed=passed,
        message=message,
        duration_seconds=time.time() - start,
    )


def _exercise_research_tools() -> StepResult:
    start = time.time()
    try:
        import asyncio
        from pathlib import Path
        from tempfile import TemporaryDirectory

        import pandas as pd  # pylint: disable=import-outside-toplevel
        from hotpass.mcp.server import HotpassMCPServer  # pylint: disable=import-outside-toplevel
    except Exception as exc:  # pragma: no cover - defensive guard
        return StepResult(
            step_id="research-tools-import",
            description="Import MCP server and pandas for research tool exercise",
            passed=False,
            message=f"Failed to import prerequisites: {exc}",
            duration_seconds=time.time() - start,
        )

    try:
        server = HotpassMCPServer()
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            dataset_path = tmp_path / "research-input.xlsx"
            pd.DataFrame(
                {
                    "organization_name": ["QG Research Org"],
                    "contact_primary_email": [""],
                    "website": ["example.org"],
                }
            ).to_excel(dataset_path, index=False)

            plan_result = asyncio.run(
                server._execute_tool(  # pylint: disable=protected-access
                    "hotpass.plan.research",
                    {
                        "dataset_path": str(dataset_path),
                        "row_id": "0",
                        "allow_network": False,
                    },
                )
            )
            if not plan_result.get("success"):
                raise RuntimeError(plan_result.get("error") or "plan research failed")

            crawl_result = asyncio.run(
                server._execute_tool(  # pylint: disable=protected-access
                    "hotpass.crawl",
                    {
                        "query_or_url": "https://example.org",
                        "allow_network": False,
                    },
                )
            )
            if not crawl_result.get("success"):
                raise RuntimeError(crawl_result.get("error") or "crawl failed")

    except Exception as exc:  # pragma: no cover - defensive guard
        return StepResult(
            step_id="research-tools-execute",
            description="Exercise hotpass.plan.research and hotpass.crawl tools",
            passed=False,
            message=f"Research tool execution failed: {exc}",
            duration_seconds=time.time() - start,
        )

    return StepResult(
        step_id="research-tools-execute",
        description="Exercise hotpass.plan.research and hotpass.crawl tools",
        passed=True,
        message="Research planning and crawl MCP tools executed successfully",
        duration_seconds=time.time() - start,
    )


def _build_summary(results: list[StepResult]) -> dict[str, Any]:
    return {
        "gate": "QG-4",
        "name": "MCP Discoverability",
        "timestamp": datetime.now(UTC).isoformat(),
        "passed": all(result.passed for result in results),
        "stats": {
            "total_steps": len(results),
            "passed": sum(result.passed for result in results),
            "failed": sum(not result.passed for result in results),
            "duration_seconds": sum(result.duration_seconds for result in results),
        },
        "steps": [
            {
                "id": result.step_id,
                "description": result.description,
                "status": "passed" if result.passed else "failed",
                "message": result.message,
                "duration_seconds": result.duration_seconds,
            }
            for result in results
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    results = [
        _import_server(),
        _check_required_tools(),
        _check_schema_shapes(),
        _exercise_research_tools(),
    ]

    summary = _build_summary(results)

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        for step in results:
            status = "PASS" if step.passed else "FAIL"
            print(f"{status}: {step.description}")
            print(f"  {step.message}")
        stats = summary["stats"]
        print(
            f"Completed QG-4 steps: {stats['passed']}/{stats['total_steps']} "
            f"passed in {stats['duration_seconds']:.2f}s",
        )
        print("✓ QG-4 passed" if summary["passed"] else "✗ QG-4 failed")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
