"""Persist batch progress, including incomplete batches."""

import json
from pathlib import Path

from .batch_result import BatchResult


def save_batch_result(batch: BatchResult, path: Path) -> None:
    path.write_text(json.dumps({
        "expected": batch.expected,
        "completed": len(batch.samples),
        "passed": batch.passed,
        "tests_passed": sum(sample.passed for sample in batch.samples),
        "tests_total": sum(sample.total for sample in batch.samples),
        "all_passed": batch.all_passed,
    }, indent=2) + "\n")
