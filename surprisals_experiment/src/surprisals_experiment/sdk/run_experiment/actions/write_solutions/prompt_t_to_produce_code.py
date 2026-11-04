"""Run each T sample through generation and testing, preserving sample order."""

import asyncio
from collections.abc import Callable
from pathlib import Path

from ....turn import Turn
from ....database import ExperimentDatabase, QuestionDatabase
from ...run_sample import run_sample


async def prompt_t_to_produce_code(
    turn: Turn, database: ExperimentDatabase, problem: QuestionDatabase, actions: dict, *,
    on_delta: Callable[[str, str], None] | None = None,
) -> list[Path]:
    pool = asyncio.Semaphore(turn.config.t_pool_size)

    async def sample(position: int) -> Path:
        async with pool:
            await run_sample(turn, position, database, problem, actions, on_delta=on_delta)
            return turn.t_dir(position) / "src"

    tasks = [asyncio.create_task(sample(position)) for position in range(turn.config.t_samples)]
    try:
        return await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
