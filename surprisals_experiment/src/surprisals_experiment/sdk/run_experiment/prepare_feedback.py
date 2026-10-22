"""Prepare feedback for the next U turn from the preserved submission."""

from importlib.resources import files
from pathlib import Path

from .read_implementations import read_implementations

from surprisals_experiment.config import Config
from ..run_test_suite import TestSuiteResult

TEMPLATE = files("surprisals_experiment").joinpath("prompts/u_feedback.txt").read_text()


def prepare_feedback(
    config: Config, attempt: int, results: list[TestSuiteResult], *,
    snapshot: Path, advice_length: int, best_length: int | None, turns_without_improvement: int,
) -> str:
    evaluations = "\n".join(
        f"T {index}: solution in /solutions/{attempt}/{index}; "
        f"passed {sample.passed} of {sample.total} tests."
        for index, sample in enumerate(results)
    )
    feedback = TEMPLATE.format(
        implementation_access=files("surprisals_experiment").joinpath(
            f"prompts/u_context_{config.u_mode}.txt",
        ).read_text(),
        implementations=read_implementations(snapshot) if config.u_mode == "chat" else "",
        evaluations=evaluations, passed=sum(result.all_passed for result in results), total=len(results),
        advice_length=advice_length, best_length=best_length,
        turns_without_improvement=turns_without_improvement,
        max_turns_without_improvement=config.max_turns_without_improvement,
    )
    (config.attempt_dir(attempt) / "feedback.txt").write_text(feedback)
    return feedback
