"""Prepare feedback for the next U turn from the preserved submission."""

from pathlib import Path

from .read_implementations import read_implementations

from surprisals_experiment.config import Config
from surprisals_experiment.prompts import render
from ..run_test_suite import TestSuiteResult


def prepare_feedback(
    config: Config, attempt: int, results: list[TestSuiteResult], *,
    snapshot: Path, advice_length: int, best_length: int | None, turns_without_improvement: int,
) -> str:
    evaluations = []
    for index, sample in enumerate(results):
        t_dir = config.t_dir(attempt, index)
        evaluations.append({
            "passed": sample.passed,
            "total": sample.total,
            "timed_out": (t_dir / "timeouts.txt").exists() and not any((t_dir / "src").iterdir()),
        })
    feedback = render(
        "u_feedback.j2",
        context_template=f"u_context_{config.u_mode}.j2",
        attempt=attempt,
        implementations=read_implementations(snapshot) if config.u_mode == "chat" else "",
        evaluations=evaluations, passed=sum(result.all_passed for result in results), total=len(results),
        advice_length=advice_length, best_length=best_length,
        turns_without_improvement=turns_without_improvement,
        max_turns_without_improvement=config.max_turns_without_improvement,
    )
    (config.attempt_dir(attempt) / "feedback.txt").write_text(feedback)
    return feedback
