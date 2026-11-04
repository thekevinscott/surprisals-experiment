"""Prompt a pool of fresh Ts and return their source directories in sample order."""

import asyncio
from collections.abc import Callable
from pathlib import Path

from surprisals_experiment.config import Config
from ....advice import Advice
from .produce_code import produce_code


async def prompt_t_to_produce_code(
    config: Config, *, advice: Advice,
    on_delta: Callable[[str, str], None] | None = None,
    folders: list[Path],
) -> list[Path]:
    pool = asyncio.Semaphore(config.t_pool_size)

    async def generate(folder: Path) -> Path:
        async with pool:
            return await produce_code(config, output=folder, advice=advice, on_delta=on_delta)

    tasks = [asyncio.create_task(generate(folder)) for folder in folders]
    try:
        return await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
