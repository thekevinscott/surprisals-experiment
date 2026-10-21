"""Structured case and suite results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TestResult:
    index: int
    passed: bool
    status: str
    stdout: str
    stderr: str
    exit_code: int | None


@dataclass(frozen=True)
class TestSuiteResult:
    cases: list[TestResult]

    @property
    def passed(self) -> int:
        return sum(case.passed for case in self.cases)

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def all_passed(self) -> bool:
        return self.total > 0 and self.passed == self.total
