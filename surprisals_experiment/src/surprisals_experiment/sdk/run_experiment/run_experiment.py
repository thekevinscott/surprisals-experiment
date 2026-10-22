"""Run the experiment through the Python SDK."""

import json
import traceback
from itertools import count
from collections.abc import Callable
from pathlib import Path

from surprisals_experiment.config import Config
from .prompt_t_to_produce_code import prompt_t_to_produce_code
from .test_code import test_code
from .prepare_advice import prepare_advice
from .prepare_feedback import prepare_feedback
from ..utils.u_session import open_u_session


async def run_experiment(
    config: Config, *, on_delta: Callable[[str, str], None] | None,
    on_t_delta: Callable[[str, str], None] | None = None,
) -> Path | None:
    """Generate, test, and shorten advice until the failure limit, turn limit, or interruption."""
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
    max_chars = config.u_advice_max_chars
    best_solution = None
    consecutive_failures = 0
    attempts = count() if config.max_u_turns is None else range(config.max_u_turns)
    async with open_u_session(config) as u_session:
        for attempt in attempts:
            advice = await prepare_advice(
                config, u_session, prompt, attempt=attempt, max_chars=max_chars, on_delta=on_delta,
            )
            try:
                solutions = await prompt_t_to_produce_code(
                    config, attempt=attempt, advice=advice,
                    snapshot=u_session.solutions / str(attempt), on_delta=on_t_delta,
                )
                results = await test_code(
                    config, solutions, test_suite,
                )
            except Exception:
                (config.attempt_dir(attempt) / "error.txt").write_text(traceback.format_exc())
                raise
            if all(result.all_passed for result in results):
                consecutive_failures = 0
                best_solution = solutions[0]
                max_chars = len(advice)
                prompt = (
                    f"Your previous advice was {max_chars} characters and all {len(results)} "
                    "solutions passed every test. Write shorter, self-contained advice that "
                    f"preserves effectiveness. Use fewer than {max_chars} characters, including "
                    "spaces and newlines; the shorter, the better. Return only the instructions to T."
                )
                (config.attempt_dir(attempt) / "feedback.txt").write_text(prompt)
            else:
                consecutive_failures += 1
                prompt = prepare_feedback(config, attempt, results)
            config.result_file.write_text(json.dumps({
                "success": best_solution is not None,
                "attempts": attempt + 1,
                "solution": str(best_solution) if best_solution is not None else None,
            }, indent=2) + "\n")
            if consecutive_failures >= config.max_consecutive_failures:
                break
    if best_solution is None:
        config.error_file.write_text(f"No passing solution after {attempt + 1} U turns\n")
    return best_solution
