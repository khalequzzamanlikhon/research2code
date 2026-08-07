"""
CLI driver for the pipeline.

Demonstrates:
  - starting a run
  - the graph pausing at the human-in-the-loop gate (interrupt)
  - resuming with an explicit approve/reject decision
  - checkpointed resumability: run with --resume <thread_id> after killing
    the process mid-run to pick back up from the last checkpoint.

Usage:
    python run_cli.py "Implement a rate limiter and write tests for it"
    python run_cli.py --resume <thread_id>
"""

from __future__ import annotations

import sys
import uuid

from dotenv import load_dotenv
from langgraph.types import Command

from graph.build_graph import build_graph
from graph.state import new_state
from observability.tracing_setup import enable_tracing

load_dotenv()  # picks up a local .env file if present; no-op if it doesn't exist
enable_tracing()


def _print_interrupt(interrupt_payload: dict) -> None:
    print("\n" + "=" * 60)
    print("HUMAN APPROVAL REQUIRED")
    print("=" * 60)
    print(interrupt_payload["question"])
    if interrupt_payload.get("last_test_result"):
        print("\nLast test result:", interrupt_payload["last_test_result"])

    # Multi-file display
    if interrupt_payload.get("files"):
        print(f"\n--- Proposed files (entrypoint: {interrupt_payload.get('entrypoint', '?')}) ---")
        for fname, fcontent in interrupt_payload["files"].items():
            print(f"\n{'─' * 40}")
            print(f"  {fname}")
            print(f"{'─' * 40}")
            print(fcontent)
    else:
        print("\n--- Proposed code ---")
        print(interrupt_payload.get("code", ""))
    print("=" * 60)


def main() -> None:
    app = build_graph()

    if len(sys.argv) >= 3 and sys.argv[1] == "--resume":
        thread_id = sys.argv[2]
        config = {"configurable": {"thread_id": thread_id}}
        # Resuming after a restart: no new input needed, just re-invoke.
        # If we're paused at the interrupt, we'll hit that branch below.
        result = app.invoke(None, config=config)
    else:
        if len(sys.argv) < 2:
            print('Usage: python run_cli.py "<task description>"')
            sys.exit(1)
        task = sys.argv[1]
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        print(f"Starting run. thread_id={thread_id}  (save this to test --resume)")
        result = app.invoke(new_state(task), config=config)

    # Check whether we're paused at an interrupt.
    state = app.get_state(config)
    if state.next and "human_approval" in state.next:
        interrupt_payload = state.tasks[0].interrupts[0].value
        _print_interrupt(interrupt_payload)
        answer = input("\nApprove? [y/N]: ").strip().lower()
        feedback = input("Optional feedback (enter to skip): ").strip() or None
        decision = {"approved": answer == "y", "feedback": feedback}
        result = app.invoke(Command(resume=decision), config=config)

    if result and result.get("final_report"):
        print("\n" + result["final_report"])


if __name__ == "__main__":
    main()
