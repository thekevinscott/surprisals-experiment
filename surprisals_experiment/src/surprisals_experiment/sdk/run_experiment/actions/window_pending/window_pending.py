from ....run import Run
from ....window import Window
from ...state.run_window import run_window


async def window_pending(run: Run) -> None:
    await run_window(run, Window(run.config))
