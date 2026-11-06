from pathlib import Path

from .....run import Run

RESULT = Path(__file__).with_name("result.sql")


async def read_progress(run: Run):
    config = run.config
    result, = await run.database.query(
        RESULT, samples=config.t_samples, timeouts=config.t_sample_retries + 1
    )
    solution = config.output / result["turn_id"] / "ts/0/attempts" / str(result["attempt"]) / "src" if result["turn_id"] else None
    return result, solution


