"""Safe async runner for sync/async hybrid contexts.

LangGraph nodes that need to call async MCP clients must NOT use
asyncio.run() directly because that breaks if the graph is ever driven by
ainvoke/astream (which runs inside an existing event loop).

This module provides `run_async()` that works correctly in both sync and
async contexts — it detects whether an event loop is already running and
handles it accordingly.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Coroutine, TypeVar

T = TypeVar("T")


def run_async(coro: Coroutine[None, None, T]) -> T:
    """Safely run a coroutine to completion in any context.

    - If NO event loop is running (sync context): uses asyncio.run().
    - If an event loop IS running (async context): runs the coroutine in a
      background thread to avoid nested-loop errors.

    This is the ONLY place async bridge logic should live — every node
    that needs to call an async MCP client should use this instead of
    asyncio.run().
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No loop running — safe to use asyncio.run()
        return asyncio.run(coro)

    # Already inside an event loop. Run in a thread to avoid nesting.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()
