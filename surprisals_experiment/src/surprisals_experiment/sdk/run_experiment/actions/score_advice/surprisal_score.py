import json
from collections.abc import Callable

from surprisals_experiment.config import Config
from ....advice import Advice


async def surprisal_score(
    config: Config, advice: Advice, *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> int | float:
    measurement, tokens = await config.advice_measure.score(advice.text, on_delta=on_delta)
    advice.write_score(measurement, tokens)
    (config.attempt_dir(attempt) / "metadata.json").write_text(
        json.dumps({"advice": advice.hash}, indent=2) + "\n"
    )
    return measurement
