"""Quick graph compilation check — used by CI to verify the graph builds without API keys."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graph.build_graph import build_graph
from graph.state import new_state

app = build_graph()
print(f"Graph compiled: {len(app.nodes)} nodes")
print(f"Edges: {len(app.edges)}")

state = new_state("CI verification task")
assert state["task"] == "CI verification task"
assert state["max_iterations"] == 3
assert state["approval_status"] == "pending"

print("State factory: OK")
print("All graph checks passed.")
