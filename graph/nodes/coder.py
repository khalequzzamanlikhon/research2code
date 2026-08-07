"""
Coder node.

Writes code into shared state ONLY -- it never touches disk directly.
File writes happen later, through the filesystem MCP server, and only
after the human-in-the-loop gate approves. On retries, the reviewer's
failure output is fed back in so the model can actually fix the bug
instead of regenerating blind.

Supports both single-file and multi-file generation. The coder decides
which mode to use based on the task complexity.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from graph.state import GraphState, HistoryEvent
from tools.llm_provider import get_llm, get_model_name

SYSTEM_PROMPT = """You are a senior software engineer. Write a complete,
self-contained Python solution for the given task, informed by the research
notes provided.

**For simple single-file tasks** (one function/class, no dependencies):
Return ONLY raw Python code with a `if __name__ == "__main__":` block
containing assert-based self-tests. NO markdown fences, NO explanations.

**For complex multi-file tasks** (multiple modules, separate test files,
dependencies): Return a JSON object with this exact structure — NO markdown
fences, NO commentary outside the JSON:
{
  "files": {
    "main.py": "... implementation ...",
    "utils.py": "... helpers ...",
    "test_solution.py": "... assert-based tests ..."
  },
  "entrypoint": "main.py",
  "install_requires": ["requests"]
}

Rules:
- "entrypoint" is the file to run for testing
- "install_requires" is optional — list pip packages the solution needs
- Every test file MUST use assert statements (pytest not required)
- Return ONLY the code (single-file) or ONLY the JSON (multi-file). Nothing else.
- The first character of your response must be either a letter/import/def/class
  (single-file) or a `{` (multi-file JSON)."""


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
            # Include previous code for retry context
            if state.get("generated_files"):
                parts.append("\nPrevious multi-file solution:")
                for fname, fcontent in state["generated_files"].items():
                    parts.append(f"--- {fname} ---\n{fcontent}")
            elif state.get("generated_code"):
                parts.append(f"\nPrevious code:\n{state['generated_code']}")

    return "\n".join(parts)


def _parse_coder_output(raw: str) -> tuple[str | None, dict[str, str] | None, str | None, list[str] | None]:
    """Parse coder output. Returns (single_code, multi_files, entrypoint, install_requires).

    - Single-file mode: single_code is set, others are None.
    - Multi-file mode: multi_files/entrypoint are set, single_code is None.
    """
    stripped = raw.strip()

    # Strip markdown fences
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1] if "\n" in stripped else stripped[3:]
    if stripped.endswith("```"):
        stripped = stripped.rsplit("```", 1)[0]
    stripped = stripped.strip()

    # Try multi-file JSON parse
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict) and "files" in data and "entrypoint" in data:
                return None, data["files"], data["entrypoint"], data.get("install_requires")
        except (json.JSONDecodeError, TypeError, KeyError):
            pass  # Not valid multi-file JSON — fall through to single-file

    # Single-file mode
    return stripped, None, None, None


def coder_node(state: GraphState) -> dict:
    llm = get_llm("coder", max_tokens=3000)
    prompt = _build_prompt(state)
    response = llm.invoke([("system", SYSTEM_PROMPT), ("user", prompt)])
    raw = response.content.strip()

    single_code, multi_files, entrypoint, install_requires = _parse_coder_output(raw)

    usage = getattr(response, "usage_metadata", None) or {}
    if usage:
        usage["model_name"] = get_model_name("coder")

    if multi_files is not None:
        # Multi-file mode
        total_lines = sum(len(c.splitlines()) for c in multi_files.values())
        summary = (
            f"Generated {len(multi_files)} files ({total_lines} lines total) "
            f"(iteration {state.get('iteration_count', 0)})."
        )
        return {
            "generated_code": json.dumps(multi_files),  # fallback serialization
            "generated_files": multi_files,
            "entrypoint": entrypoint,
            "history": [HistoryEvent(node="coder", summary=summary, timestamp=datetime.now(timezone.utc).isoformat())],
            "token_usage": [{"node": "coder", **usage}] if usage else [],
            "next_node": "evaluator",
        }

    # Single-file mode (backward compatible)
    code = single_code or ""
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
        "next_node": "evaluator",
    }
