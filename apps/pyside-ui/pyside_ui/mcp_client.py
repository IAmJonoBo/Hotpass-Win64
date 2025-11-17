from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Mapping, Protocol, Type


@dataclass(slots=True)
class ClientMCPRequest:
    method: str
    params: dict[str, Any]
    id: int | str | None = None


@dataclass(slots=True)
class MCPCallResult:
    """Container for MCP tool responses."""

    success: bool
    payload: dict[str, Any]
    error: str | None = None


class MCPClient:
    """Minimal synchronous wrapper around the Hotpass MCP server."""

    def __init__(self, server: _SupportsHandleRequest | None = None) -> None:
        if server is None:
            from hotpass.mcp.server import HotpassMCPServer, MCPRequest

            self._server: _SupportsHandleRequest = HotpassMCPServer()
            self._request_type: Type[object] = MCPRequest
        else:
            self._server = server
            self._request_type = ClientMCPRequest

    def list_tools(self, role: str = "operator") -> list[dict[str, Any]]:
        """Return the tools visible to a given role."""

        response = self._run(
            self._server.handle_request(
                self._request_type(method="tools/list", params={"role": role})
            )
        )
        if response.error:
            return []

        payload = response.result or {}
        tools = payload.get("tools", [])
        return [tool for tool in tools if isinstance(tool, Mapping)]

    def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        role: str | None = None,
    ) -> MCPCallResult:
        """Call a single MCP tool and surface success/error details."""

        params: dict[str, Any] = {"name": name, "arguments": dict(arguments or {})}
        if role:
            params["role"] = role

        response = self._run(
            self._server.handle_request(self._request_type(method="tools/call", params=params))
        )
        if response.error:
            message = response.error.get("message") if isinstance(response.error, Mapping) else str(response.error)
            return MCPCallResult(False, {}, message)

        payload: dict[str, Any] = {}
        if isinstance(response.result, Mapping):
            payload = dict(response.result)
        elif response.result is not None:
            payload = {"result": response.result}

        success_flag = payload.get("success")
        success = success_flag is True or (success_flag is None and response.error is None)
        return MCPCallResult(success, payload, None if success else payload.get("error"))

    def _run(self, coroutine: Awaitable[_MCPResponseLike]) -> _MCPResponseLike:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coroutine)
        finally:
            loop.close()


class _SupportsHandleRequest(Protocol):
    async def handle_request(self, request: object) -> object: ...


class _MCPResponseLike(Protocol):
    error: Mapping[str, Any] | None
    result: Any
    id: int | str | None
