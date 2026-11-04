import traceback
from collections.abc import Callable
from pathlib import Path

from ....turn import Turn
from ....utils.write import write
from ....database import ExperimentDatabase, QuestionDatabase
from .prompt_t_to_produce_code import prompt_t_to_produce_code


async def write_solutions(turn: Turn, database: ExperimentDatabase, problem: QuestionDatabase, actions: dict, *, on_delta: Callable[[str, str], None] | None = None) -> list[Path]:
    try:
        return await prompt_t_to_produce_code(
            turn, database, problem, actions, on_delta=on_delta,
        )
    except Exception:
        write(turn.attempt_dir / "error.txt", traceback.format_exc())
        raise
