"""Evaluate each T and leave its results in tests.json."""

from pathlib import Path

from .run_test_suite import run_test_suite


async def run_test_suite_for_ts(solutions: list[Path], test_suite: dict) -> None:
    for solution in solutions:
        await run_test_suite(test_suite, solution)
