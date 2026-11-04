import json
from collections.abc import Callable

from surprisals_experiment.config import Config
from ..write_advice.save_advice import save_advice


async def surprisal_score(
    config: Config, advice: str, *, attempt: int,
    on_delta: Callable[[str, str], None] | None = None,
) -> int | float:
    directory = save_advice(config, advice)
    measurement, tokens = await config.advice_measure.score(advice, on_delta=on_delta)
    (directory / "advice.json").write_text(json.dumps({
        "score": measurement,
        "tokens": tokens,
    }, indent=2) + "\n")
    (config.attempt_dir(attempt) / "metadata.json").write_text(
        json.dumps({"advice": directory.name}, indent=2) + "\n"
    )
    return measurement
