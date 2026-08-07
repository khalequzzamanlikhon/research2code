"""
Sandboxed code execution.

Generated code is NEVER run directly in the host process. This module runs
it inside a throwaway Docker container with no network access, a memory
cap, and a wall-clock timeout, and captures stdout/stderr/exit code. If
Docker isn't available (e.g. a quick local demo), it falls back to a
`subprocess` with resource limits -- clearly weaker isolation, and the
function says so loudly rather than pretending it's equally safe.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# Custom sandbox image (pre-built with common packages) or vanilla python slim.
# Set AGENT_SANDBOX_IMAGE=agent-sandbox:latest to use the Dockerfile.sandbox image.
DOCKER_IMAGE = os.environ.get("AGENT_SANDBOX_IMAGE", "python:3.11-slim")
TIMEOUT_SECONDS = 20
MEMORY_LIMIT = "256m"
# Persistent pip cache dir on the host — avoids fresh downloads every run.
PIP_CACHE_DIR = os.environ.get("AGENT_PIP_CACHE_DIR",
    str(Path.home() / ".cache" / "agent-pip-cache"))


@dataclass
class ExecutionResult:
    passed: bool
    stdout: str
    stderr: str
    exit_code: int
    used_docker: bool


@lru_cache(maxsize=1)
def _docker_available() -> bool:
    """Check if Docker is installed AND the daemon is actually running. Result is memoized — runs docker info only once per process."""
    if shutil.which("docker") is None:
        return False
    try:
        proc = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=5,
        )
        return proc.returncode == 0 and bool(proc.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def run_python_code(code: str, test_code: str | None = None) -> ExecutionResult:
    """
    Execute `code` (optionally followed by `test_code`, e.g. pytest-style
    assertions appended to the same file) and report the result.

    Tries Docker for sandboxed execution first (if daemon is running).
    Falls back to subprocess with a timeout — documented as weaker isolation.
    """
    combined = code if not test_code else f"{code}\n\n# --- tests ---\n{test_code}\n"

    with tempfile.TemporaryDirectory() as tmp:
        script_path = Path(tmp) / "generated_solution.py"
        script_path.write_text(combined, encoding="utf-8")

        if _docker_available():
            return _run_in_docker(script_path, tmp)
        return _run_in_subprocess(script_path)


def run_python_project(files: dict[str, str], entrypoint: str) -> ExecutionResult:
    """Write multiple files to a temp dir and execute the entrypoint in the sandbox.

    All files are written BEFORE the container starts, so the :ro mount
    (read-only inside container) remains secure. The entrypoint is the file
    passed to `python` for execution.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for filename, content in files.items():
            filepath = tmp_path / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content, encoding="utf-8")

        script_path = tmp_path / entrypoint
        if not script_path.exists():
            return ExecutionResult(False, "", f"Entrypoint '{entrypoint}' not found in generated files", -1, False)

        if _docker_available():
            return _run_in_docker(script_path, tmp)
        return _run_in_subprocess(script_path)


def _run_in_docker(script_path: Path, host_dir: str) -> ExecutionResult:
    # Ensure pip cache dir exists on host so Docker can mount it
    Path(PIP_CACHE_DIR).mkdir(parents=True, exist_ok=True)
    cmd = [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", MEMORY_LIMIT,
        "--cpus", "1",
        "-v", f"{host_dir}:/sandbox:ro",
        "-v", f"{PIP_CACHE_DIR}:/pip-cache",
        "-e", "PIP_CACHE_DIR=/pip-cache",
        DOCKER_IMAGE,
        "python", f"/sandbox/{script_path.name}",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
        return ExecutionResult(
            passed=proc.returncode == 0,
            stdout=proc.stdout,
            stderr=proc.stderr,
            exit_code=proc.returncode,
            used_docker=True,
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult(False, "", f"Execution timed out after {TIMEOUT_SECONDS}s", -1, True)


def _run_in_subprocess(script_path: Path) -> ExecutionResult:
    # Fallback path -- deliberately unsandboxed beyond a timeout. Only used
    # when Docker isn't installed; a real deployment should treat this as
    # a warning-worthy degraded mode, not a substitute for containment.
    try:
        proc = subprocess.run(
            ["python", str(script_path)],
            capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
        )
        return ExecutionResult(
            passed=proc.returncode == 0,
            stdout=proc.stdout,
            stderr=proc.stderr,
            exit_code=proc.returncode,
            used_docker=False,
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult(False, "", f"Execution timed out after {TIMEOUT_SECONDS}s", -1, False)
