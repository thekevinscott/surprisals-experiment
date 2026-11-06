import json
from collections.abc import Callable
from pathlib import Path

from posix_tools import tail


async def follow(path: Path, on_event: Callable[[dict], None]) -> None:
    """Emit stdout.txt's events until cancelled, then the lines tail had not delivered yet."""
    consumed = 0

    def emit(line: bytes) -> None:
        try:
            event = json.loads(line)
        except ValueError:
            return
        if isinstance(event, dict):
            on_event(event)

    try:
        async with tail(path, n=None, follow=True) as lines:
            async for line in lines:
                consumed += 1
                emit(line)
    finally:
        if path.exists():
            for line in (await tail(path, n=None))[consumed:]:
                emit(line)
