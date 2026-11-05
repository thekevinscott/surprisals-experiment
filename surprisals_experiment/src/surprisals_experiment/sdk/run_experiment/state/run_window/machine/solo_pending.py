from .....fork import Fork
from .....run import Run
from .....window import Window
from ...run_fork import run_fork
from .read_window import read_window


async def solo_pending(run: Run, window: Window) -> None:
    row = await read_window(run, window)
    await run_fork(run, Fork(window.config, window.position, row["winner"]),
                   window.config.window_turns)
