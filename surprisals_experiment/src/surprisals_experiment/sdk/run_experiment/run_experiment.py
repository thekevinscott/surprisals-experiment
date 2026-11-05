"""Run the experiment through the Python SDK."""

from itertools import count
from collections.abc import Callable
from pathlib import Path

from state_machine import Stop

from surprisals_experiment.config import Config
from .actions.write_solutions import write_solutions
from .actions.write_solutions.produce_code import produce_code
from .actions.run_tests import run_tests
from .actions.write_result import write_result
from .actions.write_advice import write_advice
from .actions.score_advice import score_advice
from .actions.write_feedback import write_feedback
from ..utils.u_chat import open_u_chat
from ..database import ExperimentDatabase, QuestionDatabase
from ..utils.write import write
from ..turn import Turn
from ..run import Run


def start(config: Config) -> None:
    config.save_settings()
    write(config.window_dir / "window.json", "{}\n")
    write(config.fork_dir / "fork.json", "{}\n")


async def feedback(run: Run, turn: Turn):
    await write_feedback(turn, run.database, run.problem)
    return await write_result(turn, run.database)


actions = {
    "not_started": start,
    "advice_missing": write_advice,
    "unscored": score_advice,
    "solutions_missing": write_solutions,
    "solution_missing": produce_code,
    "untested": run_tests,
    "sample_done": Stop,
    "feedback_missing": feedback,
}


async def run_experiment(
    config: Config, *, on_delta: Callable[[str, str], None] | None,
    on_t_delta: Callable[[str, str], None] | None = None,
) -> Path | None:
    """Generate, test, and shorten advice until the no-improvement limit, turn limit, or interruption."""
    problem = QuestionDatabase(config.problem_dir)
    actions["not_started"](config)
    database = ExperimentDatabase(config.output)
    await database.dirsql.ready()
    run = Run(database, problem, actions, on_t_delta)
    best_solution = None
    attempts = count() if config.max_u_turns is None else range(config.max_u_turns)
    async with open_u_chat(config) as u_chat:
        for attempt in attempts:
            turn = Turn(config, attempt)
            advice = await actions["advice_missing"](turn, u_chat, database, problem, on_delta=on_delta)
            await actions["unscored"](turn, advice, on_delta=on_delta)
            await actions["solutions_missing"](run, turn)
            best_solution, turns_without_improvement = await actions["feedback_missing"](run, turn)
            if turns_without_improvement >= config.max_turns_without_improvement:
                break
    if best_solution is None:
        write(config.error_file, f"No passing solution after {attempt + 1} U turns\n")
    return best_solution
