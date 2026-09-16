"""
Final report node.

Assembles everything the pipeline produced into one clean markdown
document: task, cited research, final code, test results, and a full log
of human interventions. This is the artifact a non-technical reviewer
(or your recruiter) actually reads.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime

from graph.state import GraphState, HistoryEvent
from tools.token_tracker import calculate_cost, format_cost


def _render_report(state: GraphState) -> str:
    lines = ["# Task Report\n", f"**Task:** {state['task']}\n"]

    lines.append("## Research Sources\n")
    for note in state.get("research_notes", []):
        lines.append(f"- **Query:** {note['source']}\n\n  {note['summary'][:500]}\n")

    lines.append("## Final Code\n")
    lang = state.get('code_language', 'python')
    if state.get("generated_files") and state.get("entrypoint"):
        lines.append(f"**Multi-file project** (entrypoint: `{state['entrypoint']}`)\n")
        for fname in sorted(state["generated_files"].keys()):
            fcontent = state["generated_files"][fname]
            lines.append(f"### `{fname}`\n")
            lines.append(f"```{lang}\n{fcontent}\n```\n")
    else:
        lines.append(f"```{lang}\n{state.get('generated_code', '')}\n```\n")

    lines.append("## Test Results\n")
    for i, tr in enumerate(state.get("test_results", []), start=1):
        status = "✅ PASSED" if tr["passed"] else "❌ FAILED"
        lines.append(f"**Attempt {i}: {status}**\n")
        if tr["output"]:
            lines.append(f"```\n{tr['output']}\n```\n")
        if tr.get("error"):
            lines.append(f"Error:\n```\n{tr['error']}\n```\n")

    # Evaluation scores (LLM-as-judge)
    if state.get("evaluation_scores"):
        lines.append("## Code Quality Evaluation (LLM-as-Judge)\n")
        for i, es in enumerate(state["evaluation_scores"], start=1):
            if "error" in es:
                lines.append(f"- **Attempt {i}:** Evaluation error — {es['error']}\n")
            else:
                lines.append(f"**Attempt {i}:** Overall **{es.get('overall', 'N/A')}/5**\n")
                for dim in ["correctness", "efficiency", "readability", "robustness", "test_quality"]:
                    if dim in es:
                        bar = "█" * es[dim] + "░" * (5 - es[dim])
                        lines.append(f"- {dim}: {es[dim]}/5 `{bar}`")
                if es.get("summary"):
                    lines.append(f"\n> {es['summary']}\n")
        lines.append("")

    lines.append("## Human Approval\n")
    lines.append(f"- Status: **{state.get('approval_status', 'not_required')}**")
    if state.get("approval_feedback"):
        lines.append(f"- Feedback: {state['approval_feedback']}")
    lines.append("")

    lines.append("## Execution Log\n")
    for event in state.get("history", []):
        lines.append(f"- `{event['timestamp']}` **{event['node']}** — {event['summary']}")

    if state.get("token_usage"):
        lines.append("\n## Token / Cost Summary\n")
        total_in = total_out = total_total = 0
        total_cost = 0.0
        per_node: list[tuple[str, str, int, float]] = []
        for entry in state["token_usage"]:
            meta = {k: v for k, v in entry.items() if k != "node"}
            in_tok = meta.get("input_tokens", 0) or 0
            out_tok = meta.get("output_tokens", 0) or 0
            tok_total = meta.get("total_tokens", 0) or 0
            total_in += in_tok
            total_out += out_tok
            total_total += tok_total
            model = meta.get("model_name", entry.get("node", "unknown"))
            cost = calculate_cost(model, in_tok, out_tok)
            total_cost += cost
            per_node.append((entry.get("node", "?"), model, tok_total, cost))

        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| **Total input tokens** | {total_in:,} |")
        lines.append(f"| **Total output tokens** | {total_out:,} |")
        lines.append(f"| **Total tokens consumed** | {total_total:,} |")
        lines.append(f"| **LLM calls** | {len(state['token_usage'])} |")
        lines.append(f"| **Estimated cost** | {format_cost(total_cost)} |")
        lines.append("")
        lines.append("### Per-Node Breakdown\n")
        lines.append("| Node | Model | Tokens | Cost |")
        lines.append("|------|-------|--------|------|")
        for node, model, tok, cost in per_node:
            lines.append(f"| {node} | {model} | {tok:,} | {format_cost(cost)} |")
        lines.append("")

    return "\n".join(lines)


def final_report_node(state: GraphState) -> dict:
    report = _render_report(state)

    out_path = f"reports/report_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.md"
    try:
        import os

        os.makedirs("reports", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
    except OSError:
        print(f"[final_report] WARNING: Failed to write report to {out_path}", file=sys.stderr)

    return {
        "final_report": report,
        "history": [
            HistoryEvent(node="final_report", summary=f"Report written to {out_path}", timestamp=datetime.now(UTC).isoformat())
        ],
    }
