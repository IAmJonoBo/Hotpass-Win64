from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from hotpass.config import get_default_profile
from hotpass.mcp.server import HotpassMCPServer
from hotpass.research import ResearchContext, ResearchOrchestrator


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _write_dataset(tmp_path: Path) -> Path:
    path = tmp_path / "mcp-research-input.xlsx"
    df = pd.DataFrame(
        {
            "organization_name": ["Example Research Org"],
            "contact_primary_email": [""],
            "website": ["example.org"],
        }
    )
    df.to_excel(path, index=False)
    return path


@pytest.mark.asyncio
async def test_plan_research_tool(tmp_path, monkeypatch):
    dataset = _write_dataset(tmp_path)
    monkeypatch.delenv("FEATURE_ENABLE_REMOTE_RESEARCH", raising=False)
    monkeypatch.delenv("ALLOW_NETWORK_RESEARCH", raising=False)

    server = HotpassMCPServer()
    result = await server._execute_tool(  # pylint: disable=protected-access
        "hotpass.plan.research",
        {
            "dataset_path": str(dataset),
            "row_id": "0",
            "allow_network": True,
        },
    )

    expect(result["success"] is True, "Plan research tool should succeed")
    outcome = result["outcome"]
    expect("plan" in outcome, "Outcome should include plan metadata")
    expect(
        any(step["status"] == "success" for step in outcome["steps"]),
        "At least one step should succeed",
    )


@pytest.mark.asyncio
async def test_crawl_tool(monkeypatch):
    monkeypatch.delenv("FEATURE_ENABLE_REMOTE_RESEARCH", raising=False)
    monkeypatch.delenv("ALLOW_NETWORK_RESEARCH", raising=False)

    server = HotpassMCPServer()
    result = await server._execute_tool(  # pylint: disable=protected-access
        "hotpass.crawl",
        {
            "query_or_url": "https://example.org",
            "allow_network": True,
        },
    )

    expect(result["success"] is True, "Crawl tool should succeed")
    outcome = result["outcome"]
    expect(outcome["plan"]["entity_name"], "Crawl outcome should include entity name")


@pytest.mark.asyncio
async def test_ta_check_tool(monkeypatch, tmp_path):
    artifact = tmp_path / "latest-ta.json"
    artifact.write_text("{}", encoding="utf-8")
    history = tmp_path / "history.ndjson"
    history.write_text("", encoding="utf-8")

    async def fake_run_command(self, cmd):
        payload = {
            "summary": {"total": 5, "passed": 5, "failed": 0, "all_passed": True},
            "gates": [
                {
                    "id": "QG-1",
                    "name": "CLI Integrity",
                    "passed": True,
                    "message": "ok",
                },
                {"id": "QG-2", "name": "Data Quality", "passed": True, "message": "ok"},
            ],
            "artifact_path": str(artifact),
            "history_path": str(history),
        }
        return {"returncode": 0, "stdout": json.dumps(payload), "stderr": ""}

    monkeypatch.setattr(HotpassMCPServer, "_run_command", fake_run_command)

    server = HotpassMCPServer()
    result = await server._execute_tool(  # pylint: disable=protected-access
        "hotpass.ta.check",
        {},
    )

    expect(result["success"] is True, "TA check tool should report success")
    expect(
        result["summary"]["all_passed"] is True,
        "Summary should indicate all gates passed",
    )
    expect(
        Path(result["artifact_path"]).exists(),
        "Artifact path returned by TA tool must exist",
    )
    expect(
        Path(result.get("history_path", history)).exists(),
        "History path should be present and exist",
    )


@pytest.mark.asyncio
async def test_plan_research_includes_rate_limit(tmp_path, monkeypatch):
    dataset = _write_dataset(tmp_path)
    profile = get_default_profile("generic").model_copy(
        update={
            "name": "rate-limit",
            "research_rate_limit": {
                "min_interval_seconds": 1.5,
                "burst": 3,
            },
        }
    )

    monkeypatch.setattr(
        HotpassMCPServer,
        "_load_industry_profile",
        lambda self, name: profile,
    )

    class DummyOutcome:
        def __init__(self, plan_payload: dict[str, object]):
            self._payload: dict[str, Any] = {
                "plan": plan_payload,
                "steps": [],
                "enriched_row": None,
                "provenance": None,
                "elapsed_seconds": 0.0,
                "success": True,
                "artifact_path": None,
            }

        @property
        def success(self) -> bool:
            return True

        def to_dict(self) -> dict[str, Any]:
            return self._payload

    def fake_plan(self, context: ResearchContext) -> DummyOutcome:
        expect(
            context.profile is profile,
            "Server should pass custom profile to orchestrator",
        )
        plan_payload: dict[str, object] = {
            "entity_name": "Example Flight School",
            "entity_slug": "example-flight-school",
            "query": None,
            "target_urls": [],
            "allow_network": context.allow_network,
            "authority_sources": [],
            "backfill_fields": [],
            "rate_limit": {
                "min_interval_seconds": 1.5,
                "burst": 3,
            },
        }
        return DummyOutcome(plan_payload)

    monkeypatch.setattr(ResearchOrchestrator, "plan", fake_plan, raising=False)

    server = HotpassMCPServer()
    result = await server._execute_tool(  # pylint: disable=protected-access
        "hotpass.plan.research",
        {
            "dataset_path": str(dataset),
            "row_id": "0",
            "allow_network": False,
            "profile": "rate-limit",
        },
    )

    expect(result["success"] is True, "Plan research should succeed with custom profile")
    plan = result["outcome"]["plan"]
    rate_limit = plan.get("rate_limit")
    if rate_limit is None:
        raise AssertionError("Plan should include rate limit details")
    expect(
        rate_limit["min_interval_seconds"] == 1.5,
        "Rate limit interval should propagate",
    )
    expect(rate_limit["burst"] == 3, "Rate limit burst should propagate")
