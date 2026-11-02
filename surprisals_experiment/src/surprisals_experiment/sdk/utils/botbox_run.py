"""Run a command in Botbox, following stdout.txt live."""

import asyncio
import json
from collections.abc import Callable
from pathlib import Path

from botbox import Botbox, RunResult


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


async def botbox_run(agent, command, *, dockerfile, mounts, workdir, output: Path,
                     on_event: Callable[[dict], None]) -> RunResult:
    async with Botbox(agent, dockerfile=dockerfile) as box:
        await box.build()
        done = asyncio.Event()
        follower = asyncio.create_task(follow(output / "stdout.txt", done, on_event))
        try:
            return await box.run(command, mounts=mounts, workdir=workdir, output=output)
        finally:
            done.set()
            await follower
