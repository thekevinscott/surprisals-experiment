"""Generate one T solution and preserve its diagnostics."""

import asyncio
import json
import shutil
from pathlib import Path

from surprisals_experiment.retry_policy import DELAYS, retried
from ....run import Run
from ....sample import Sample
from ....prompt_t import prompt_t
from ....utils.write import write


async def produce_code(run: Run, sample: Sample) -> None:
    config = sample.turn.config
    output = sample.t_dir
    advice = sample.turn.advice.text
    on_delta = run.on_t_delta
    output.mkdir(parents=True, exist_ok=True)
    source = output / "src"

    def before_sleep(state):
        shutil.rmtree(source, ignore_errors=True)
        if on_delta is not None:
            on_delta("retry", f"T {state.attempt_number}/{len(DELAYS)} "
                              f"in {state.upcoming_sleep:g}s: {state.outcome.exception()}\n")

    @retried(operation="T sample", before_sleep=before_sleep)
    async def generate() -> Path:
        for _ in range(config.t_sample_retries + 1):
            try:
                async with asyncio.timeout(config.t_sample_timeout):
                    t_run = await prompt_t(config, advice, output=source, logs=output, on_delta=on_delta)
                    write(output / "generation.json", json.dumps({"exit_code": t_run.exit_code}, indent=2) + "\n")
                    if t_run.exit_code == -1:
                        raise RuntimeError("T infrastructure failed: botbox could not obtain an exit code")
                    return source
            except TimeoutError:
                log = output / "timeouts.txt"
                previous = log.read_text() if log.exists() else ""
                write(log, previous + f"T exceeded {config.t_sample_timeout:g} seconds\n")
                shutil.rmtree(source)
        source.mkdir()
        write(output / "generation.json", json.dumps({"timed_out": True}) + "\n")
        return source

    await generate()
