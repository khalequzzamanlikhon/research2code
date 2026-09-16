"""
Reviewer/Tester node.

Executes the coder's output inside the sandbox (never in-process) and
records pass/fail. Does not decide routing itself -- it just reports
results into state; the Supervisor node is the only place that decides
whether to loop back to the Coder, proceed to human approval, or bail out
after too many retries. Keeping routing centralized in the Supervisor is
what makes this a real state machine instead of nodes silently deciding
their own successors.
"""

from __future__ import annotations

from datetime import UTC, datetime

from graph.state import GraphState, HistoryEvent, TestResult
from sandbox.executor import run_python_code, run_python_project


def reviewer_node(state: GraphState) -> dict:
    # Multi-file mode
    if state.get("generated_files") and state.get("entrypoint"):
        result = run_python_project(state["generated_files"], state["entrypoint"])
    else:
        # Single-file mode (backward compatible)
        result = run_python_code(state["generated_code"])

    test_result = TestResult(
        passed=result.passed,
        output=result.stdout,
        error=result.stderr if not result.passed else None,
    )

    summary = (
        f"Execution {'PASSED' if result.passed else 'FAILED'} "
        f"(sandbox={'docker' if result.used_docker else 'subprocess-fallback'})"
    )

    return {
        "test_results": [test_result],
        "iteration_count": state.get("iteration_count", 0) + 1,
        "history": [
            HistoryEvent(node="reviewer", summary=summary, timestamp=datetime.now(UTC).isoformat())
        ],
        "next_node": "supervisor",
    }
