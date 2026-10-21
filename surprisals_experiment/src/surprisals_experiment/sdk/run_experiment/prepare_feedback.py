"""Prepare feedback for the next U turn from the preserved submission."""

from importlib.resources import files

from surprisals_experiment.config import Config
from ..run_test_suite import TestSuiteResult

TEMPLATE = files("surprisals_experiment").joinpath("prompts/u_feedback.txt").read_text()


def prepare_feedback(config: Config, attempt: int, results: TestSuiteResult) -> str:
    feedback = TEMPLATE.format(solution=f"/solutions/{attempt}", passed=results.passed, total=results.total)
    (config.attempt_dir(attempt) / "feedback.txt").write_text(feedback)
    return feedback
