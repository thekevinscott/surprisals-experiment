import traceback
from collections.abc import Callable
from pathlib import Path

from ....turn import Turn
from ....utils.write import write
from .prompt_t_to_produce_code import prompt_t_to_produce_code


async def write_solutions(turn: Turn, *, on_delta: Callable[[str, str], None] | None = None) -> list[Path]:
    try:
        return await prompt_t_to_produce_code(
            turn.config, advice=turn.advice.text, on_delta=on_delta,
            folders=[turn.t_dir(sample) for sample in range(turn.config.t_samples)],
        )
    except Exception:
        write(turn.attempt_dir / "error.txt", traceback.format_exc())
        raise
