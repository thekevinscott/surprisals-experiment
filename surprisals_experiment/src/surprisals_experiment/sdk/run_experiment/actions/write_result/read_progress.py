from pathlib import Path

from ....run import Run

RESULT = Path(__file__).with_name("result.sql")


async def read_progress(run: Run):
    config = run.config
    result, = await run.database.query(RESULT, samples=config.t_samples)
    solution = config.output / result["turn_id"] / "ts/0/src" if result["turn_id"] else None
    return result, solution


