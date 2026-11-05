import asyncio
import json
from collections.abc import Callable
from pathlib import Path


async def follow(path: Path, done: asyncio.Event, on_event: Callable[[dict], None]) -> None:
    while not path.exists():
        if done.is_set():
            return
        await asyncio.sleep(.05)
    pending = ""
    with path.open() as stream:
        while True:
            finished = done.is_set()
            *lines, pending = (pending + stream.read()).split("\n")
            for line in lines:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if isinstance(event, dict):
                    on_event(event)
            if finished:
                return
            await asyncio.sleep(.05)
