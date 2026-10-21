"""Hidden-test evaluation API."""

from .results import TestResult, TestSuiteResult
from .run_test_suite import run_test_suite

__all__ = ["TestResult", "TestSuiteResult", "run_test_suite"]
