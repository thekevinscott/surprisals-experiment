"""Run an attempt and preserve its error if evaluation fails."""

import traceback
from collections.abc import Callable
from pathlib import Path

from surprisals_experiment.config import Config
from ..run_test_suite import TestSuiteResult
from .evaluate_attempt import evaluate_attempt


def run_attempt(config: Config, *, attempt: int, advice: str, test_suite: dict, snapshot: Path,
                on_delta: Callable[[str, str], None] | None = None) -> tuple[Path, TestSuiteResult]:
    attempt_dir = config.attempt_dir(attempt)
    attempt_dir.mkdir(parents=True, exist_ok=True)
    try:
        return evaluate_attempt(config, attempt=attempt, advice=advice, test_suite=test_suite,
                                snapshot=snapshot, on_delta=on_delta)
    except Exception:
        (attempt_dir / "error.txt").write_text(traceback.format_exc())
        raise
