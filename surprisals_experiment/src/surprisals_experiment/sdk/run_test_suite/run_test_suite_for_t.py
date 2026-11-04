"""Run and tally stdin/stdout tests."""

from pathlib import Path

from surprisals_experiment.config import TEST_TIMEOUT_SECONDS

from .results import TestSuiteResult
from .run_case import run_case


async def run_test_suite_for_t(test_suite: list[dict], solution_dir: Path) -> TestSuiteResult:
    """Run main.py for each input and collect successes and failures."""
    return TestSuiteResult([
        await run_case(index, case["input"], case["output"], solution_dir, TEST_TIMEOUT_SECONDS)
        for index, case in enumerate(test_suite)
    ])
