"""Generate, preserve, and evaluate one T sample."""

import json
import shutil
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from surprisals_experiment.config import Config
from ..utils.transcripts import save_transcripts
from ..prompt_t import prompt_t
from ..run_test_suite import TestSuiteResult, run_test_suite


async def evaluate_attempt(config: Config, *, attempt: int, sample: int, advice: str, test_suite: dict, snapshot: Path,
                on_delta: Callable[[str, str], None] | None = None) -> TestSuiteResult:
    sample_dir = config.t_dir(attempt, sample)
    sample_dir.mkdir(parents=True, exist_ok=True)
    output = sample_dir / "src"
    t_run = await prompt_t(config, advice, output=output, on_delta=on_delta)
    diagnostics = asdict(t_run)
    save_transcripts(diagnostics.pop("transcript"), sample_dir / "t_transcripts")
    (sample_dir / "run.json").write_text(json.dumps(diagnostics, indent=2) + "\n")
    if t_run.exit_code == -1:
        raise RuntimeError("T infrastructure failed: botbox could not obtain an exit code")
    shutil.copytree(output, snapshot, symlinks=True)
    results = await run_test_suite(test_suite, output, timeout_seconds=config.test_timeout_seconds)
    (sample_dir / "tests.json").write_text(json.dumps({
        "passed": results.passed,
        "failed": results.failed,
        "total": results.total,
        "all_passed": results.all_passed,
        "cases": [asdict(case) for case in results.cases],
    }, indent=2) + "\n")
    return results
