from .....fork import Fork
from .....run import Run
from .....window import Window
from ...run_fork import fork_state
from .read_window import read_window


async def state(run: Run, window: Window) -> str:
    for position in range(window.config.window_forks):
        fork = Fork(window.config, window.position, position)
        if await fork_state(run, fork, window.config.fork_turns) != "fork_done":
            return "fork_pending"
    row = await read_window(run, window)
    fork = Fork(window.config, window.position, row["winner"])
    if await fork_state(run, fork, window.config.fork_turns + window.config.window_solo_turns) != "fork_done":
        return "solo_pending"
    return "window_done"
