"""Drive the experiment from artifacts; startup and restart use the same classifiers."""

import asyncio
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

QUERIES = Path(__file__).with_name("queries")


async def state(config: Config, database: ExperimentDatabase) -> dict:
    result, = await query(database, config, QUERIES / "run.sql")
    return result


async def fork_state(config: Config, database: ExperimentDatabase) -> dict:
    rows = await query(database, config, QUERIES / "fork.sql")
    return rows[0] if rows else {"state": "complete"}


async def drive_fork(config: Config, database: ExperimentDatabase, problem: QuestionDatabase, *,
                     on_delta=None, on_t_delta=None):
    while True:
        current = await fork_state(config, database)
        if current["state"] == "complete":
            return
        turn = config.at(window=config.position["window"], fork=config.position["fork"], turn=current["turn"])
        if current["state"] == "advice_missing":
            await write_advice(turn, database, problem, on_delta=on_delta)
        elif current["state"] == "feedback_missing":
            await write_feedback(turn, database, problem)
            await write_result(config, database)
        else:
            link, = await query(database, turn, QUERIES / "advice.sql")
            advice = Advice((config.output / link["advice_id"] / "advice.txt").read_bytes().decode("utf-8"),
                            config.advice_measure, config.output)
            if current["state"] == "unscored":
                await score_advice(turn, database, advice, on_delta=on_delta)
            else:
                if current["state"] == "solutions_missing":
                    await write_solutions(turn, database, advice, on_delta=on_t_delta)
                else:
                    await run_tests(turn, database, problem)


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
                write(config.error_file, "No passing solution before the stop rule or turn cap\n")
            return solution
        scoped = config.at(window=current["window"], fork=current["fork"], turn=10)
        if current["state"] == "window_missing":
            write(scoped.window_dir / "window.json", "{}\n")
        elif current["state"] == "fork_round":
            # Fork markers can be missing after interruption during window creation.
            async def fork(position):
                scope = config.at(window=current["window"], fork=position)
                if not (scope.fork_dir / "fork.json").exists():
                    write(scope.fork_dir / "fork.json", "{}\n")
                await drive_fork(scope, database, problem, on_delta=on_delta, on_t_delta=on_t_delta)

            tasks = [asyncio.create_task(fork(position)) for position in range(4)]
            try:
                await asyncio.gather(*tasks)
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        else:
            await drive_fork(scoped, database, problem, on_delta=on_delta, on_t_delta=on_t_delta)
