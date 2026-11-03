"""Prompt a pool of fresh Ts and return their source directories in sample order."""

import asyncio
import shutil
from collections.abc import Callable
from pathlib import Path

from surprisals_experiment.config import Config
from .produce_code import produce_code


async def prompt_t_to_produce_code(
    config: Config, *, attempt: int, advice: str, snapshot: Path,
    on_delta: Callable[[str, str], None] | None = None,
    folders: list[Path] | None = None,
) -> list[Path]:
    snapshot.mkdir(parents=True, exist_ok=True)
    (snapshot / "advice.txt").write_text(advice)
    pool = asyncio.Semaphore(config.t_pool_size)

    async def generate(folder: Path) -> Path:
        async with pool:
            source = await produce_code(config, output=folder, advice=advice, on_delta=on_delta)
            destination = snapshot / folder.name
            shutil.rmtree(destination, ignore_errors=True)
            shutil.copytree(source, destination, symlinks=True)
            return source

    if folders is None:
        folders = [config.t_dir(attempt, sample) for sample in range(config.t_samples)]
    tasks = [asyncio.create_task(generate(folder)) for folder in folders]
    try:
        return await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
