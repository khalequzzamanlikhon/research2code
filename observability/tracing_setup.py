"""
LangSmith tracing setup.

Import and call `enable_tracing()` once at process start (e.g. top of
run_cli.py or frontend/app.py) to get full node-by-node traces, including
where a human approved/rejected a step, in your LangSmith project.

Needs these environment variables set (e.g. in a .env file):
    LANGCHAIN_TRACING_V2=true
    LANGCHAIN_API_KEY=<your key>
    LANGCHAIN_PROJECT=research-code-review-agent
"""

from __future__ import annotations

import os


def enable_tracing(project_name: str = "research-code-review-agent") -> None:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", project_name)
    if not os.environ.get("LANGCHAIN_API_KEY"):
        print(
            "[tracing_setup] WARNING: LANGCHAIN_API_KEY not set — "
            "traces will not be uploaded to LangSmith."
        )
