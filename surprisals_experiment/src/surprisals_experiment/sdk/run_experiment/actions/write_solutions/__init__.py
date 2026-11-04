import asyncio
import traceback
from collections.abc import Callable

from ....turn import Turn
from ....utils.write import write
from .run_sample import run_sample
from ....database import ExperimentDatabase, QuestionDatabase


async def write_solutions(turn: Turn, database: ExperimentDatabase, problem: QuestionDatabase, *, on_delta: Callable[[str, str], None] | None = None) -> None:
    pool = asyncio.Semaphore(turn.config.t_pool_size)

    async def generate(sample: int) -> None:
        async with pool:
            await run_sample(turn, sample, database, problem, on_delta=on_delta)

    tasks = [asyncio.create_task(generate(sample)) for sample in range(turn.config.t_samples)]
    try:
        await asyncio.gather(*tasks)
    except Exception:
        write(turn.attempt_dir / "error.txt", traceback.format_exc())
        raise
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
