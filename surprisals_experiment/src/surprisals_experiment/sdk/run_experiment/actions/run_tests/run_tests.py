import traceback
from pathlib import Path

from surprisals_experiment.config import Config
from ....database import QuestionDatabase
from ....run_test_suite import run_test_suite


async def run_tests(config: Config, solutions: list[Path], problem: QuestionDatabase, *, attempt: int):
    try:
        return await run_test_suite(config, solutions, problem)
    except Exception:
        (config.attempt_dir(attempt) / "error.txt").write_text(traceback.format_exc())
        raise
