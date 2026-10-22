"""Keep blocking work off the event loop and finish it before cancellation cleanup."""

import asyncio
from collections.abc import Callable
from contextlib import suppress
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


async def run_sync(function: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    task = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # A thread cannot be cancelled. Let it finish before closing its resources.
        with suppress(Exception):
            await task
        raise
