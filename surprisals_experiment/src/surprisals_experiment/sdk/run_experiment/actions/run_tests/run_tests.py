import traceback
from pathlib import Path


from ....turn import Turn
from ....utils.write import write
from ....database import ExperimentDatabase, QuestionDatabase
from ....run_test_suite import run_test_suite

PENDING = Path(__file__).with_name("pending_samples.sql")


async def run_tests(turn: Turn, database: ExperimentDatabase, problem: QuestionDatabase):
    samples = await database.query(PENDING, **turn.params, samples=turn.config.t_samples)
    try:
        await run_test_suite(turn.config, [turn.t_dir(sample["position"]) / "src" for sample in samples], problem)
    except Exception:
        write(turn.attempt_dir / "error.txt", traceback.format_exc())
        raise
