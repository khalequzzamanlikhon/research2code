"""
Researcher node.

Cheaper/faster model (Haiku) by design -- research is high-volume,
low-reasoning-depth work compared to coding, so routing it to a smaller
model is a deliberate cost decision worth calling out in the README.
"""

from __future__ import annotations

from datetime import datetime, timezone

from graph.state import GraphState, HistoryEvent, ResearchNote
from tools.async_utils import run_async
from tools.llm_provider import get_llm, get_model_name
from tools.mcp_client import SERVERS, MCPToolClient

SYSTEM_PROMPT = """You are a technical researcher. Given a coding/research task, \
produce 2-4 short, specific search queries that would find the current best \
practice or approach. Return ONLY the queries, one per line, no numbering."""


async def _gather_research(task: str) -> tuple[list[ResearchNote], dict]:
    llm = get_llm("researcher", max_tokens=300)
    query_resp = llm.invoke([("system", SYSTEM_PROMPT), ("user", task)])
    usage = getattr(query_resp, "usage_metadata", None) or {}
    queries = [q.strip("- \n").strip() for q in query_resp.content.split("\n") if q.strip()]

    notes: list[ResearchNote] = []
    async with MCPToolClient(SERVERS["docs_search"]) as search_client:
        for query in queries[:4]:
            raw = await search_client.call("search", query=query, max_results=3)
            notes.append(ResearchNote(source=query, summary=raw))
    return notes, usage


def researcher_node(state: GraphState) -> dict:
    notes, usage = run_async(_gather_research(state["task"]))
    if usage:
        usage["model_name"] = get_model_name("researcher")
    return {
        "research_notes": notes,
        "token_usage": [{"node": "researcher", **usage}] if usage else [],
        "history": [
            HistoryEvent(
                node="researcher",
                summary=f"Ran {len(notes)} search queries.",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        ],
        "next_node": "coder",
    }
