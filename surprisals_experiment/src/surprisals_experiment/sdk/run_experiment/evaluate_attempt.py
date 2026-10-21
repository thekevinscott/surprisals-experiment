"""Evaluate an advice batch and retain every T submission."""

import json
import shutil
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from surprisals_experiment.config import Config
from ..utils.transcripts import save_transcripts
from ..prompt_t import prompt_t
from ..run_test_suite import run_test_suite
from .batch_result import BatchResult
from .save_batch_result import save_batch_result


def evaluate_attempt(config: Config, *, attempt: int, advice: str, test_suite: dict, snapshot: Path,
                on_delta: Callable[[str, str], None] | None = None) -> tuple[Path, BatchResult]:
    attempt_dir = config.attempt_dir(attempt)
    batch = BatchResult(config.t_samples)
    save_batch_result(batch, attempt_dir / "batch.json")
    for sample in range(config.t_samples):
        sample_dir = config.t_dir(attempt, sample)
        sample_dir.mkdir(parents=True, exist_ok=True)
        output = sample_dir / "src"
        t_run = prompt_t(config, advice, output=output, on_delta=on_delta)
        diagnostics = asdict(t_run)
        save_transcripts(diagnostics.pop("transcript"), sample_dir / "t_transcripts")
        (sample_dir / "run.json").write_text(json.dumps(diagnostics, indent=2) + "\n")
        if t_run.exit_code == -1:
            raise RuntimeError("T infrastructure failed: botbox could not obtain an exit code")
        sample_snapshot = snapshot if config.t_samples == 1 else snapshot / str(sample)
        shutil.copytree(output, sample_snapshot, symlinks=True)
        results = run_test_suite(test_suite, output, timeout_seconds=config.test_timeout_seconds)
        (sample_dir / "tests.json").write_text(json.dumps({
            "passed": results.passed,
            "failed": results.failed,
            "total": results.total,
            "all_passed": results.all_passed,
            "cases": [asdict(case) for case in results.cases],
        }, indent=2) + "\n")
        batch.samples.append(results)
        save_batch_result(batch, attempt_dir / "batch.json")
    return config.t_dir(attempt, 0) / "src", batch
