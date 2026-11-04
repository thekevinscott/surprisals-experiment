from collections.abc import Callable

from surprisals_experiment.config import Config
from ....advice import Advice
from .characters_score import characters_score
from .surprisal_score import surprisal_score

SCORES = {"characters": characters_score, "surprisal": surprisal_score}


async def score_advice(
    config: Config, advice: Advice, *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> int | float:
    return await SCORES[config.cap_strategy](config, advice, attempt=attempt, on_delta=on_delta)
