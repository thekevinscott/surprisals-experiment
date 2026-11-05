from pathlib import Path

from ......fork import Fork
from ......run import Run

STATE = Path(__file__).with_name("state.sql")


async def read_fork(run: Run, fork: Fork) -> dict:
    row, = await run.database.query(STATE, **fork.params, samples=fork.config.t_samples)
    return row
