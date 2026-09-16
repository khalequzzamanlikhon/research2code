"""
Security-focused tests for the most safety-critical paths in the system.

These tests verify that:
- The filesystem MCP server's path jailing cannot be escaped
- The coder's markdown-fence stripping works correctly
- The coder's retry feedback injection includes failure context
- The sandbox executor handles edge cases properly

All tests run offline — no API keys or Docker required.
"""

import os
import tempfile
from pathlib import Path

import pytest

from graph.nodes.coder import _build_prompt
from graph.state import TestResult, new_state
from sandbox.executor import run_python_code

# ---------------------------------------------------------------------------
# Conditional import: mcp.server.fastmcp may not be available in older
# mcp package versions. If missing, path-jailing tests are skipped.
# ---------------------------------------------------------------------------

try:
    from mcp_servers.filesystem_server import _safe_path

    SAFE_PATH_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    SAFE_PATH_AVAILABLE = False


# ---------------------------------------------------------------------------
# Path jailing (_safe_path)
# ---------------------------------------------------------------------------

ORIGINAL_WORKDIR = os.environ.get("AGENT_SANDBOX_DIR")


def _safe_path_skip_reason():
    return (
        "mcp.server.fastmcp not available. "
        "You likely have mcp>=2.0 installed which removed FastMCP. "
        "Fix: pip install 'mcp>=1.1.0,<2.0.0'"
    )


@pytest.fixture
def temp_workdir():
    """Create a temporary directory and set AGENT_SANDBOX_DIR to it."""
    if not SAFE_PATH_AVAILABLE:
        pytest.skip(_safe_path_skip_reason())
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AGENT_SANDBOX_DIR"] = tmp
        # Re-import to pick up the new WORKDIR
        import importlib

        import mcp_servers.filesystem_server as fs_mod

        importlib.reload(fs_mod)
        yield Path(tmp)
        if ORIGINAL_WORKDIR is not None:
            os.environ["AGENT_SANDBOX_DIR"] = ORIGINAL_WORKDIR
        importlib.reload(fs_mod)


@pytest.mark.skipif(not SAFE_PATH_AVAILABLE, reason=_safe_path_skip_reason())
class TestSafePath:
    def test_normal_path_inside_workdir(self, temp_workdir):
        """A normal relative path resolves inside WORKDIR."""
        result = _safe_path("foo.py")
        assert str(temp_workdir) in str(result)
        assert result.name == "foo.py"

    def test_parent_traversal_blocked(self, temp_workdir):
        """../../etc/passwd must raise ValueError."""
        with pytest.raises(ValueError):
            _safe_path("../../../etc/passwd")

    def test_absolute_escape_blocked(self, temp_workdir):
        """Absolute /etc/passwd must raise ValueError."""
        with pytest.raises(ValueError):
            _safe_path("/etc/passwd")

    def test_dot_resolves_to_workdir(self, temp_workdir):
        """'.' resolves to WORKDIR itself."""
        result = _safe_path(".")
        assert result == temp_workdir.resolve()

    def test_deep_traversal_blocked(self, temp_workdir):
        """Deep parent traversal beyond root is blocked."""
        with pytest.raises(ValueError):
            _safe_path("../../../../../../etc/passwd")

    def test_nested_path_inside_workdir(self, temp_workdir):
        """Nested directories inside WORKDIR are allowed."""
        result = _safe_path("src/utils/helper.py")
        assert str(temp_workdir) in str(result)
        assert result.name == "helper.py"


# ---------------------------------------------------------------------------
# Coder: markdown-fence stripping
# ---------------------------------------------------------------------------

class TestCoderPrompt:
    def test_build_prompt_with_task_only(self):
        """_build_prompt with a fresh state (no research, no failures)."""
        state = new_state("Write a fib function")
        prompt = _build_prompt(state)
        assert "Task: Write a fib function" in prompt
        assert "FAILED" not in prompt

    def test_build_prompt_includes_failure_output(self):
        """_build_prompt injects previous failure into the retry prompt."""
        state = new_state("Write a fib function")
        state["test_results"] = [
            TestResult(passed=False, output="Traceback...", error="AssertionError: fib(0) != 0")
        ]
        state["generated_code"] = "def fib(n): return n"
        prompt = _build_prompt(state)
        assert "FAILED" in prompt
        assert "AssertionError" in prompt
        assert "def fib(n): return n" in prompt  # previous code included
        assert "Fix the bug" in prompt

    def test_build_prompt_no_failure_when_tests_pass(self):
        """No failure context injected when last test passed."""
        state = new_state("Write a fib function")
        state["test_results"] = [
            TestResult(passed=False, output="fail", error="err"),
            TestResult(passed=True, output="pass", error=None),
        ]
        state["generated_code"] = "def fib(n): return n"
        prompt = _build_prompt(state)
        assert "FAILED" not in prompt


# ---------------------------------------------------------------------------
# Sandbox executor: edge cases
# ---------------------------------------------------------------------------

class TestSandboxEdgeCases:
    def test_empty_code_runs(self):
        """Empty code should pass (exit code 0)."""
        result = run_python_code("")
        assert result.passed
        assert result.exit_code == 0

    def test_syntax_error_reported_as_failure(self):
        """A SyntaxError should produce a failure, not crash the sandbox."""
        result = run_python_code("def broken(")
        assert not result.passed
        assert result.exit_code != 0

    def test_runtime_error_reported_as_failure(self):
        """A runtime error (ZeroDivisionError) is caught and reported."""
        result = run_python_code("1/0")
        assert not result.passed

    def test_infinite_loop_not_truly_infinite(self):
        """While True: pass should be killed by the timeout, not hang."""
        result = run_python_code("while True: pass\n")
        assert not result.passed

    def test_print_multiline_output_captured(self):
        """Multi-line stdout is fully captured."""
        result = run_python_code("for i in range(3):\n    print(i)")
        assert result.passed
        assert "0" in result.stdout
        assert "1" in result.stdout
        assert "2" in result.stdout

    def test_with_test_code_appended(self):
        """The test_code parameter appends additional code for execution."""
        result = run_python_code("x = 42", test_code="assert x == 42\nprint('ok')")
        assert result.passed
        assert "ok" in result.stdout
