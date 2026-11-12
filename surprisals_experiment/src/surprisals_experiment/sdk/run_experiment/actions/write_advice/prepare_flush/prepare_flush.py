"""Build the flush prompt from the shortest all-pass attempt in earlier windows."""

import json
from pathlib import Path

from surprisals_experiment.prompt import Prompt
from run_database import ExperimentDatabase, QuestionDatabase
from .....advice import Advice
from .....turn import Turn
from ..render_code import render_code

TURN = Prompt("u/flush/turn.txt")
BEST_ATTEMPT = Path(__file__).parent / "best_attempt.sql"


async def prepare_flush(turn: Turn, problem: QuestionDatabase, database: ExperimentDatabase) -> str:
    config = turn.config
    question = await problem.question
    best = await database.query(BEST_ATTEMPT, samples=config.t_samples, window=turn.window)
    if not best:
        return question
    metadata = json.loads((config.output / best[0]["turn_id"] / "metadata.json").read_text())
    advice = Advice.load(config.output, metadata["advice"], config.advice_measure)
    attempt = dict(
        number=best[0]["turn"], advice=advice.text,
        code=await render_code(config, database, best[0]["turn_id"]),
    )
    return TURN(
        question=question.rstrip("\n"),
        attempt=attempt, measurement=advice.measurement,
    )
