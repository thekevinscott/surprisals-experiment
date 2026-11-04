"""Describe each T sample's test result for the next U turn."""

from surprisals_experiment.config import Config
from ..run_test_suite import TestSuiteResult


def describe_result(config: Config, attempt: int, index: int, sample: TestSuiteResult) -> str:
    t_dir = config.t_dir(attempt, index)
    timed_out = (t_dir / "timeouts.txt").exists() and not any((t_dir / "src").iterdir())
    return f"passed {sample.passed} of {sample.total} tests" + (
        "; timed out on every try and wrote no solution" if timed_out else ""
    )
