"""Run the experiment through the Python SDK."""

import json
import traceback
from itertools import count
from collections.abc import Callable
from pathlib import Path

from surprisals_experiment.config import Config
from .prompt_t_to_produce_code import prompt_t_to_produce_code
from ..run_test_suite import run_test_suite_for_ts
from .prepare_advice import prepare_advice
from .prepare_feedback import describe_result, prepare_feedback
from .prepare_flush import Attempt, prepare_flush
from .read_implementations import read_sources
from ..utils.u_session import open_u_session
from ..utils.u_chat import ChatSession


async def run_experiment(
    config: Config, *, on_delta: Callable[[str, str], None] | None,
    on_t_delta: Callable[[str, str], None] | None = None,
) -> Path | None:
    """Generate, test, and shorten advice until the no-improvement limit, turn limit, or interruption."""
    prompt = config.question_file.read_text()
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
            advice, measurement = await prepare_advice(
                config, u_session, prompt, attempt=attempt, on_delta=on_delta,
            )
            try:
                solutions = await prompt_t_to_produce_code(
                    config, attempt=attempt, advice=advice,
                    snapshot=u_session.solutions / str(attempt), on_delta=on_t_delta,
                )
                results = await run_test_suite_for_ts(config, solutions, test_suite)
            except Exception:
                (config.attempt_dir(attempt) / "error.txt").write_text(traceback.format_exc())
                raise
            if (all(result.all_passed for result in results)
                    and (best_length is None or measurement < best_length)):
                turns_without_improvement = 0
                best_solution = solutions[0]
                best_length = measurement
                if isinstance(u_session, ChatSession):
                    u_session.best_advice = advice
            else:
                turns_without_improvement += 1
            if isinstance(u_session, ChatSession):
                u_session.best_length = best_length
                u_session.turns_without_improvement = turns_without_improvement
            if config.u_flush:
                history.append(Attempt(
                    attempt, advice, measurement,
                    [describe_result(config, attempt, index, sample) for index, sample in enumerate(results)],
                    all(result.all_passed for result in results), read_sources(u_session.solutions / str(attempt)),
                    config.advice_measure.scores.get(advice),
                ))
                u_session.messages = u_session.messages[:1]
                prompt = prepare_flush(config, history)
                (config.attempt_dir(attempt) / "feedback.txt").write_text(prompt)
            else:
                prompt = prepare_feedback(
                    config, attempt, results, snapshot=u_session.solutions / str(attempt),
                    advice_length=measurement,
                    best_length=best_length, turns_without_improvement=turns_without_improvement,
                )
            config.result_file.write_text(json.dumps({
                **config.advice_measure.result_fields(best_length),
                "success": best_solution is not None,
                "attempts": attempt + 1,
                "solution": str(best_solution) if best_solution is not None else None,
            }, indent=2) + "\n")
            if turns_without_improvement >= config.max_turns_without_improvement:
                break
    if best_solution is None:
        config.error_file.write_text(f"No passing solution after {attempt + 1} U turns\n")
    return best_solution
