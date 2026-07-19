"""
Final report node.

Assembles everything the pipeline produced into one clean markdown
document: task, cited research, final code, test results, and a full log
of human interventions. This is the artifact a non-technical reviewer
(or your recruiter) actually reads.
"""

from __future__ import annotations

from datetime import datetime, timezone

from graph.state import GraphState, HistoryEvent


def _render_report(state: GraphState) -> str:
    lines = [f"# Task Report\n", f"**Task:** {state['task']}\n"]

    lines.append("## Research Sources\n")
    for note in state.get("research_notes", []):
        lines.append(f"- **Query:** {note['source']}\n\n  {note['summary'][:500]}\n")

    lines.append("## Final Code\n")
    lines.append(f"```{state.get('code_language', 'python')}\n{state.get('generated_code', '')}\n```\n")

    lines.append("## Test Results\n")
    for i, tr in enumerate(state.get("test_results", []), start=1):
        status = "✅ PASSED" if tr["passed"] else "❌ FAILED"
        lines.append(f"**Attempt {i}: {status}**\n")
        if tr["output"]:
            lines.append(f"```\n{tr['output']}\n```\n")
        if tr.get("error"):
            lines.append(f"Error:\n```\n{tr['error']}\n```\n")

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
        provider_counts: dict[str, int] = {}
        for entry in state["token_usage"]:
            meta = {k: v for k, v in entry.items() if k != "node"}
            total_in += meta.get("input_tokens", 0) or 0
            total_out += meta.get("output_tokens", 0) or 0
            total_total += meta.get("total_tokens", 0) or 0
            provider = meta.get("model_name", entry.get("node", "unknown"))
            provider_counts[provider] = provider_counts.get(provider, 0) + 1

        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| **Total input tokens** | {total_in:,} |")
        lines.append(f"| **Total output tokens** | {total_out:,} |")
        lines.append(f"| **Total tokens consumed** | {total_total:,} |")
        lines.append(f"| **LLM calls** | {len(state['token_usage'])} |")
        lines.append("")

    return "\n".join(lines)


def final_report_node(state: GraphState) -> dict:
    report = _render_report(state)

    out_path = f"reports/report_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.md"
    try:
        import os

        os.makedirs("reports", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
    except OSError:
        pass  # report is still returned in state even if disk write fails

    return {
        "final_report": report,
        "history": [
            HistoryEvent(node="final_report", summary=f"Report written to {out_path}", timestamp=datetime.now(timezone.utc).isoformat())
        ],
    }
