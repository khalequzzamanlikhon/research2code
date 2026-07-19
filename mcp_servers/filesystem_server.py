"""
MCP server: safe, sandboxed filesystem access.

Runs as a standalone stdio process (LangGraph never imports this file
directly -- it talks to it over the Model Context Protocol via
tools/mcp_client.py). All paths are resolved relative to WORKDIR and
jailed there, so a compromised or hallucinating agent can't write outside
the sandbox no matter what path string it produces.

Run standalone for a smoke test:
    python mcp_servers/filesystem_server.py
"""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

WORKDIR = Path(os.environ.get("AGENT_SANDBOX_DIR", "./sandbox_workspace")).resolve()
WORKDIR.mkdir(parents=True, exist_ok=True)

mcp = FastMCP("filesystem")


def _safe_path(relative_path: str) -> Path:
    """Resolve a path and refuse anything that escapes WORKDIR."""
    candidate = (WORKDIR / relative_path).resolve()
    if WORKDIR not in candidate.parents and candidate != WORKDIR:
        raise ValueError(f"Refusing to access path outside sandbox: {relative_path}")
    return candidate


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write text content to a file inside the sandbox workspace, creating parent dirs as needed."""
    target = _safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} bytes to {target.relative_to(WORKDIR)}"


@mcp.tool()
def read_file(path: str) -> str:
    """Read a text file from the sandbox workspace."""
    target = _safe_path(path)
    if not target.exists():
        return f"ERROR: {path} does not exist"
    return target.read_text(encoding="utf-8")


@mcp.tool()
def list_files(path: str = ".") -> str:
    """List files under a directory inside the sandbox workspace."""
    target = _safe_path(path)
    if not target.exists():
        return f"ERROR: {path} does not exist"
    entries = sorted(p.relative_to(WORKDIR).as_posix() for p in target.rglob("*"))
    return "\n".join(entries) if entries else "(empty)"


if __name__ == "__main__":
    mcp.run(transport="stdio")
