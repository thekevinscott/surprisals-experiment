"""Generate one T solution and preserve its diagnostics."""

import asyncio
import json
from functools import partial
from pathlib import Path

from surprisals_experiment.retry_policy.constants import DELAYS
from surprisals_experiment.retry_policy.retried import retried

from ....prompt_t import prompt_t
from ....run import Run
from ....sample import Sample
from ....utils.write import write


async def produce_code(run: Run, sample: Sample) -> None:
    config = sample.turn.config
    output = sample.t_dir
    advice = sample.turn.advice.text
    on_delta = (
        partial(run.on_t_delta, str(output.relative_to(config.output)))
        if run.on_t_delta
        else None
    )
    attempts = output / "attempts"
    log = output / "timeouts.txt"

    def timeouts() -> int:
        return len(log.read_text().splitlines()) if log.exists() else 0

    def next_attempt() -> Path:
        attempts.mkdir(parents=True, exist_ok=True)
        attempt = attempts / str(len(list(attempts.iterdir())))
        attempt.mkdir()
        return attempt

    def before_sleep(state):
        if on_delta is not None:
            on_delta(
                "retry",
                f"T {state.attempt_number}/{len(DELAYS)} "
                f"in {state.upcoming_sleep:g}s: {state.outcome.exception()}\n",
            )

    @retried(operation="T sample", before_sleep=before_sleep)
    async def generate() -> Path:
        while timeouts() <= config.t_sample_retries:
            attempt = next_attempt()
            source = attempt / "src"
            try:
                async with asyncio.timeout(config.t_sample_timeout):
                    t_run = await prompt_t(
                        config, advice, output=source, logs=attempt, on_delta=on_delta
                    )
                    write(
                        attempt / "generation.json",
                        json.dumps({"exit_code": t_run.exit_code}, indent=2) + "\n",
                    )
                    if t_run.exit_code == -1:
                        raise RuntimeError(
                            "T infrastructure failed: botbox could not obtain an exit code"
                        )
                    return source
            except TimeoutError:
                previous = log.read_text() if log.exists() else ""
                write(
                    log, previous + f"T exceeded {config.t_sample_timeout:g} seconds\n"
                )

    await generate()
