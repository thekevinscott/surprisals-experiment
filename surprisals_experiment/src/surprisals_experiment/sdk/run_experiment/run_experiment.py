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
from .queries import query
from ..advice import Advice
from ..database import ExperimentDatabase, QuestionDatabase
from ..utils.write import write

QUERIES = Path(__file__).parent


async def state(config: Config, database: ExperimentDatabase) -> dict:
    result, = await query(database, config, QUERIES / "run.sql")
    return result


async def turn_state(config: Config, database: ExperimentDatabase) -> dict:
    result, = await query(database, config, QUERIES / "turn.sql")
    return result


async def run_experiment(
    config: Config, *, on_delta: Callable[[str, str], None] | None,
    on_t_delta: Callable[[str, str], None] | None = None,
) -> Path | None:
    config.save_settings()
    database = ExperimentDatabase(config.output)
    problem = QuestionDatabase(config.problem_dir)
    while True:
        current = await state(config, database)
        if current["state"] == "stopped":
            solution = await write_result(config, database)
            if solution is None:
                write(config.error_file, f"No passing solution after {current['turn']} U turns\n")
            return solution
        if current["state"] == "not_started":
            write(config.window_dir / "window.json", "{}\n")
            write(config.fork_dir / "fork.json", "{}\n")
            continue
        turn = config.at(turn=current["turn"])
        stage = await turn_state(turn, database)
        if stage["state"] == "advice_missing":
            await write_advice(turn, database, problem, on_delta=on_delta)
        elif stage["state"] == "feedback_missing":
            await write_feedback(turn, database, problem)
            await write_result(config, database)
        elif stage["state"] == "untested":
            await run_tests(turn, database, problem)
        else:
            link, = await query(database, turn, QUERIES / "advice.sql")
            advice = Advice((config.output / link["advice_id"] / "advice.txt").read_bytes().decode("utf-8"),
                            config.advice_measure, config.output)
            if stage["state"] == "unscored":
                await score_advice(turn, advice, on_delta=on_delta)
            elif stage["state"] == "solutions_missing":
                await write_solutions(turn, database, advice, on_delta=on_t_delta)
