"""Select the next step for one T sample from its persisted artifacts."""

from functools import partial
from pathlib import Path

from state_machine import Stop, state_machine

from ...turn import Turn
from ...database import ExperimentDatabase, QuestionDatabase

QUERIES = Path(__file__).parent


async def run_sample(turn: Turn, sample: int, database: ExperimentDatabase,
                     problem: QuestionDatabase, actions: dict, *, on_delta=None) -> None:
    async def state() -> str:
        for name in ("solution_missing", "untested"):
            row, = await database.query(QUERIES / f"{name}.sql", **turn.params, sample=sample)
            if row["missing"]:
                return name
        return "done"

    await state_machine(state=state, actions={
        "solution_missing": partial(actions["solution_missing"], turn.config,
                                    output=turn.t_dir(sample), advice=turn.advice.text, on_delta=on_delta),
        "untested": partial(actions["untested"], turn, problem, sample=sample),
        "done": Stop,
    })
