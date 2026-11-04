"""Generate one T solution; publish completion only after a successful call."""

import asyncio
import json
import shutil
from collections.abc import Callable
from pathlib import Path

from surprisals_experiment.config import Config
from ....prompt_t import prompt_t
from ....utils.write import write


async def produce_code(
    config: Config, *, output: Path, advice: str,
    on_delta: Callable[[str, str], None] | None = None,
) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    source = output / "src"
    shutil.rmtree(source, ignore_errors=True)
    async with asyncio.timeout(config.t_sample_timeout):
        t_run = await prompt_t(config, advice, output=source, logs=output, on_delta=on_delta)
    if t_run.exit_code == -1:
        raise RuntimeError("T infrastructure failed: botbox could not obtain an exit code")
    write(output / "run.json", json.dumps({"exit_code": t_run.exit_code}, indent=2) + "\n")
    return source
