"""Drive the existing sequential loop from artifacts, including partial turns."""

from collections.abc import Callable
from pathlib import Path

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
    )
    if result["state"] == "window_missing" and result["window"] > 0:
        stop, = await database.query(
            QUERIES / "window_stop.sql", window=result["window"] - 1, samples=config.t_samples,
        )
        if stop["stopped"]:
            result["state"] = "stopped"
    return result


async def turn_state(turn: Turn, database: ExperimentDatabase) -> dict:
    result, = await database.query(QUERIES / "turn.sql", **turn.params, samples=turn.config.t_samples)
    return result


async def run_experiment(
    config: Config, *, on_delta: Callable[[str, str], None] | None,
    on_t_delta: Callable[[str, str], None] | None = None,
) -> Path | None:
    config.save_settings()
    database = ExperimentDatabase(config.output)
    await database.dirsql.ready()
    problem = QuestionDatabase(config.problem_dir)
    while True:
        current = await state(config, database)
        turn = Turn(config, current["turn"])
        if current["state"] == "stopped":
            solution, _ = await write_result(turn, database)
            if solution is None:
                write(config.error_file, f"No passing solution after {turn.position} U turns\n")
            return solution
        if current["state"] == "not_started":
            write(config.window_dir / "window.json", "{}\n")
            write(config.fork_dir / "fork.json", "{}\n")
            continue
        stage = await turn_state(turn, database)
        if stage["state"] == "advice_missing":
            await write_advice(turn, database, problem, on_delta=on_delta)
        elif stage["state"] == "unscored":
            await score_advice(turn, on_delta=on_delta)
        elif stage["state"] == "solutions_missing":
            await write_solutions(turn, database, on_delta=on_t_delta)
        elif stage["state"] == "untested":
            await run_tests(turn, database, problem)
        elif stage["state"] == "feedback_missing":
            await write_feedback(turn, database, problem)
            await write_result(turn, database)
