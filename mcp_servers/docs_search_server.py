"""
MCP server: web/docs search tool for the Researcher agent.

Wraps a search API (Tavily by default -- swap the implementation of
`_search` for SerpAPI, Bing, or an internal docs index without touching
any agent code, since agents only ever see the MCP tool interface).

Requires TAVILY_API_KEY in the environment. Falls back to a stub response
if the key isn't set, so the graph still runs end-to-end in a demo/CI
environment without network access.

Run standalone for a smoke test:
    python mcp_servers/docs_search_server.py
"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("docs_search")

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")


def _search(query: str, max_results: int = 5) -> list[dict]:
    if not TAVILY_API_KEY:
        return [
            {
                "title": "STUB RESULT (set TAVILY_API_KEY for real search)",
                "url": "https://example.com",
                "content": f"No search API key configured. Query was: {query!r}",
            }
        ]

    from tavily import TavilyClient  # imported lazily so the module loads without the dep

    client = TavilyClient(api_key=TAVILY_API_KEY)
    response = client.search(query=query, max_results=max_results)
    return [
        {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")}
        for r in response.get("results", [])
    ]


@mcp.tool()
def search(query: str, max_results: int = 5) -> str:
    """Search the web for current information relevant to a query. Returns titled snippets with source URLs."""
    results = _search(query, max_results=max_results)
    lines = []
    for r in results:
        lines.append(f"- {r['title']} ({r['url']})\n  {r['content'][:400]}")
    return "\n".join(lines) if lines else "No results found."


if __name__ == "__main__":
    mcp.run(transport="stdio")
