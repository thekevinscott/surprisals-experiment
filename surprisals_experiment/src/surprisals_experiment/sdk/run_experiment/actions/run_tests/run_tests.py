import traceback

from ....turn import Turn
from ....utils.write import write
from ....database import QuestionDatabase
from ....run_test_suite import run_test_suite


async def run_tests(turn: Turn, problem: QuestionDatabase):
    try:
        await run_test_suite(turn.config, [turn.t_dir(sample) / "src" for sample in range(turn.config.t_samples)], problem)
    except Exception:
        write(turn.attempt_dir / "error.txt", traceback.format_exc())
        raise
