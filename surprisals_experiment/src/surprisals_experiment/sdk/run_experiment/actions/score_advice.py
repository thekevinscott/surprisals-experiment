import json
from collections.abc import Callable

from surprisals_experiment.config import Config


async def score_advice(
    config: Config, advice: str, *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> int | float:
    directory = config.attempt_dir(attempt)
    measurement, tokens = await config.advice_measure.score(advice, on_delta=on_delta)
    (directory / "metadata.json").write_text(json.dumps({
        "measurement": measurement,
        **({"tokens": tokens} if tokens is not None else {}),
    }, indent=2) + "\n")
    return measurement
