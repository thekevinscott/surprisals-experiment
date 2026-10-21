"""Generate, preserve, and evaluate T's submission."""

import json
import shutil
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from surprisals_experiment.config import Config
from ..utils.transcripts import save_transcripts
from ..prompt_t import prompt_t
from ..run_test_suite import TestSuiteResult, run_test_suite


def evaluate_attempt(config: Config, *, attempt: int, advice: str, test_suite: dict, snapshot: Path,
                on_delta: Callable[[str, str], None] | None = None) -> tuple[Path, TestSuiteResult]:
    attempt_dir = config.attempt_dir(attempt)
    output = attempt_dir / "src"
    t_run = prompt_t(config, advice, output=output, on_delta=on_delta)
    diagnostics = asdict(t_run)
    save_transcripts(diagnostics.pop("transcript"), attempt_dir / "t_transcripts")
    (attempt_dir / "run.json").write_text(json.dumps(diagnostics, indent=2) + "\n")
    if t_run.exit_code == -1:
        raise RuntimeError("T infrastructure failed: botbox could not obtain an exit code")
    shutil.copytree(output, snapshot, symlinks=True)
    results = run_test_suite(test_suite, output, timeout_seconds=config.test_timeout_seconds)
    (attempt_dir / "tests.json").write_text(json.dumps({
        "passed": results.passed,
        "failed": results.failed,
        "total": results.total,
        "all_passed": results.all_passed,
        "cases": [asdict(case) for case in results.cases],
    }, indent=2) + "\n")
    return output, results
