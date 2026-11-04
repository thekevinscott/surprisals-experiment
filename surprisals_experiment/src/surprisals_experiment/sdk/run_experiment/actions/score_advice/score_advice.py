from collections.abc import Callable

from surprisals_experiment.config import Config
from ....advice import Advice


async def score_advice(
    config: Config, advice: Advice, *,
    on_delta: Callable[[str, str], None] | None = None,
) -> int | float:
    return await advice.score(on_delta=on_delta)
