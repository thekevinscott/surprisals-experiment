"""Run the experiment through the Python SDK."""

from collections.abc import Callable
from pathlib import Path

from state_machine import Stop, state_machine

from surprisals_experiment.config import Config
from .actions.write_solutions import write_solutions
from .actions.write_solutions.produce_code import produce_code
from .actions.run_tests import run_tests
from .actions.write_result import read_progress, write_result
from .actions.write_advice import write_advice
from .actions.score_advice import score_advice
from .actions.start import start
from ..utils.u_chat import open_u_chat
from ..database import ExperimentDatabase, QuestionDatabase
from ..utils.write import write
from ..run import Run
from .state.run_fork import turn_pending
from .state.run_window import fork_pending, solo_pending
from .state import state
from .actions.window_pending import window_pending


actions = {
    "not_started": start,
    "advice_missing": write_advice,
    "unscored": score_advice,
    "solutions_missing": write_solutions,
    "solution_missing": produce_code,
    "untested": run_tests,
    "sample_done": Stop,
    "turn_done": Stop,
    "turn_pending": turn_pending,
    "fork_done": Stop,
    "fork_pending": fork_pending,
    "solo_pending": solo_pending,
    "window_done": Stop,
    "window_pending": window_pending,
    "run_done": Stop,
}


async def run_experiment(
    config: Config, *, on_delta: Callable[[str, str], None] | None,
    on_t_delta: Callable[[str, str], None] | None = None,
) -> Path | None:
    """Generate, test, and shorten advice until window improvement falls below 5% or interruption."""
    problem = QuestionDatabase(config.problem_dir)
    database = ExperimentDatabase(config.output)
    await database.dirsql.ready()
    async with open_u_chat(config) as u_chat:
        run = Run(config, database, problem, actions, on_t_delta, u_chat, on_delta)
        await state_machine(state, actions, run)
        await write_result(run)
        result, best_solution = await read_progress(run)
    if best_solution is None:
        write(config.error_file, f"No passing solution after {result['attempts']} U turns\n")
    return best_solution
