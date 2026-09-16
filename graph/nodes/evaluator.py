"""
LLM-as-Judge evaluator node.

Scores the coder's output on multiple quality dimensions BEFORE execution.
This is separate from the sandbox reviewer — the evaluator provides qualitative
feedback, while the reviewer provides quantitative pass/fail.

Results are appended to state so they appear in the final report. The evaluator
uses a cheaper model (same as researcher) to keep costs low.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from graph.state import GraphState, HistoryEvent
from tools.llm_provider import get_llm, get_model_name

EVAL_SYSTEM_PROMPT = """You are a strict code quality evaluator. Score the following
Python solution on each dimension from 1 (poor) to 5 (excellent). Be harsh —
a 4 is already very good. Deduct points for missing edge cases, inefficient
algorithms, unclear naming, or missing type hints.

Dimensions:
- correctness: Does the logic appear to solve the stated problem? (1-5)
- efficiency: Is the time/space complexity reasonable? (1-5)
- readability: Are names, structure, and comments clear? (1-5)
- robustness: Are edge cases, error handling, and input validation addressed? (1-5)
- test_quality: Are the included assertions comprehensive and meaningful? (1-5)

Return ONLY a JSON object with no markdown fences, no commentary:
{"correctness": N, "efficiency": N, "readability": N, "robustness": N, "test_quality": N, "overall": N.N, "summary": "one-sentence critique"}
"""


def evaluator_node(state: GraphState) -> dict:
    """Score the coder's output using an LLM judge.

    Runs after the coder but before the sandbox reviewer. Scores are purely
    qualitative — the reviewer node still owns pass/fail based on execution.
    """
    code = state.get("generated_code", "")
    task = state.get("task", "")

    if not code:
        return {
            "evaluation_scores": [{"error": "no code to evaluate"}],
            "history": [
                HistoryEvent(
                    node="evaluator",
                    summary="Skipped — no generated code to evaluate.",
                    timestamp=datetime.now(UTC).isoformat(),
                )
            ],
            "next_node": "reviewer",
        }

    llm = get_llm("researcher", max_tokens=300)
    prompt = f"Task: {task}\n\nCode to evaluate:\n```python\n{code[:3000]}\n```"

    try:
        response = llm.invoke([("system", EVAL_SYSTEM_PROMPT), ("user", prompt)])
        content = response.content.strip()

        # Strip markdown fences if the model included them
        if content.startswith("```"):
            content = content.split("\n", 1)[-1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()

        scores = json.loads(content)
    except (json.JSONDecodeError, Exception):
        scores = {"error": "evaluation parse failed", "raw": content[:200]}

    usage = getattr(response, "usage_metadata", None) or {}
    if usage:
        usage["model_name"] = get_model_name("researcher")

    return {
        "evaluation_scores": [scores],
        "token_usage": [{"node": "evaluator", **usage}] if usage else [],
        "history": [
            HistoryEvent(
                node="evaluator",
                summary=(
                    f"Overall score: {scores.get('overall', 'N/A')}/5"
                    if "overall" in scores
                    else "Evaluation completed (see report for scores)."
                ),
                timestamp=datetime.now(UTC).isoformat(),
            )
        ],
        "next_node": "reviewer",
    }
