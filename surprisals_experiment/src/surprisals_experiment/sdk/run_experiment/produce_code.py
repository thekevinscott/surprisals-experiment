"""Generate one T solution and preserve its diagnostics."""

import json
import shutil
from collections.abc import Callable
from pathlib import Path

from surprisals_experiment.config import Config
from ..prompt_t import prompt_t


async def produce_code(config: Config, *, attempt: int, sample: int, advice: str, snapshot: Path,
                on_delta: Callable[[str, str], None] | None = None) -> Path:
    sample_dir = config.t_dir(attempt, sample)
    sample_dir.mkdir(parents=True, exist_ok=True)
    output = sample_dir / "src"
    t_run = await prompt_t(config, advice, output=output, logs=sample_dir, on_delta=on_delta)
    (sample_dir / "run.json").write_text(json.dumps({"exit_code": t_run.exit_code}, indent=2) + "\n")
    if t_run.exit_code == -1:
        raise RuntimeError("T infrastructure failed: botbox could not obtain an exit code")
    shutil.copytree(output, snapshot, symlinks=True)
    return output
