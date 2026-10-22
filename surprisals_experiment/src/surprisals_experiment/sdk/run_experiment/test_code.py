"""Evaluate every generated solution on every testcase and preserve results."""

import json
from dataclasses import asdict
from pathlib import Path

from surprisals_experiment.config import Config
from ..run_test_suite import TestSuiteResult, run_test_suite


async def test_code(
    config: Config, solutions: list[Path], test_suite: dict,
) -> list[TestSuiteResult]:
    results = []
    for solution in solutions:
        result = await run_test_suite(test_suite, solution, timeout_seconds=config.test_timeout_seconds)
        (solution.parent / "tests.json").write_text(json.dumps({
            "passed": result.passed,
            "failed": result.failed,
            "total": result.total,
            "all_passed": result.all_passed,
            "cases": [asdict(case) for case in result.cases],
        }, indent=2) + "\n")
        results.append(result)
    return results
