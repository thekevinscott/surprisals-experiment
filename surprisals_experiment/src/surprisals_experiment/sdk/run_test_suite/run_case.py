"""Run one stdin/stdout test case."""

import subprocess
import sys
from pathlib import Path

from .results import TestResult


def run_case(index: int, stdin: str, expected: str, solution_dir: Path, timeout_seconds: float) -> TestResult:
    try:
        result = subprocess.run(
            [sys.executable, "main.py"],
            cwd=solution_dir,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        passed = result.returncode == 0 and result.stdout.strip() == expected.strip()
        status = "passed" if passed else "runtime_error" if result.returncode else "wrong_answer"
        return TestResult(index, passed, status, result.stdout, result.stderr, result.returncode)
    except (subprocess.TimeoutExpired, UnicodeDecodeError) as error:
        return TestResult(index, False, "error", "", str(error), None)
