"""Prompt a pool of fresh Ts and return their source directories in sample order."""

import asyncio
from collections.abc import Callable
from pathlib import Path

from surprisals_experiment.config import Config
from .produce_code import produce_code


async def prompt_t_to_produce_code(
    config: Config, *, attempt: int, advice: str, snapshot: Path,
    on_delta: Callable[[str, str], None] | None = None,
) -> list[Path]:
    snapshot.mkdir(parents=True)
    (snapshot / "advice.txt").write_text(advice)
    pool = asyncio.Semaphore(config.t_pool_size)
    async def generate(sample: int) -> Path:
        async with pool:
            return await produce_code(
                config, attempt=attempt, sample=sample, advice=advice,
                snapshot=snapshot / str(sample), on_delta=on_delta,
            )

    tasks = [asyncio.create_task(generate(sample)) for sample in range(config.t_samples)]
    try:
        return await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
