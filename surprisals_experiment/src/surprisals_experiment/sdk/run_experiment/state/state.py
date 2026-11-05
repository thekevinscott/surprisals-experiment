from pathlib import Path

from ...run import Run
from ...window import Window
from .run_window.machine import state as window_state

STATE = Path(__file__).with_name("state.sql")


async def state(run: Run) -> str:
    row, = await run.database.query(STATE)
    if row["not_started"]:
        return "not_started"
    return "run_done" if await window_state(run, Window(run.config)) == "window_done" else "window_pending"
