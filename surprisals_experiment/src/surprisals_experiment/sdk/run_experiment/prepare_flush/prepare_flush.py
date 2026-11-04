"""Build the flush prompt from the shortest all-pass attempt on disk."""

import json
from pathlib import Path

from surprisals_experiment.config import Config
from surprisals_experiment.prompt import Prompt
from ...database import ExperimentDatabase, QuestionDatabase
from ..read_implementations import read_sources

TURN = Prompt("u/flush/turn.txt")
BEST_ATTEMPT = Path(__file__).parent / "best_attempt.sql"


async def prepare_flush(config: Config, problem: QuestionDatabase, database: ExperimentDatabase) -> str:
    question = await problem.question
    best = await database.query(BEST_ATTEMPT, samples=config.t_samples)
    if not best:
        return question
    turn = config.output / best[0]["dir"]
    return TURN(
        question=question.rstrip("\n"), unit=config.advice_measure.unit, t_samples=config.t_samples,
        attempt=dict(
            number=int(turn.name), length=best[0]["measurement"], advice=best[0]["advice"],
            tokens=json.loads(best[0]["tokens"]) if best[0]["tokens"] else None,
            sources=read_sources([turn / "ts" / str(sample) / "src" for sample in range(config.t_samples)]),
        ),
    )
