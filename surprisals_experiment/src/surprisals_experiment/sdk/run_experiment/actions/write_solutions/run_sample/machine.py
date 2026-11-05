from pathlib import Path

from state_machine import state_machine

from .....run import Run
from .....sample import Sample

QUERIES = Path(__file__).parent


async def state(run: Run, sample: Sample) -> str:
    for name in ("solution_missing", "untested"):
        row, = await run.database.query(QUERIES / f"{name}.sql", **sample.params)
        if row["missing"]:
            return name
    return "sample_done"


async def run_sample(run: Run, sample: Sample) -> None:
    await state_machine(state, run.actions, run, sample)
