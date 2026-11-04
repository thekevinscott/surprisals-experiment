from collections.abc import Callable

from surprisals_experiment.config import Config
from ....database import ExperimentDatabase
from .characters_score import characters_score
from .surprisal_score import surprisal_score

SCORES = {"characters": characters_score, "surprisal": surprisal_score}


async def score_advice(
    config: Config, database: ExperimentDatabase, advice: str, *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> int | float:
    return await SCORES[config.cap_strategy](config, database, advice, attempt=attempt, on_delta=on_delta)
