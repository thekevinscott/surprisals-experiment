"""Evaluate every generated solution on every testcase and preserve results."""

import json
import time
from dataclasses import asdict
from pathlib import Path

from surprisals_experiment.config import Config
from .results import TestSuiteResult
from .run_test_suite import run_test_suite


async def run_test_suite_for_ts(
    config: Config, solutions: list[Path], test_suite: dict,
) -> list[TestSuiteResult]:
    results = []
    for solution in solutions:
        started = time.monotonic()
        result = await run_test_suite(test_suite, solution)
        duration = round(time.monotonic() - started, 3)
        (solution.parent / "tests.json").write_text(json.dumps({
            "duration_seconds": duration,
            "passed": result.passed,
            "failed": result.failed,
            "total": result.total,
            "all_passed": result.all_passed,
            "cases": [asdict(case) for case in result.cases],
        }, indent=2) + "\n")
        results.append(result)
    return results
