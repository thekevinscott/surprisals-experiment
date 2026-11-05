from ....fork import Fork
from ....run import Run
from ....window import Window
from ...run_fork import run_fork


async def fork_pending(run: Run, window: Window) -> None:
    await run_fork(run, Fork(window.config, window.position, 0))
