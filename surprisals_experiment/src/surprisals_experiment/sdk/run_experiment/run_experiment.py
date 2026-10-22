"""Run the experiment through the Python SDK."""

import json
import traceback
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
    """Keep failed attempts and return the first passing folder, or None."""
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
    async with open_u_session(config) as u_session:
        for attempt in range(config.max_u_turns):
            advice = await prepare_advice(
                config, u_session, prompt, attempt=attempt, on_delta=on_delta,
            )
            try:
                solutions = await prompt_t_to_produce_code(
                    config, attempt=attempt, advice=advice,
                    snapshot=u_session.solutions / str(attempt), on_delta=on_t_delta,
                )
                results = await test_code(config, solutions, test_suite)
            except Exception:
                (config.attempt_dir(attempt) / "error.txt").write_text(traceback.format_exc())
                raise
            output = solutions[0]
            if all(result.all_passed for result in results):
                break
            if attempt + 1 < config.max_u_turns:
                prompt = prepare_feedback(config, attempt, results)
        else:
            output = None
    config.result_file.write_text(json.dumps({
        "success": output is not None,
        "attempts": attempt + 1,
        "solution": str(output) if output is not None else None,
    }, indent=2) + "\n")
    if output is None:
        config.error_file.write_text(f"No passing solution after {config.max_u_turns} U turns\n")
    return output
