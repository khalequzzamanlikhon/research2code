"""
Shared graph state.

This is the single source of truth passed between every node. Keeping it a
typed schema (rather than a loose dict) is one of the "pro elements" of this
project -- it makes the graph self-documenting and lets your IDE/linter catch
node bugs before runtime.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Literal, TypedDict


class ResearchNote(TypedDict):
    source: str
    summary: str


class TestResult(TypedDict):
    passed: bool
    output: str
    error: str | None


class HistoryEvent(TypedDict):
    node: str
    summary: str
    timestamp: str


ApprovalStatus = Literal["pending", "approved", "rejected", "not_required"]


class GraphState(TypedDict, total=False):
    # --- input -----------------------------------------------------------
    task: str

    # --- researcher output -------------------------------------------------
    research_notes: Annotated[list[ResearchNote], add]

    # --- coder output ------------------------------------------------------
    generated_code: str
    generated_files: dict[str, str]  # multi-file: filename → content
    entrypoint: str  # multi-file: which file to execute (e.g. "main.py")
    code_language: str

    # --- evaluator output ----------------------------------------------------
    evaluation_scores: Annotated[list[dict], add]

    # --- reviewer output -----------------------------------------------------
    test_results: Annotated[list[TestResult], add]
    iteration_count: int
    max_iterations: int

    # --- human-in-the-loop ---------------------------------------------------
    approval_status: ApprovalStatus
    approval_feedback: str | None

    # --- bookkeeping ---------------------------------------------------------
    history: Annotated[list[HistoryEvent], add]
    next_node: str
    token_usage: Annotated[list[dict], add]

    # --- final output ----------------------------------------------------------
    final_report: str | None


def new_state(task: str, max_iterations: int = 3) -> GraphState:
    """Factory for a fresh run's initial state."""
    return GraphState(
        task=task,
        research_notes=[],
        generated_code="",
        code_language="python",
        test_results=[],
        iteration_count=0,
        max_iterations=max_iterations,
        approval_status="pending",
        approval_feedback=None,
        history=[],
        next_node="researcher",
        token_usage=[],
        final_report=None,
    )
