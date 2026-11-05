from ....fork import Fork
from ....run import Run
from ....window import Window
from ...run_fork import fork_state


async def state(run: Run, window: Window) -> str:
    fork = Fork(window.config, window.position, 0)
    return "window_done" if await fork_state(run, fork) == "fork_done" else "fork_pending"
