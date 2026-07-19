"""
Benchmark runner for the multi-agent pipeline.

Measures success rate, iteration distribution, token consumption,
and provider failover across a set of predefined tasks.

Usage:
    python scripts/run_benchmark.py                     # run all tasks
    python scripts/run_benchmark.py --tasks 0 1          # run specific tasks by index
    python scripts/run_benchmark.py --quick              # run first 3 tasks only
    python scripts/run_benchmark.py --report-only        # re-generate report from saved results
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from langgraph.types import Command

load_dotenv()

from graph.build_graph import build_graph
from graph.state import new_state

# ---------------------------------------------------------------------------
# Benchmark task suite
# ---------------------------------------------------------------------------

BENCHMARK_TASKS: list[dict[str, Any]] = [
    {
        "id": "fibonacci",
        "task": "Write a function that returns the nth Fibonacci number using dynamic programming. Include assert-based tests.",
    },
    {
        "id": "lru-cache",
        "task": "Implement an LRU cache with get() and put() methods. Include assert-based tests.",
    },
    {
        "id": "rate-limiter",
        "task": "Implement a sliding window rate limiter. Include assert-based tests.",
    },
    {
        "id": "json-validator",
        "task": "Write a JSON schema validator that checks required fields, types, and enum values. Include assert-based tests.",
    },
    {
        "id": "anagram-grouper",
        "task": "Write a function that groups a list of strings into anagrams. Include assert-based tests.",
    },
]

RESULTS_DIR = Path("reports")
RESULTS_FILE = RESULTS_DIR / "benchmark_results.json"

MAX_ITERATIONS = 3
TIMEOUT_PER_TASK = 120  # seconds wall-clock


def run_single_task(task_def: dict[str, Any]) -> dict[str, Any]:
    """Run the pipeline on one task and return structured results."""
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    app = build_graph()

    start = time.monotonic()
    task_text = task_def["task"]
    task_id = task_def["id"]

    print(f"\n{'='*60}")
    print(f"Task: {task_id}")
    print(f"{'='*60}")
    print(f"Input: {task_text[:100]}...")

    result: dict[str, Any] = {
        "task_id": task_id,
        "task": task_text,
        "thread_id": thread_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "tests_passed": False,
        "iterations_used": 0,
        "human_approved": False,
        "total_tokens": 0,
        "duration_seconds": 0.0,
        "error": None,
        "final_report_snippet": "",
    }

    try:
        state = new_state(task_text, max_iterations=MAX_ITERATIONS)
        output = app.invoke(state, config=config)

        # Handle possible interrupt at human_approval
        app_state = app.get_state(config)
        if app_state.next and "human_approval" in app_state.next:
            interrupt_val = app_state.tasks[0].interrupts[0].value
            # Auto-approve for benchmarking (we want end-to-end completion)
            output = app.invoke(Command(resume={"approved": True, "feedback": None}), config=config)

        end = time.monotonic()
        result["duration_seconds"] = round(end - start, 2)

        # Extract metrics from final state
        final_state = app.get_state(config).values if hasattr(app.get_state(config), "values") else output
        if isinstance(final_state, dict):
            test_results = final_state.get("test_results", [])
            result["iterations_used"] = final_state.get("iteration_count", 0)
            result["human_approved"] = final_state.get("approval_status") == "approved"
            if test_results:
                result["tests_passed"] = any(
                    tr.get("passed", False) for tr in test_results[-3:]
                )

            # Token accounting
            token_usage = final_state.get("token_usage", [])
            total_tokens = 0
            for entry in token_usage:
                meta = {k: v for k, v in entry.items() if k != "node"}
                total_tokens += meta.get("total_tokens", 0) or 0
            result["total_tokens"] = total_tokens

            # Report snippet
            report = final_state.get("final_report", "")
            result["final_report_snippet"] = report[:300] if report else ""

        status = "✅" if result["tests_passed"] else "❌"
        print(f"\n{status} Result: passed={result['tests_passed']}, "
              f"iterations={result['iterations_used']}, "
              f"tokens={result['total_tokens']}, "
              f"duration={result['duration_seconds']}s")

    except Exception as e:
        result["error"] = str(e)
        print(f"\n❌ Task failed with error: {e}")

    return result


def generate_report(results: list[dict[str, Any]]) -> str:
    """Generate a markdown report from benchmark results."""
    total = len(results)
    passed = sum(1 for r in results if r["tests_passed"])
    approved = sum(1 for r in results if r["human_approved"])
    total_tokens = sum(r.get("total_tokens", 0) for r in results)
    total_duration = sum(r.get("duration_seconds", 0) for r in results)
    avg_iterations = (
        sum(r.get("iterations_used", 0) for r in results) / total if total else 0
    )

    lines = [
        "# Agent Pipeline Benchmark Report",
        "",
        f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"**Tasks run:** {total}",
        f"**Max iterations per task:** {MAX_ITERATIONS}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| **Success rate** (tests passed) | {passed}/{total} ({passed/total*100:.0f}%) |",
        f"| **Human approval rate** | {approved}/{total} ({approved/total*100:.0f}%) |",
        f"| **Avg iterations per task** | {avg_iterations:.1f} |",
        f"| **Total tokens consumed** | {total_tokens:,} |",
        f"| **Total wall-clock time** | {total_duration:.1f}s |",
        f"| **Avg time per task** | {total_duration/total:.1f}s |" if total else "",
        "",
        "## Per-Task Results",
        "",
        "| Task | Tests Passed | Iterations | Tokens | Duration | Error |",
        "|------|-------------|-----------|-------|----------|-------|",
    ]

    for r in results:
        status = "✅" if r["tests_passed"] else "❌"
        error = r.get("error", "")[:40] if r.get("error") else ""
        lines.append(
            f"| {r['task_id']} | {status} | {r.get('iterations_used', 'N/A')} "
            f"| {r.get('total_tokens', 0):,} | {r.get('duration_seconds', 0):.1f}s "
            f"| {error} |"
        )

    lines.extend(["", "## Detailed Logs", ""])
    for r in results:
        lines.append(f"### {r['task_id']}")
        lines.append(f"- **Thread ID:** `{r['thread_id']}`")
        lines.append(f"- **Tests passed:** {r['tests_passed']}")
        lines.append(f"- **Human approved:** {r['human_approved']}")
        lines.append(f"- **Iterations:** {r.get('iterations_used', 'N/A')}")
        lines.append(f"- **Tokens:** {r.get('total_tokens', 0):,}")
        lines.append(f"- **Duration:** {r.get('duration_seconds', 0):.1f}s")
        if r.get("error"):
            lines.append(f"- **Error:** {r['error']}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run agent pipeline benchmark")
    parser.add_argument("--tasks", type=int, nargs="*", help="Task indices to run")
    parser.add_argument("--quick", action="store_true", help="Run first 3 tasks only")
    parser.add_argument("--report-only", action="store_true", help="Re-generate report from saved results")
    args = parser.parse_args()

    # Resolve tasks
    available = BENCHMARK_TASKS
    if args.quick:
        available = available[:3]
    elif args.tasks is not None:
        available = [available[i] for i in args.tasks]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.report_only:
        if RESULTS_FILE.exists():
            with open(RESULTS_FILE) as f:
                results = json.load(f)
            report = generate_report(results)
            report_path = RESULTS_DIR / f"benchmark_report_{datetime.now().strftime('%Y%m%dT%H%M%SZ')}.md"
            report_path.write_text(report, encoding="utf-8")
            print(report)
            print(f"\nReport saved to {report_path}")
        else:
            print(f"No results file found at {RESULTS_FILE}. Run without --report-only first.")
        return

    # Run benchmark
    print(f"Benchmark: {len(available)} tasks, max {MAX_ITERATIONS} iterations each")
    print(f"Tasks: {[t['id'] for t in available]}")

    results: list[dict[str, Any]] = []
    for i, task_def in enumerate(available):
        print(f"\n--- Task {i+1}/{len(available)}: {task_def['id']} ---")
        result = run_single_task(task_def)
        results.append(result)

        # Save intermediate results in case of crash
        with open(RESULTS_FILE, "w") as f:
            json.dump(results, f, indent=2, default=str)

    # Generate report
    report = generate_report(results)
    report_path = RESULTS_DIR / f"benchmark_report_{datetime.now().strftime('%Y%m%dT%H%M%SZ')}.md"
    report_path.write_text(report, encoding="utf-8")

    print("\n" + "=" * 60)
    print(report)
    print(f"\nFull results saved to {RESULTS_FILE}")
    print(f"Report saved to {report_path}")


if __name__ == "__main__":
    main()
