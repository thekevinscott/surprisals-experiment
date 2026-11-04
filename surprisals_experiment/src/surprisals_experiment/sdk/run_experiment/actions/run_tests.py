import traceback
from pathlib import Path

from surprisals_experiment.config import Config
from ...run_test_suite import run_test_suite_for_ts


async def run_tests(config: Config, solutions: list[Path], test_suite: dict, *, attempt: int):
    try:
        await run_test_suite_for_ts(solutions, test_suite)
    except Exception:
        (config.attempt_dir(attempt) / "error.txt").write_text(traceback.format_exc())
        raise
