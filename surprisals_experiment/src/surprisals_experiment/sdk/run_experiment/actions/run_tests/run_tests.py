import traceback
from pathlib import Path

from surprisals_experiment.config import Config
from ....utils.write import write
from ....database import QuestionDatabase
from ....run_test_suite import run_test_suite


async def run_tests(config: Config, solutions: list[Path], problem: QuestionDatabase, *, attempt: int):
    try:
        await run_test_suite(config, solutions, problem)
    except Exception:
        write(config.attempt_dir(attempt) / "error.txt", traceback.format_exc())
        raise
