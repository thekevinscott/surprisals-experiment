from pathlib import Path

from ......run import Run
from ......window import Window

STATE = Path(__file__).with_name("state.sql")


async def read_window(run: Run, window: Window) -> dict:
    row, = await run.database.query(STATE, **window.params, samples=window.config.t_samples)
    return row
