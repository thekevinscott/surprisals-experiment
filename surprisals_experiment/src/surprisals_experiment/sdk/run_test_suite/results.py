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
