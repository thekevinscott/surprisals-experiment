import traceback
from pathlib import Path

from surprisals_experiment.config import Config
from surprisals_experiment.retry_policy import retried
from ....utils.write import write
from ....database import ExperimentDatabase, QuestionDatabase
from ....run_test_suite import run_test_suite
from ...queries import query

SAMPLES = Path(__file__).parents[2] / "queries/samples.sql"


@retried(operation="Test evaluation")
async def run_tests(config: Config, database: ExperimentDatabase, problem: QuestionDatabase):
    samples = await query(database, config, SAMPLES)
    try:
        await run_test_suite(config, [config.t_dir(config.position["turn"], sample["position"]) / "src"
                                     for sample in samples if sample["state"] == "untested"], problem)
    except Exception:
        write(config.attempt_dir(config.position["turn"]) / "error.txt", traceback.format_exc())
        raise
