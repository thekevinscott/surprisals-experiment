import asyncio
import traceback

from ....turn import Turn
from ....utils.write import write
from .run_sample import run_sample
from ....run import Run
from ....sample import Sample


async def write_solutions(run: Run, turn: Turn) -> None:
    pool = asyncio.Semaphore(turn.config.t_pool_size)

    async def generate(position: int) -> None:
        async with pool:
            await run_sample(run, Sample(turn, position))

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
