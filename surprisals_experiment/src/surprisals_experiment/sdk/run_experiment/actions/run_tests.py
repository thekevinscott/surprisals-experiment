import json
import traceback
from pathlib import Path

from surprisals_experiment.config import Config
from ...run_test_suite import run_test_suite_for_ts


async def run_tests(config: Config, solutions: list[Path], *, attempt: int):
    try:
        return await run_test_suite_for_ts(config, solutions, json.loads(config.test_suite_file.read_text()))
    except Exception:
        (config.attempt_dir(attempt) / "error.txt").write_text(traceback.format_exc())
        raise
