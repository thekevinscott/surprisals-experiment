"""Run the experiment through the Python SDK."""

from itertools import count
from collections.abc import Callable
from pathlib import Path

from surprisals_experiment.config import Config
from .actions.write_solutions import write_solutions
from .actions.run_tests import run_tests
from .actions.write_result import write_result
from .actions.write_advice import write_advice
from .actions.score_advice import score_advice
from .actions.write_feedback import write_feedback
from ..utils.u_chat import open_u_chat
from ..database import ExperimentDatabase, QuestionDatabase
from ..utils.write import write
from ..turn import Turn


async def run_experiment(
    config: Config, *, on_delta: Callable[[str, str], None] | None,
    on_t_delta: Callable[[str, str], None] | None = None,
) -> Path | None:
    """Generate, test, and shorten advice until the no-improvement limit, turn limit, or interruption."""
    problem = QuestionDatabase(config.problem_dir)
    config.save_settings()
    write(config.window_dir / "window.json", "{}\n")
    write(config.fork_dir / "fork.json", "{}\n")
    database = ExperimentDatabase(config.output)
    best_solution = None
    attempts = count() if config.max_u_turns is None else range(config.max_u_turns)
    async with open_u_chat(config) as u_chat:
        for attempt in attempts:
            turn = Turn(config, attempt)
            advice = await write_advice(turn, u_chat, database, problem, on_delta=on_delta)
            await score_advice(turn, advice, on_delta=on_delta)
            await write_solutions(turn, on_delta=on_t_delta)
            await run_tests(turn, problem)
            await write_feedback(turn, database, problem)
            best_solution, turns_without_improvement = await write_result(turn, database)
            if turns_without_improvement >= config.max_turns_without_improvement:
                break
    if best_solution is None:
        write(config.error_file, f"No passing solution after {attempt + 1} U turns\n")
    return best_solution
