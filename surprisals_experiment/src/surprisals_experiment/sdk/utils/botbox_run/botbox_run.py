"""Run a command in Botbox, following stdout.txt live."""

import asyncio
from collections.abc import Callable
from pathlib import Path

from botbox import Botbox, RunResult

from .follow import follow


async def botbox_run(agent, command, *, dockerfile, mounts, workdir, output: Path,
                     on_event: Callable[[dict], None]) -> RunResult:
    async with Botbox(agent, dockerfile=dockerfile) as box:
        await box.build()
        # Eager, so a run that never yields still cancels follow inside its try, not before it starts.
        follower = asyncio.create_task(follow(output / "stdout.txt", on_event), eager_start=True)
        try:
            return await box.run(command, mounts=mounts, workdir=workdir, output=output)
        finally:
            follower.cancel()
            try:
                await follower
            except asyncio.CancelledError:
                if asyncio.current_task().cancelling():
                    raise
