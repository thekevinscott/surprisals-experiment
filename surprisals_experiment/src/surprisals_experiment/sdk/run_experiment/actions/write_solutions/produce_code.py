"""Generate one T solution and preserve its diagnostics."""

import asyncio
import json
import shutil
from collections.abc import Callable
from pathlib import Path

from surprisals_experiment.config import Config
from surprisals_experiment.retry_policy import DELAYS, retried
from ....prompt_t import prompt_t
from ....utils.write_text import write_text


async def produce_code(
    config: Config, *, output: Path, advice: str,
    on_delta: Callable[[str, str], None] | None = None,
) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    source = output / "src"
    (output / "timeouts.txt").unlink(missing_ok=True)

    def before_sleep(state):
        shutil.rmtree(source, ignore_errors=True)
        if on_delta is not None:
            on_delta("retry", f"T {state.attempt_number}/{len(DELAYS)} "
                              f"in {state.upcoming_sleep:g}s: {state.outcome.exception()}\n")

    @retried(operation="T sample", before_sleep=before_sleep)
    async def generate() -> Path:
        shutil.rmtree(source, ignore_errors=True)
        for _ in range(config.t_sample_retries + 1):
            try:
                async with asyncio.timeout(config.t_sample_timeout):
                    t_run = await prompt_t(config, advice, output=source, logs=output, on_delta=on_delta)
                    write_text(output / "run.json", json.dumps({"exit_code": t_run.exit_code}, indent=2) + "\n")
                    if t_run.exit_code == -1:
                        raise RuntimeError("T infrastructure failed: botbox could not obtain an exit code")
                    return source
            except TimeoutError:
                with (output / "timeouts.txt").open("a") as log:
                    log.write(f"T exceeded {config.t_sample_timeout:g} seconds\n")
                shutil.rmtree(source)
        source.mkdir()
        return source

    return await generate()
