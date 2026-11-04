import json
from collections.abc import Callable

from surprisals_experiment.config import Config


async def surprisal_score(
    config: Config, advice: str, *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> int | float:
    directory = config.attempt_dir(attempt)
    measurement, tokens = await config.advice_measure.score(advice, on_delta=on_delta)
    (directory / "metadata.json").write_text(json.dumps({
        "measurement": measurement,
        "tokens": tokens,
    }, indent=2) + "\n")
    return measurement
