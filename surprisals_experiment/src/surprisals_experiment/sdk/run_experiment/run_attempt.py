"""Run an attempt and preserve its error if evaluation fails."""

import asyncio
import traceback
from collections.abc import Callable
from pathlib import Path

from surprisals_experiment.config import Config
from ..run_test_suite import TestSuiteResult
from .evaluate_attempt import evaluate_attempt


async def run_attempt(config: Config, *, attempt: int, advice: str, test_suite: dict, snapshot: Path,
                on_delta: Callable[[str, str], None] | None = None) -> tuple[Path, list[TestSuiteResult]]:
    attempt_dir = config.attempt_dir(attempt)
    attempt_dir.mkdir(parents=True, exist_ok=True)
    try:
        pool = asyncio.Semaphore(config.t_pool_size)
        async def evaluate(sample: int) -> TestSuiteResult:
            async with pool:
                return await evaluate_attempt(
                    config, attempt=attempt, sample=sample, advice=advice,
                    test_suite=test_suite, snapshot=snapshot / str(sample), on_delta=on_delta,
                )

        tasks = [asyncio.create_task(evaluate(sample)) for sample in range(config.t_samples)]
        try:
            results = await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        return config.t_dir(attempt, 0) / "src", results
    except Exception:
        (attempt_dir / "error.txt").write_text(traceback.format_exc())
        raise
