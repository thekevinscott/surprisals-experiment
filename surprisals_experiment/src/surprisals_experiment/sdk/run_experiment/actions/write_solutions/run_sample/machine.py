from pathlib import Path

from state_machine import state_machine

from .....run import Run
from .....sample import Sample

QUERIES = Path(__file__).parent


async def state(run: Run, sample: Sample) -> str:
    timeouts = sample.turn.config.t_sample_retries + 1
    row, = await run.database.query(QUERIES / "solution_missing.sql", **sample.params, timeouts=timeouts)
    if row["missing"]:
        return "solution_missing"
    row, = await run.database.query(QUERIES / "untested.sql", **sample.params)
    if row["missing"]:
        return "untested"
    return "sample_done"


async def run_sample(run: Run, sample: Sample) -> None:
    await state_machine(state, run.actions, run, sample)
