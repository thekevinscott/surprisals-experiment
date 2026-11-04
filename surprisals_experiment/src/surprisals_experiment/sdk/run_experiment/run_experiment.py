"""Run the experiment through the Python SDK."""

import json
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
from ..utils.u_chat import open_u_session
from ..utils.u_chat.history import build_messages, measured_state


async def run_experiment(
    config: Config, *, on_delta: Callable[[str, str], None] | None,
    on_t_delta: Callable[[str, str], None] | None = None,
) -> Path | None:
    """Generate, test, and shorten advice until the no-improvement limit, turn limit, or interruption."""
    test_suite = json.loads(config.test_suite_file.read_text())
    if not isinstance(test_suite, dict) or test_suite.get("fn_name"):
        raise ValueError("Only stdin/stdout test suites are supported")
    inputs, outputs = test_suite.get("inputs"), test_suite.get("outputs")
    if (not isinstance(inputs, list) or not isinstance(outputs, list)
            or not inputs or len(inputs) != len(outputs)
            or not all(isinstance(value, str) for value in inputs + outputs)):
        raise ValueError("Test suite requires equally sized, nonempty inputs and outputs lists of strings")
    config.save_settings()
    best_length = None
    best_solution = None
    turns_without_improvement = 0
    history = []
    attempts = count() if config.max_u_turns is None else range(config.max_u_turns)
    async with open_u_session(config) as u_session:
        for attempt in attempts:
            messages = build_messages(config, attempt)
            summary_file = config.attempt_dir(attempt) / "summary.txt"
            if (not config.u_flush and attempt and config.u_compact_chars
                    and not summary_file.exists()
                    and sum(len(m.get("content") or "") + len(m.get("reasoning") or "")
                            for m in messages) > config.u_compact_chars):
                await u_session.compact(
                    messages[:-1], summary_file, question=config.question_file.read_text(),
                    **measured_state(config, attempt), on_delta=on_delta,
                )
                messages = build_messages(config, attempt)
            advice = await write_advice(
                config, u_session, messages, attempt=attempt, on_delta=on_delta,
            )
            measurement = await score_advice(
                config, advice, attempt=attempt, on_delta=on_delta,
            )
            solutions = await write_solutions(
                config, attempt=attempt, advice=advice,
                on_delta=on_t_delta,
                folders=[config.t_dir(attempt, s) for s in range(config.t_samples)],
            )
            results = await run_tests(config, solutions, test_suite, attempt=attempt)
            best_length, best_solution, turns_without_improvement = write_feedback(
                config, attempt, advice, measurement, solutions, results,
                best_length, best_solution, turns_without_improvement, history,
            )
            write_result(config, attempt=attempt, best_length=best_length, best_solution=best_solution)
            if turns_without_improvement >= config.max_turns_without_improvement:
                break
    if best_solution is None:
        config.error_file.write_text(f"No passing solution after {attempt + 1} U turns\n")
    return best_solution
