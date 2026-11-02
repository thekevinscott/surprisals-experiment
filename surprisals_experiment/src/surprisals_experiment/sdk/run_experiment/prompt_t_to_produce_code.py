"""Prompt a pool of fresh Ts and return their source directories in sample order."""

import asyncio
import shutil
from collections.abc import Callable
from pathlib import Path

from surprisals_experiment.config import Config
from surprisals_experiment.retry_policy import DELAYS, retried
from .produce_code import produce_code


async def prompt_t_to_produce_code(
    config: Config, *, attempt: int, advice: str, snapshot: Path,
    on_delta: Callable[[str, str], None] | None = None,
) -> list[Path]:
    snapshot.mkdir(parents=True)
    (snapshot / "advice.txt").write_text(advice)
    pool = asyncio.Semaphore(config.t_pool_size)

    def before_sleep(state):
        sample = state.args[0]
        shutil.rmtree(config.t_dir(attempt, sample) / "src", ignore_errors=True)
        if on_delta is not None:
            on_delta("retry", f"T sample {sample} {state.attempt_number}/{len(DELAYS)} "
                              f"in {state.upcoming_sleep:g}s: {state.outcome.exception()}\n")

    @retried(operation="T sample", before_sleep=before_sleep)
    async def generate_once(sample: int) -> Path:
        output = config.t_dir(attempt, sample) / "src"
        for _ in range(config.t_sample_retries + 1):
            try:
                async with asyncio.timeout(config.t_sample_timeout):
                    return await produce_code(
                        config, attempt=attempt, sample=sample, advice=advice,
                        snapshot=snapshot / str(sample), on_delta=on_delta,
                    )
            except TimeoutError:
                with (config.t_dir(attempt, sample) / "timeouts.txt").open("a") as log:
                    log.write(f"T sample {sample} exceeded {config.t_sample_timeout:g} seconds\n")
                shutil.rmtree(output)
        output.mkdir()
        (snapshot / str(sample)).mkdir()
        return output

    async def generate(sample: int) -> Path:
        async with pool:
            return await generate_once(sample)

    tasks = [asyncio.create_task(generate(sample)) for sample in range(config.t_samples)]
    try:
        return await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
