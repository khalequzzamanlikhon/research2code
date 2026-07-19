"""
Coder node.

Writes code into shared state ONLY -- it never touches disk directly.
File writes happen later, through the filesystem MCP server, and only
after the human-in-the-loop gate approves. On retries, the reviewer's
failure output is fed back in so the model can actually fix the bug
instead of regenerating blind.
"""

from __future__ import annotations

from datetime import datetime, timezone

from graph.state import GraphState, HistoryEvent
from tools.llm_provider import get_llm

SYSTEM_PROMPT = """You are a senior software engineer. Write a complete, \
self-contained Python solution for the given task, informed by the research \
notes provided. Include a short `if __name__ == "__main__":` block with a \
simple usage example or basic self-test using assert statements so the \
reviewer agent can execute the file directly.

CRITICAL: Return ONLY raw Python code. NO markdown fences (```python), NO \
explanations, NO commentary. The first line must be either `def`, `class`, \
`import`, or a comment — never a backtick. If I can't run your output \
straight through `python -c`, you failed."""


def _build_prompt(state: GraphState) -> str:
    parts = [f"Task: {state['task']}"]

    if state.get("research_notes"):
        parts.append("\nResearch notes:")
        for note in state["research_notes"]:
            parts.append(f"- {note['source']}:\n{note['summary']}")

    if state.get("test_results"):
        last = state["test_results"][-1]
        if not last["passed"]:
            parts.append(
                "\nThe previous attempt FAILED. Fix the bug. "
                f"Error output:\n{last['error'] or last['output']}"
            )
            parts.append(f"\nPrevious code:\n{state['generated_code']}")

    return "\n".join(parts)


def coder_node(state: GraphState) -> dict:
    llm = get_llm("coder", max_tokens=2000)
    prompt = _build_prompt(state)
    response = llm.invoke([("system", SYSTEM_PROMPT), ("user", prompt)])
    code = response.content.strip()

    # Guard: strip markdown fences if the model ignored the prompt
    if code.startswith("```"):
        code = code.split("\n", 1)[-1] if "\n" in code else code[3:]
    if code.endswith("```"):
        code = code.rsplit("```", 1)[0]
    code = code.strip()

    usage = getattr(response, "usage_metadata", None) or {}

    return {
        "generated_code": code,
        "history": [
            HistoryEvent(
                node="coder",
                summary=f"Generated {len(code.splitlines())} lines of code "
                f"(iteration {state.get('iteration_count', 0)}).",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        ],
        "token_usage": [{"node": "coder", **usage}] if usage else [],
        "next_node": "reviewer",
    }
