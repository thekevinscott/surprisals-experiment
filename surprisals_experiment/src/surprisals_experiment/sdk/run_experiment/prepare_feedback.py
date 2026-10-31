"""Prepare feedback for the next U turn from the preserved submission."""

import json
from pathlib import Path

from .read_implementations import read_implementations

from surprisals_experiment.config import Config
from surprisals_experiment.prompt import Prompt
from ..run_test_suite import TestSuiteResult

FEEDBACK = Prompt("u/feedback.txt")
CONTEXT = Prompt("u/chat/context.txt")


def describe_result(config: Config, attempt: int, index: int, sample: TestSuiteResult) -> str:
    t_dir = config.t_dir(attempt, index)
    timed_out = (t_dir / "timeouts.txt").exists() and not any((t_dir / "src").iterdir())
    return f"passed {sample.passed} of {sample.total} tests" + (
        "; timed out on every try and wrote no solution" if timed_out else ""
    )


def prepare_feedback(
    config: Config, attempt: int, results: list[TestSuiteResult], *,
    snapshot: Path, advice_length: int | float, best_length: int | float | None, turns_without_improvement: int,
) -> str:
    evaluations = []
    for index, sample in enumerate(results):
        evaluations.append(f"T {index}: {describe_result(config, attempt, index, sample)}.")
    advice_measurement = f"Your advice was {advice_length} characters."
    if config.cap_strategy == "surprisal":
        metadata = json.loads((config.advice_dir(attempt, 0) / "metadata.json").read_text())
        annotated = "".join(f"{token}<{bits:.1f}>" for token, bits in metadata["tokens"])
        advice_measurement = f"Your advice cost {advice_length:.1f} bits:\n{annotated}"
    feedback = FEEDBACK(
        unit=config.advice_measure.unit, measure_wording=config.advice_measure.wording,
        implementation_access=CONTEXT(),
        implementations=read_implementations(snapshot),
        evaluations="\n".join(evaluations), passed=sum(result.all_passed for result in results), total=len(results),
        advice_measurement=advice_measurement, best_length=best_length,
        turns_without_improvement=turns_without_improvement,
        max_turns_without_improvement=config.max_turns_without_improvement,
    )
    (config.attempt_dir(attempt) / "feedback.txt").write_text(feedback)
    return feedback
