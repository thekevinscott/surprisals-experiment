"""Drive windows, fork rounds, and turns from disk-derived state."""

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


async def drive_fork(config: Config, database: ExperimentDatabase, problem: QuestionDatabase,
                     window: int, fork: int, start: int, end: int, *, on_delta=None, on_t_delta=None):
    while True:
        pending = await database.query(
            QUERIES / "fork.sql", window=window, fork=fork, start=start, end=end,
            samples=config.t_samples,
        )
        if not pending:
            return
        turn = Turn(config, pending[0]["turn"], window, fork)
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
        window = current["window"]
        fork = current["fork"]
        if current["state"] == "stopped":
            solution, _ = await write_result(Turn(config, 39, window - 1, fork), database)
            if solution is None:
                write(config.error_file, "No passing solution before the stop rule or turn cap\n")
            return solution
        if current["state"] == "window_missing":
            write(config.output / "windows" / str(window) / "window.json", "{}\n")
        elif current["state"] == "fork_round":
            end = min(10, config.max_u_turns - window * 40) if config.max_u_turns is not None else 10

            async def run_fork(position):
                folder = config.output / "windows" / str(window) / "forks" / str(position)
                if not (folder / "fork.json").exists():
                    write(folder / "fork.json", "{}\n")
                await drive_fork(config, database, problem, window, position, 0, end,
                                 on_delta=on_delta, on_t_delta=on_t_delta)

            tasks = [asyncio.create_task(run_fork(position)) for position in range(4)]
            try:
                await asyncio.gather(*tasks)
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            await write_result(Turn(config, min(9, end - 1), window, fork), database)
        else:
            end = min(40, config.max_u_turns - window * 40) if config.max_u_turns is not None else 40
            await drive_fork(config, database, problem, window, fork, 10, end,
                             on_delta=on_delta, on_t_delta=on_t_delta)
