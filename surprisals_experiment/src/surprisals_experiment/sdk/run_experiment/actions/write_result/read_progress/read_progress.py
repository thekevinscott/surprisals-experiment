from pathlib import Path

from .....run import Run

RESULT = Path(__file__).with_name("result.sql")


async def read_progress(run: Run):
    config = run.config
    result, = await run.database.query(RESULT, samples=config.t_samples)
    solution = config.output / result["t_id"] / "src" if result["t_id"] else None
    return result, solution


