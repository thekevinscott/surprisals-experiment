"""Run an attempt and preserve its error if evaluation fails."""

import traceback
from collections.abc import Callable
from pathlib import Path

from surprisals_experiment.config import Config
from .batch_result import BatchResult
from .evaluate_attempt import evaluate_attempt


def run_attempt(config: Config, *, attempt: int, advice: str, test_suite: dict, snapshot: Path,
                on_delta: Callable[[str, str], None] | None = None) -> tuple[Path, BatchResult]:
    attempt_dir = config.attempt_dir(attempt)
    attempt_dir.mkdir(parents=True, exist_ok=True)
    try:
        batch = BatchResult(config.t_samples)
        for sample in range(config.t_samples):
            sample_snapshot = snapshot if config.t_samples == 1 else snapshot / str(sample)
            _, results = evaluate_attempt(
                config, attempt=attempt, sample=sample, advice=advice,
                test_suite=test_suite, snapshot=sample_snapshot, on_delta=on_delta,
            )
            batch.samples.append(results)
        return config.t_dir(attempt, 0) / "src", batch
    except Exception:
        (attempt_dir / "error.txt").write_text(traceback.format_exc())
        raise
