"""
Thin wrapper around the official MCP python SDK for connecting LangGraph
agent nodes to MCP servers over stdio.

Why this file exists: instead of every node importing a server module
directly and calling its functions like a library, nodes go through this
client, which speaks the actual Model Context Protocol (list_tools /
call_tool over a JSON-RPC session). That's the "MCP-based tool discovery"
pro element -- swap a server for a completely different implementation
(even one written in another language) and no agent code changes.
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@dataclass
class MCPServerSpec:
    name: str
    command: str
    args: list[str]


class MCPToolClient:
    """
    Connects to one MCP server process, lists its tools, and exposes a
    simple `call(tool_name, **kwargs)` interface. Use as an async context
    manager so the subprocess and session are cleaned up correctly.

    Example:
        spec = MCPServerSpec("filesystem", "python", ["mcp_servers/filesystem_server.py"])
        async with MCPToolClient(spec) as fs:
            tools = await fs.list_tools()
            result = await fs.call("write_file", path="out.py", content="print(1)")
    """

    def __init__(self, spec: MCPServerSpec):
        self.spec = spec
        self._session: ClientSession | None = None
        self._stack = contextlib.AsyncExitStack()

    async def __aenter__(self) -> "MCPToolClient":
        params = StdioServerParameters(command=self.spec.command, args=self.spec.args)
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self._stack.aclose()
        self._session = None

    async def list_tools(self) -> list[dict]:
        assert self._session is not None, "use `async with MCPToolClient(...) as client`"
        resp = await self._session.list_tools()
        return [{"name": t.name, "description": t.description} for t in resp.tools]

    async def call(self, tool_name: str, **kwargs: Any) -> str:
        assert self._session is not None, "use `async with MCPToolClient(...) as client`"
        result = await self._session.call_tool(tool_name, arguments=kwargs)
        # MCP tool results are a list of content blocks; flatten text blocks.
        chunks = []
        for block in result.content:
            if getattr(block, "type", None) == "text":
                chunks.append(block.text)
            else:
                chunks.append(json.dumps(getattr(block, "model_dump", lambda: str(block))()))
        return "\n".join(chunks)


# Central registry of servers this project ships with. Add new MCP servers
# here and every node can reach them by name without hardcoding paths.
SERVERS = {
    "filesystem": MCPServerSpec(
        name="filesystem",
        command="python",
        args=["mcp_servers/filesystem_server.py"],
    ),
    "docs_search": MCPServerSpec(
        name="docs_search",
        command="python",
        args=["mcp_servers/docs_search_server.py"],
    ),
}
