"""
Unit tests for the routing logic and sandbox executor -- the parts of the
system that don't require live API keys, so they run in CI as-is.
"""

from graph.state import TestResult, new_state
from graph.supervisor import route_after_review
from sandbox.executor import run_python_code


def test_route_after_review_pass_goes_to_approval():
    state = new_state("dummy task")
    state["test_results"] = [TestResult(passed=True, output="ok", error=None)]
    assert route_after_review(state) == "human_approval"


def test_route_after_review_fail_under_max_loops_back():
    state = new_state("dummy task", max_iterations=3)
    state["iteration_count"] = 1
    state["test_results"] = [TestResult(passed=False, output="", error="boom")]
    assert route_after_review(state) == "coder"


def test_route_after_review_fail_at_max_goes_to_approval():
    state = new_state("dummy task", max_iterations=2)
    state["iteration_count"] = 2
    state["test_results"] = [TestResult(passed=False, output="", error="boom")]
    assert route_after_review(state) == "human_approval"


def test_sandbox_runs_passing_code():
    result = run_python_code("assert 1 + 1 == 2\nprint('ok')")
    assert result.passed
    assert "ok" in result.stdout


def test_sandbox_reports_failure():
    result = run_python_code("assert 1 == 2, 'nope'")
    assert not result.passed
    assert result.exit_code != 0
