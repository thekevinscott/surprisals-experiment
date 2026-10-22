"""Generate one T solution and preserve its diagnostics."""

import asyncio
import json
import shutil
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from surprisals_experiment.config import Config
from ..utils.transcripts import save_transcripts
from ..prompt_t import prompt_t


async def produce_code(
    config: Config, *, pool: asyncio.Semaphore, attempt: int, sample: int, advice: str, snapshot: Path,
    on_delta: Callable[[str, str], None] | None = None,
) -> Path:
    async with pool:
        sample_dir = config.t_dir(attempt, sample)
        sample_dir.mkdir(parents=True, exist_ok=True)
        output = sample_dir / "src"
        t_run = await prompt_t(config, advice, output=output, on_delta=on_delta)
        diagnostics = asdict(t_run)
        save_transcripts(diagnostics.pop("transcript"), sample_dir / "t_transcripts")
        (sample_dir / "run.json").write_text(json.dumps(diagnostics, indent=2) + "\n")
        if t_run.exit_code == -1:
            raise RuntimeError("T infrastructure failed: botbox could not obtain an exit code")
        shutil.copytree(output, snapshot, symlinks=True)
        return output
