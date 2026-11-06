"""Evaluate every generated solution on every testcase and leave results in tests.json."""

import json
import time
from dataclasses import asdict
from pathlib import Path

from surprisals_experiment.config import Config
from run_database import QuestionDatabase
from ..utils.write import write
from .run_test_suite_for_t import run_test_suite_for_t


async def run_test_suite(
    config: Config, solutions: list[Path], problem: QuestionDatabase,
) -> None:
    test_suite = await problem.test_suite
    for solution in solutions:
        started = time.monotonic()
        result = await run_test_suite_for_t(test_suite, solution)
        duration = round(time.monotonic() - started, 3)
        write(solution.parent / "tests.json", json.dumps({
            "duration_seconds": duration,
            "passed": result.passed,
            "failed": result.failed,
            "total": result.total,
            "all_passed": result.all_passed,
            "cases": [asdict(case) for case in result.cases],
        }, indent=2) + "\n")
