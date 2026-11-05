from ...run import Run
from ...window import Window
from .run_window.machine import state as window_state
from .read_window import read_window


async def state(run: Run) -> str:
    row = await read_window(run)
    if row["position"] is None:
        return "not_started"
    if await window_state(run, Window(run.config, row["position"])) != "window_done":
        return "window_pending"
    return "run_done" if row["stop"] else "window_pending"
