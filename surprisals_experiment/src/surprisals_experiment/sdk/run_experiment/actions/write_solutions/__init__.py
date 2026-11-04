import traceback
from collections.abc import Callable
from pathlib import Path

from surprisals_experiment.config import Config
from ....utils.write import write
from .prompt_t_to_produce_code import prompt_t_to_produce_code


async def write_solutions(
    config: Config, *, attempt: int, advice: str,
    on_delta: Callable[[str, str], None] | None = None,
    folders: list[Path],
) -> list[Path]:
    try:
        return await prompt_t_to_produce_code(
            config, advice=advice,
            on_delta=on_delta,
            folders=folders,
        )
    except Exception:
        write(config.attempt_dir(attempt) / "error.txt", traceback.format_exc())
        raise
