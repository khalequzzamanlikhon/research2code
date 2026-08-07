"""
Human-in-the-loop approval gate.

This is the standout production pattern of the whole project: the graph
genuinely pauses (via LangGraph's `interrupt`) before anything risky
happens -- here, writing the final code to disk through the filesystem MCP
server. Execution state is checkpointed, so the process can be killed and
resumed later and the graph will still be sitting at this exact point
waiting for a decision.

The frontend (Streamlit or CLI) resumes the graph by invoking it again
with a `Command(resume=...)` payload containing the human's decision.
"""

from __future__ import annotations

from datetime import datetime, timezone

from langgraph.types import interrupt

from graph.state import GraphState, HistoryEvent
from tools.async_utils import run_async
from tools.mcp_client import SERVERS, MCPToolClient


async def _write_approved_files(files: dict[str, str]) -> str:
    results = []
    async with MCPToolClient(SERVERS["filesystem"]) as fs:
        for filename, content in files.items():
            r = await fs.call("write_file", path=filename, content=content)
            results.append(r)
    return "; ".join(results)


async def _write_approved_code(code: str) -> str:
    async with MCPToolClient(SERVERS["filesystem"]) as fs:
        return await fs.call("write_file", path="solution.py", content=code)


def human_approval_node(state: GraphState) -> dict:
    last_result = state["test_results"][-1] if state.get("test_results") else None

    # Build interrupt payload — include all files in multi-file mode
    interrupt_payload: dict = {
        "question": "Approve writing this code to disk?",
        "last_test_result": last_result,
    }
    is_multi_file = bool(state.get("generated_files") and state.get("entrypoint"))
    if is_multi_file:
        interrupt_payload["files"] = state["generated_files"]
        interrupt_payload["entrypoint"] = state["entrypoint"]
        interrupt_payload["code"] = state.get("generated_code", "")  # fallback for frontends
    else:
        interrupt_payload["code"] = state["generated_code"]

    decision = interrupt(interrupt_payload)

    approved = bool(decision.get("approved"))
    feedback = decision.get("feedback")

    history = [
        HistoryEvent(
            node="human_approval",
            summary=f"Human {'approved' if approved else 'rejected'} the code."
            + (f" Feedback: {feedback}" if feedback else ""),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    ]

    if approved:
        if is_multi_file:
            write_result = run_async(_write_approved_files(state["generated_files"]))
        else:
            write_result = run_async(_write_approved_code(state["generated_code"]))
        history.append(
            HistoryEvent(node="human_approval", summary=write_result, timestamp=datetime.now(timezone.utc).isoformat())
        )
        return {"approval_status": "approved", "approval_feedback": feedback, "history": history, "next_node": "final_report"}

    return {"approval_status": "rejected", "approval_feedback": feedback, "history": history, "next_node": "final_report"}
