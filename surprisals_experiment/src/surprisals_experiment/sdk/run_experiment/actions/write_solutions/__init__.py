import traceback
from collections.abc import Callable
from pathlib import Path

from ....turn import Turn
from ....database import ExperimentDatabase
from ....utils.write import write
from .prompt_t_to_produce_code import prompt_t_to_produce_code

PENDING = Path(__file__).with_name("pending_samples.sql")


async def write_solutions(turn: Turn, database: ExperimentDatabase, *, on_delta: Callable[[str, str], None] | None = None) -> list[Path]:
    samples = await database.query(PENDING, **turn.params, samples=turn.config.t_samples)
    try:
        return await prompt_t_to_produce_code(
            turn.config, advice=turn.advice.text, on_delta=on_delta,
            folders=[turn.t_dir(sample["position"]) for sample in samples],
        )
    except Exception:
        write(turn.attempt_dir / "error.txt", traceback.format_exc())
        raise
