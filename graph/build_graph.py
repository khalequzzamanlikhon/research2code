"""
Assembles the full LangGraph StateGraph: nodes, edges (linear + conditional),
and a persistent checkpointer.

The checkpointer is what enables the "kill the process mid-run, restart,
resume where it left off" demo. SQLite is used by default (single file,
zero setup); swap `sqlite_checkpointer()` for a Postgres-backed one in
docker-compose for anything beyond a local demo.
"""

from __future__ import annotations

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from graph.nodes.coder import coder_node
from graph.nodes.evaluator import evaluator_node
from graph.nodes.final_report import final_report_node
from graph.nodes.human_approval import human_approval_node
from graph.nodes.researcher import researcher_node
from graph.nodes.reviewer import reviewer_node
from graph.state import GraphState
from graph.supervisor import route_after_review

CHECKPOINT_DB = "checkpoints.sqlite"


def build_graph(checkpoint_path: str = CHECKPOINT_DB):
    graph = StateGraph(GraphState)

    graph.add_node("researcher", researcher_node)
    graph.add_node("coder", coder_node)
    graph.add_node("evaluator", evaluator_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("human_approval", human_approval_node)
    graph.add_node("final_report", final_report_node)

    graph.set_entry_point("researcher")

    # Linear parts of the pipeline -- these always happen in this order.
    graph.add_edge("researcher", "coder")
    graph.add_edge("coder", "evaluator")
    graph.add_edge("evaluator", "reviewer")

    # The one real branch point: pass, fail-but-retry, or fail-out-of-retries.
    graph.add_conditional_edges(
        "reviewer",
        route_after_review,
        {"coder": "coder", "human_approval": "human_approval"},
    )

    graph.add_edge("human_approval", "final_report")
    graph.add_edge("final_report", END)

    conn = sqlite3.connect(checkpoint_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    return graph.compile(checkpointer=checkpointer)


def get_graph_png(checkpoint_path: str = CHECKPOINT_DB) -> bytes:
    """Export the compiled graph as a PNG for the README architecture diagram."""
    compiled = build_graph(checkpoint_path)
    png: bytes = compiled.get_graph().draw_mermaid_png()
    return png
