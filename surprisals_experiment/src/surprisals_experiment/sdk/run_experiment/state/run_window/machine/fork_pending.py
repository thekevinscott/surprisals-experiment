import asyncio

from .....fork import Fork
from .....run import Run
from .....window import Window
from ...run_fork import run_fork


async def fork_pending(run: Run, window: Window) -> None:
    tasks = [asyncio.create_task(run_fork(
        run, Fork(window.config, window.position, position), window.config.fork_turns,
    )) for position in range(window.config.window_forks)]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
