import traceback

from ....run import Run
from ....sample import Sample
from ....utils.write import write
from ....run_test_suite import run_test_suite


async def run_tests(run: Run, sample: Sample) -> None:
    try:
        await run_test_suite(sample.turn.config, [sample.t_dir / "src"], run.problem)
    except Exception:
        write(sample.turn.attempt_dir / "error.txt", traceback.format_exc())
        raise
