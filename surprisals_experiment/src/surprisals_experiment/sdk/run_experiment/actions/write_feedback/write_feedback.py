from pathlib import Path

from surprisals_experiment.config import Config
from ....database import ExperimentDatabase, QuestionDatabase
from ....utils.write import write
from ...prepare_flush.prepare_flush import render_flush

BEST = Path(__file__).with_name("best_attempt.sql")


async def write_feedback(config: Config, database: ExperimentDatabase, problem: QuestionDatabase):
    prompt = await render_flush(config, problem, database, BEST)
    write(config.attempt_dir(config.position["turn"]) / "feedback.txt", prompt)
