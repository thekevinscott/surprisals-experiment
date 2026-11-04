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
from ..utils.write_text import write_text


async def run_experiment(
    config: Config, *, on_delta: Callable[[str, str], None] | None,
    on_t_delta: Callable[[str, str], None] | None = None,
) -> Path | None:
    """Generate, test, and shorten advice until the no-improvement limit, turn limit, or interruption."""
    problem = QuestionDatabase(config.problem_dir)
    prompt = await problem.question
    config.save_settings()
    write_text(config.window_dir / "window.json", "{}\n")
    write_text(config.fork_dir / "fork.json", "{}\n")
    database = ExperimentDatabase(config.output)
    best_length = None
    best_solution = None
    turns_without_improvement = 0
    attempts = count() if config.max_u_turns is None else range(config.max_u_turns)
    async with open_u_chat(config, problem) as u_chat:
        for attempt in attempts:
            advice = await write_advice(
                config, u_chat, prompt, attempt=attempt, on_delta=on_delta,
            )
            measurement = await score_advice(
                config, advice, attempt=attempt, on_delta=on_delta,
            )
            solutions = await write_solutions(
                config, attempt=attempt, advice=advice,
                on_delta=on_t_delta,
                folders=[config.t_dir(attempt, s) for s in range(config.t_samples)],
            )
            results = await run_tests(config, solutions, problem, attempt=attempt)
            prompt, best_length, best_solution, turns_without_improvement = await write_feedback(
                config, u_chat, attempt, advice, measurement, solutions, results,
                best_length, best_solution, turns_without_improvement, problem, database,
            )
            write_result(config, attempt=attempt, best_length=best_length, best_solution=best_solution)
            if turns_without_improvement >= config.max_turns_without_improvement:
                break
    if best_solution is None:
        config.error_file.write_text(f"No passing solution after {attempt + 1} U turns\n")
    return best_solution
