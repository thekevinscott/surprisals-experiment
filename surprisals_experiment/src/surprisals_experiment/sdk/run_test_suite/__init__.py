"""Hidden-test evaluation API."""

from .results import TestResult, TestSuiteResult
from .run_test_suite import run_test_suite
from .run_test_suite_for_ts import run_test_suite_for_ts

__all__ = ["TestResult", "TestSuiteResult", "run_test_suite", "run_test_suite_for_ts"]
