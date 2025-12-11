from __future__ import annotations

from pathlib import Path
from typing import Any

from dataclasses import dataclass

from pyside_ui.mcp_client import MCPCallResult, MCPClient
from pyside_ui.simulated_runs import SimulationRunLoader


@dataclass
class _Response:
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    id: int | None = None


class _StubServer:
    def __init__(self) -> None:
        self.calls: list[object] = []

    async def handle_request(self, request: object) -> _Response:
        self.calls.append(request)
        if request.method == "tools/list":
            return _Response(result={"tools": [{"name": "hotpass.qa", "description": "QA", "inputSchema": {}}]})
        if request.method == "tools/call" and request.params.get("name") == "hotpass.qa":
            arguments: dict[str, Any] = request.params.get("arguments", {})  # type: ignore[assignment]
            return _Response(result={"success": True, "echo": arguments})
        return _Response(error={"code": 404, "message": "Unknown tool"})


def test_mcp_client_handles_basic_calls() -> None:
    client = MCPClient(server=_StubServer())

    tools = client.list_tools()
    assert {tool["name"] for tool in tools} == {"hotpass.qa"}

    response = client.call_tool("hotpass.qa", {"target": "all"})
    assert isinstance(response, MCPCallResult)
    assert response.success is True
    assert response.payload["echo"] == {"target": "all"}

    failure = client.call_tool("hotpass.refine", {"input_path": "data"})
    assert failure.success is False
    assert "Unknown" in (failure.error or "")


def test_simulated_runs_are_loaded_from_disk() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    loader = SimulationRunLoader(repo_root / "data" / "pyside-ui")

    available = loader.available()
    assert "refine" in available

    run = loader.load("refine")
    assert run.tool == "hotpass.refine"
    assert run.arguments["profile"] == "generic"
    assert run.result["success"] is True
