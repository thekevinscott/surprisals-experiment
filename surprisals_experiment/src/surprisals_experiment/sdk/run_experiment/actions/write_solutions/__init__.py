import asyncio
import traceback
from collections.abc import Callable
from pathlib import Path

from ....turn import Turn
from ....utils.write import write
from .produce_code import produce_code


async def write_solutions(turn: Turn, *, on_delta: Callable[[str, str], None] | None = None) -> list[Path]:
    pool = asyncio.Semaphore(turn.config.t_pool_size)

    async def generate(sample: int) -> Path:
        async with pool:
            return await produce_code(turn.config, output=turn.t_dir(sample), advice=turn.advice.text, on_delta=on_delta)

    tasks = [asyncio.create_task(generate(sample)) for sample in range(turn.config.t_samples)]
    try:
        return await asyncio.gather(*tasks)
    except Exception:
        write(turn.attempt_dir / "error.txt", traceback.format_exc())
        raise
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
