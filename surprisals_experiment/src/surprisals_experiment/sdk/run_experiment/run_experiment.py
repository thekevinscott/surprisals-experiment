"""Run the experiment through the Python SDK."""

import json
from collections.abc import Callable
from pathlib import Path

from surprisals_experiment.config import Config
from .run_attempt import run_attempt
from .save_advice import save_advice
from .prepare_feedback import prepare_feedback
from ..utils.u_session import open_u_session


def run_experiment(
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
    with open_u_session(config) as u_session:
        for attempt in range(config.max_u_turns):
            for candidate in range(config.u_advice_retries + 1):
                advice = u_session.prompt(prompt, on_delta=on_delta)
                measurement = len(advice)
                rejected = config.u_advice_max_chars is not None and measurement >= config.u_advice_max_chars
                save_advice(config.advice_dir(attempt, candidate), advice,
                            rejected=rejected, measurement=measurement)
                if not rejected:
                    break
                prompt = (f"Your advice was {measurement} characters. It must be fewer than "
                          f"{config.u_advice_max_chars} characters, including spaces and newlines. "
                          "Rewrite it to meet that limit. Return only the instructions to T.")
            else:
                raise RuntimeError(
                    f"U advice exceeded the character limit after {config.u_advice_retries} retries"
                )
            output, results = run_attempt(
                config, attempt=attempt, advice=advice, test_suite=test_suite,
                snapshot=u_session.solutions / str(attempt), on_delta=on_t_delta,
            )
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
