"""Prepare feedback for the next U turn from the preserved submission."""

from importlib.resources import files
from pathlib import Path

from .read_implementations import read_implementations

from surprisals_experiment.config import Config
from ..run_test_suite import TestSuiteResult

TEMPLATE = files("surprisals_experiment").joinpath("prompts/u_feedback.txt").read_text()


def prepare_feedback(
    config: Config, attempt: int, results: list[TestSuiteResult], *,
    snapshot: Path, advice_length: int | float, best_length: int | float | None, turns_without_improvement: int,
) -> str:
    evaluations = []
    for index, sample in enumerate(results):
        t_dir = config.t_dir(attempt, index)
        ending = "; timed out on every try and wrote no solution." if (
            (t_dir / "timeouts.txt").exists() and not any((t_dir / "src").iterdir())
        ) else "."
        location = f"solution in /solutions/{attempt}/{index}; " if config.u_mode == "agent" else ""
        evaluations.append(
            f"T {index}: {location}"
            f"passed {sample.passed} of {sample.total} tests{ending}"
        )
    feedback = config.advice_measure.render(TEMPLATE).format(
        implementation_access=files("surprisals_experiment").joinpath(
            f"prompts/u_context_{config.u_mode}.txt",
        ).read_text(),
        implementations=read_implementations(snapshot) if config.u_mode == "chat" else "",
        evaluations="\n".join(evaluations), passed=sum(result.all_passed for result in results), total=len(results),
        advice_length=advice_length, best_length=best_length,
        turns_without_improvement=turns_without_improvement,
        max_turns_without_improvement=config.max_turns_without_improvement,
    )
    (config.attempt_dir(attempt) / "feedback.txt").write_text(feedback)
    return feedback
