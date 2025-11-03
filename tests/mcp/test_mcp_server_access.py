import pytest

from hotpass.mcp.server import HotpassMCPServer, MCPRequest


@pytest.mark.asyncio
async def test_observer_sees_limited_tools_and_blocked_calls():
    server = HotpassMCPServer()

    list_response = await server.handle_request(
        MCPRequest(method="tools/list", params={"role": "observer"})
    )
    assert list_response.error is None
    tool_names = {tool["name"] for tool in list_response.result["tools"]}
    assert "hotpass.refine" not in tool_names
    assert "hotpass.qa" in tool_names

    blocked = await server.handle_request(
        MCPRequest(
            method="tools/call",
            params={"role": "observer", "name": "hotpass.refine", "arguments": {}},
        )
    )
    assert blocked.error and blocked.error["code"] == 403


@pytest.mark.asyncio
async def test_researcher_can_request_intelligent_search():
    server = HotpassMCPServer()
    response = await server.handle_request(
        MCPRequest(
            method="tools/call",
            params={
                "role": "researcher",
                "name": "hotpass.search.intelligent",
                "arguments": {"query": "Acme Aviation"},
            },
        )
    )
    assert response.error is None
    assert response.result["success"] is True
    assert "strategy" in response.result


@pytest.mark.asyncio
async def test_role_override_argument_is_sanitised():
    server = HotpassMCPServer()
    captured: dict[str, dict[str, object]] = {}

    tool = server._tool_registry["hotpass.qa"].definition

    async def _capture(args: dict[str, object]) -> dict[str, object]:
        captured["args"] = args
        return {"success": True}

    server.register_tool(tool, _capture)

    response = await server.handle_request(
        MCPRequest(
            method="tools/call",
            params={
                "name": "hotpass.qa",
                "arguments": {"target": "all", "_role": "admin"},
            },
        )
    )

    assert response.error is None
    assert response.result["success"] is True
    assert captured["args"] == {"target": "all"}
