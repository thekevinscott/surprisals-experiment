from collections.abc import Callable

from surprisals_experiment.config import Config
from ....advice import Advice
from ....database import ExperimentDatabase


async def score_advice(
    config: Config, database: ExperimentDatabase, advice: Advice, *,
    on_delta: Callable[[str, str], None] | None = None,
) -> int | float:
    async with database.advice_locks[advice.directory]:
        return await advice.score(on_delta=on_delta)
