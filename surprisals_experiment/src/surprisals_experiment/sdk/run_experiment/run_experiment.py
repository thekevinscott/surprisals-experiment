"""Drive the existing sequential loop from artifacts, including partial turns."""

import json
from collections.abc import Callable
from pathlib import Path

from state_machine import Stop, state_machine

from surprisals_experiment.config import Config
from .actions.write_solutions import write_solutions
from .actions.run_tests import run_tests
from .actions.write_result import write_result
from .actions.write_advice import write_advice
from .actions.score_advice import score_advice
from .actions.write_feedback import write_feedback
from ..database import ExperimentDatabase, QuestionDatabase
from ..turn import Turn
from ..utils.write import write

QUERIES = Path(__file__).parent


async def state(config: Config, database: ExperimentDatabase) -> dict:
    result, = await database.query(
        QUERIES / "run.sql", samples=config.t_samples,
        cap=config.max_u_turns if config.max_u_turns is not None else -1,
        max_stale=config.max_turns_without_improvement,
    )
    return result


async def turn_state(turn: Turn, database: ExperimentDatabase) -> dict:
    result, = await database.query(QUERIES / "turn.sql", **turn.params, samples=turn.config.t_samples)
    return result


async def run_experiment(
    config: Config, *, on_delta: Callable[[str, str], None] | None,
    on_t_delta: Callable[[str, str], None] | None = None,
) -> Path | None:
    settings = config.output / "settings.json"
    if settings.exists():
        config = Config(**(json.loads(settings.read_text()) | {"api_key": config.api_key}))
    config.save_settings()
    database = ExperimentDatabase(config.output)
    await database.dirsql.ready()
    problem = QuestionDatabase(config.problem_dir)
    async def current_turn() -> Turn:
        current = await state(config, database)
        return Turn(config, current["turn"])

    async def read_state() -> str:
        current = await state(config, database)
        if current["state"] != "turn":
            return current["state"]
        stage = await turn_state(Turn(config, current["turn"]), database)
        return stage["state"]

    async def start() -> None:
        write(config.window_dir / "window.json", "{}\n")
        write(config.fork_dir / "fork.json", "{}\n")

    async def advice() -> None:
        await write_advice(await current_turn(), database, problem, on_delta=on_delta)

    async def score() -> None:
        await score_advice(await current_turn(), on_delta=on_delta)

    async def solutions() -> None:
        await write_solutions(await current_turn(), database, on_delta=on_t_delta)

    async def tests() -> None:
        await run_tests(await current_turn(), database, problem)

    async def feedback() -> None:
        turn = await current_turn()
        await write_feedback(turn, database, problem)
        await write_result(turn, database)

    await state_machine(
        state=read_state,
        actions={
            "not_started": start,
            "advice_missing": advice,
            "unscored": score,
            "solutions_missing": solutions,
            "untested": tests,
            "feedback_missing": feedback,
            "stopped": Stop,
        },
    )
    turn = await current_turn()
    solution, _ = await write_result(turn, database)
    if solution is None:
        write(config.error_file, f"No passing solution after {turn.position} U turns\n")
    return solution
