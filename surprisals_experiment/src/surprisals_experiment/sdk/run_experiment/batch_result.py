"""Outcomes from independent T evaluations of the same advice."""

from dataclasses import dataclass, field

from ..run_test_suite import TestSuiteResult


@dataclass
class BatchResult:
    expected: int
    samples: list[TestSuiteResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(sample.all_passed for sample in self.samples)

    @property
    def all_passed(self) -> bool:
        return len(self.samples) == self.expected and self.passed == self.expected
