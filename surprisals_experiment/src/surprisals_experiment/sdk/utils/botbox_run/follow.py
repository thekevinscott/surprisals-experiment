import asyncio
import json
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path

from posix_tools import tail


async def follow(path: Path, done: asyncio.Event, on_event: Callable[[dict], None]) -> None:
    consumed = 0

    def emit(line: bytes) -> None:
        try:
            event = json.loads(line)
        except ValueError:
            return
        if isinstance(event, dict):
            on_event(event)

    async def stream(lines) -> None:
        nonlocal consumed
        async for line in lines:
            consumed += 1
            emit(line)

    async with tail(path, n=None, follow=True) as lines:
        reader = asyncio.create_task(stream(lines))
        await done.wait()
        reader.cancel()
        with suppress(asyncio.CancelledError):
            await reader
    # Lines written just before done can still be in tail's pipe when it is killed.
    if path.exists():
        for line in path.read_bytes().split(b"\n")[consumed:]:
            emit(line)
