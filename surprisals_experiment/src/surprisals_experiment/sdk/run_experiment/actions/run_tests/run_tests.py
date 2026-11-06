import traceback
from pathlib import Path

from ....run import Run
from ....sample import Sample
from ....utils.write import write
from ....run_test_suite import run_test_suite

T = Path(__file__).with_name("t.sql")


async def run_tests(run: Run, sample: Sample) -> None:
    t, = await run.database.query(T, **sample.params)
    try:
        await run_test_suite(sample.turn.config, [sample.turn.config.output / t["id"] / "src"], run.problem)
    except Exception:
        write(sample.turn.attempt_dir / "error.txt", traceback.format_exc())
        raise
