"""
Supervisor routing logic.

Deliberately plain Python (not an LLM call) -- routing here is cheap,
deterministic, and auditable, which is what you want for a hard
"don't loop forever" guarantee. The graph topology itself is linear
(researcher -> coder -> reviewer) for the parts that always happen in
order; this module supplies the one genuinely conditional decision point:
what to do after the reviewer runs.
"""

from __future__ import annotations

from graph.state import GraphState

MAX_ITERATIONS_DEFAULT = 3


def route_after_review(state: GraphState) -> str:
    """
    Called as a LangGraph conditional edge after the reviewer node.
    Returns the name of the next node to run.
    """
    test_results = state.get("test_results", [])
    if not test_results:
        # Shouldn't happen, but fail safe rather than loop.
        return "human_approval"

    last = test_results[-1]
    max_iters = state.get("max_iterations", MAX_ITERATIONS_DEFAULT)

    if last["passed"]:
        return "human_approval"

    if state.get("iteration_count", 0) >= max_iters:
        # Bounded retries: stop looping, surface the failing state to a
        # human instead of burning tokens indefinitely.
        return "human_approval"

    return "coder"  # loop back; coder_node reads the failure from state
