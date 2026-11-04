"""Build the flush prompt from the shortest all-pass attempt on disk."""

import json
from pathlib import Path

from surprisals_experiment.config import Config
from surprisals_experiment.prompt import Prompt
from ..database import Database
from .read_implementations import read_sources

TURN = Prompt("u/flush/turn.txt")
BEST_ATTEMPT = Path(__file__).parents[1] / "database" / "best_attempt.sql"


async def prepare_flush(config: Config, database: Database) -> str:
    question = config.question_file.read_text()
    best = await database.query(BEST_ATTEMPT, samples=config.t_samples)
    if not best:
        return question
    number, measurement = best[0]["attempt"], best[0]["measurement"]
    directory = config.attempt_dir(number)
    surprisal = config.cap_strategy == "surprisal"
    return TURN(
        question=question.rstrip("\n"), surprisal=surprisal, t_samples=config.t_samples,
        attempt=dict(
            number=number, length=measurement, advice=(directory / "advice.txt").read_text(),
            tokens=json.loads((directory / "metadata.json").read_text())["tokens"] if surprisal else None,
            sources=read_sources([config.t_dir(number, sample) / "src" for sample in range(config.t_samples)]),
        ),
    )
