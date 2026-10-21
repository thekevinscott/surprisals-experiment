"""Prepare feedback for the next U turn from the preserved submission."""

from importlib.resources import files

from surprisals_experiment.config import Config
from .batch_result import BatchResult

TEMPLATE = files("surprisals_experiment").joinpath("prompts/u_feedback.txt").read_text()


def prepare_feedback(config: Config, attempt: int, results: BatchResult) -> str:
    evaluations = "\n".join(
        f"T {index}: solution in /solutions/{attempt}"
        f"{'/' + str(index) if config.t_samples > 1 else ''}; "
        f"passed {sample.passed} of {sample.total} tests."
        for index, sample in enumerate(results.samples)
    )
    feedback = TEMPLATE.format(evaluations=evaluations, passed=results.passed, total=results.expected)
    (config.attempt_dir(attempt) / "feedback.txt").write_text(feedback)
    return feedback
