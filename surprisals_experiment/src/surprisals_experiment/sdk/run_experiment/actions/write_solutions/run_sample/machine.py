from collections.abc import Callable
from functools import partial
from pathlib import Path

from state_machine import Stop, state_machine

from .....turn import Turn
from .....database import ExperimentDatabase, QuestionDatabase
from ..produce_code import produce_code
from ...run_tests import run_tests

QUERIES = Path(__file__).parent


async def run_sample(turn: Turn, sample: int, database: ExperimentDatabase,
                     problem: QuestionDatabase, *,
                     on_delta: Callable[[str, str], None] | None = None) -> None:
    async def state() -> str:
        for name in ("solution_missing", "untested"):
            row, = await database.query(QUERIES / f"{name}.sql", **turn.params, sample=sample)
            if row["missing"]:
                return name
        return "done"

    await state_machine(state=state, actions={
        "solution_missing": partial(produce_code, turn.config, output=turn.t_dir(sample),
                                    advice=turn.advice.text, on_delta=on_delta),
        "untested": partial(run_tests, turn, problem, sample=sample),
        "done": Stop,
    })
