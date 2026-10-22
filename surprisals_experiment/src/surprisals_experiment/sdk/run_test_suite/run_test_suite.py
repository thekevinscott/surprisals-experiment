"""Run and tally stdin/stdout tests."""

from pathlib import Path

from .results import TestSuiteResult
from .run_case import run_case


async def run_test_suite(test_suite: dict, solution_dir: Path, *, timeout_seconds: float) -> TestSuiteResult:
    """Run main.py for each input and collect successes and failures."""
    return TestSuiteResult([
        await run_case(index, stdin, expected, solution_dir, timeout_seconds)
        for index, (stdin, expected) in enumerate(zip(test_suite["inputs"], test_suite["outputs"], strict=True))
    ])
