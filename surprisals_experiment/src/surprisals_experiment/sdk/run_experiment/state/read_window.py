from pathlib import Path

from ...run import Run

STATE = Path(__file__).with_name("state.sql")


async def read_window(run: Run) -> dict:
    row, = await run.database.query(STATE, samples=run.config.t_samples)
    return row
