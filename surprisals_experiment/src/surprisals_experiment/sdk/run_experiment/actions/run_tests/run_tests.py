import traceback
from pathlib import Path

from ....run import Run
from ....sample import Sample
from ....utils.write import write
from ....run_test_suite import run_test_suite

ATTEMPT = Path(__file__).with_name("attempt.sql")


async def run_tests(run: Run, sample: Sample) -> None:
    row, = await run.database.query(ATTEMPT, **sample.params)
    source = sample.t_dir / "attempts" / str(row["attempt"]) / "src"
    try:
        await run_test_suite(sample.turn.config, [source], run.problem)
    except Exception:
        write(sample.turn.attempt_dir / "error.txt", traceback.format_exc())
        raise
